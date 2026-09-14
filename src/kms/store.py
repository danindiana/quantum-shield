"""A minimal, file-based, passphrase-encrypted key store.

This is what src/kms/ was missing entirely -- simple_ssh_keygen.py
currently writes raw private key bytes straight to ~/.ssh/, protected
only by Unix file permissions (0600). This module gives library
consumers a way to store a KEM or signature keypair encrypted at rest
instead, without changing how kem.py/signature.py generate keys.

Design, deliberately kept small:
- One JSON file per key, named `<name>.qskey.json`, containing metadata
  in plaintext (algorithm, key type, creation time) and the actual key
  material AEAD-encrypted (AES-256-GCM) under a key derived from a
  passphrase via scrypt.
- The key `name` is bound in as AEAD associated data, so a ciphertext
  file can't be silently renamed/swapped without decryption failing.
- No key rotation, no multi-user access control, no hardware-backed
  storage (HSM/TPM) -- see docs/FUTURE_DIRECTIONS.md for what's still
  missing on top of this.

NOT AUDITED -- see the project README's disclaimer. This uses the
`cryptography` library's AEAD/KDF primitives directly; it implements no
cryptographic algorithms of its own, same boundary as src/algorithms/.
"""
import json
import os
from base64 import b64encode, b64decode
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

_SCRYPT_N = 2 ** 14
_SCRYPT_R = 8
_SCRYPT_P = 1
_KEY_LEN = 32
_SALT_LEN = 16
_NONCE_LEN = 12

KEY_TYPES = ("kem", "signature")


class KeyStoreError(RuntimeError):
    """Raised for any key store failure other than a wrong passphrase."""


class WrongPassphraseError(KeyStoreError):
    """Raised when decryption fails -- either the passphrase was wrong or
    the file was corrupted/tampered with. AES-GCM can't distinguish the
    two (that's the point of an AEAD authentication tag), so neither can
    this."""


class KeyStore:
    def __init__(self, base_dir=None):
        self.base_dir = Path(base_dir) if base_dir else Path.home() / ".quantum-shield" / "keystore"
        self.base_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

    def _path_for(self, name: str) -> Path:
        if not name or "/" in name or name.startswith("."):
            raise KeyStoreError(f"invalid key name: {name!r}")
        return self.base_dir / f"{name}.qskey.json"

    @staticmethod
    def _derive_key(passphrase: bytes, salt: bytes) -> bytes:
        kdf = Scrypt(salt=salt, length=_KEY_LEN, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P)
        return kdf.derive(passphrase)

    def save_keypair(self, name: str, algorithm: str, key_type: str,
                      public_key: bytes, secret_key: bytes, passphrase: str,
                      overwrite: bool = False) -> Path:
        """Encrypts and writes a keypair. Raises KeyStoreError if a key
        with this name already exists, unless overwrite=True."""
        if key_type not in KEY_TYPES:
            raise KeyStoreError(f"key_type must be one of {KEY_TYPES}, got {key_type!r}")
        path = self._path_for(name)
        if path.exists() and not overwrite:
            raise KeyStoreError(f"key {name!r} already exists at {path} (pass overwrite=True to replace it)")

        salt = os.urandom(_SALT_LEN)
        nonce = os.urandom(_NONCE_LEN)
        aes_key = self._derive_key(passphrase.encode(), salt)
        payload = json.dumps({
            "public_key": b64encode(public_key).decode(),
            "secret_key": b64encode(secret_key).decode(),
        }).encode()
        ciphertext = AESGCM(aes_key).encrypt(nonce, payload, associated_data=name.encode())

        record = {
            "name": name,
            "algorithm": algorithm,
            "key_type": key_type,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "kdf": {
                "algorithm": "scrypt",
                "n": _SCRYPT_N, "r": _SCRYPT_R, "p": _SCRYPT_P,
                "salt": b64encode(salt).decode(),
            },
            "nonce": b64encode(nonce).decode(),
            "ciphertext": b64encode(ciphertext).decode(),
        }
        path.write_text(json.dumps(record, indent=2))
        path.chmod(0o600)
        return path

    def load_keypair(self, name: str, passphrase: str) -> dict:
        """Returns {"algorithm", "key_type", "created_utc", "public_key",
        "secret_key"} with the keys decrypted back to bytes. Raises
        WrongPassphraseError on a bad passphrase or corrupted file."""
        path = self._path_for(name)
        if not path.exists():
            raise KeyStoreError(f"no key named {name!r} in {self.base_dir}")

        record = json.loads(path.read_text())
        kdf_params = record["kdf"]
        salt = b64decode(kdf_params["salt"])
        nonce = b64decode(record["nonce"])
        ciphertext = b64decode(record["ciphertext"])
        aes_key = self._derive_key(passphrase.encode(), salt)

        try:
            payload = AESGCM(aes_key).decrypt(nonce, ciphertext, associated_data=name.encode())
        except Exception as exc:
            raise WrongPassphraseError(
                f"failed to decrypt {name!r}: wrong passphrase or corrupted file") from exc

        data = json.loads(payload)
        return {
            "algorithm": record["algorithm"],
            "key_type": record["key_type"],
            "created_utc": record["created_utc"],
            "public_key": b64decode(data["public_key"]),
            "secret_key": b64decode(data["secret_key"]),
        }

    def list_keys(self) -> list:
        """Returns metadata (no key material) for every stored key."""
        out = []
        for path in sorted(self.base_dir.glob("*.qskey.json")):
            record = json.loads(path.read_text())
            out.append({k: record[k] for k in ("name", "algorithm", "key_type", "created_utc")})
        return out

    def delete_key(self, name: str) -> None:
        path = self._path_for(name)
        if not path.exists():
            raise KeyStoreError(f"no key named {name!r} in {self.base_dir}")
        path.unlink()
