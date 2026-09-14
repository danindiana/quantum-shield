"""A minimal, file-based, passphrase-encrypted key store.

This is what src/kms/ was missing entirely -- simple_ssh_keygen.py
currently writes raw private key bytes straight to ~/.ssh/, protected
only by Unix file permissions (0600). This module gives library
consumers a way to store a KEM or signature keypair encrypted at rest
instead, without changing how kem.py/signature.py generate keys.

Design, deliberately kept small:
- One JSON file per key's *active* generation, named `<name>.qskey.json`,
  containing metadata in plaintext (algorithm, key type, generation,
  status, creation time) and the actual key material AEAD-encrypted
  (AES-256-GCM) under a key derived from a passphrase via scrypt.
- The key `name` is bound in as AEAD associated data, so a ciphertext
  file can't be silently renamed/swapped without decryption failing.
- `rotate_key()` archives the current active generation as
  `<name>.g<N>.qskey.json` (status "rotated") and writes a new active
  generation N+1 under the original `<name>.qskey.json`. `revoke_key()`
  marks the active generation's status "revoked" in place --
  `load_keypair()` then refuses it unless `allow_revoked=True` is passed
  explicitly (the public key may still be needed to verify old
  signatures; the secret key generally shouldn't be used for anything
  new once revoked).
- Still no multi-user access control, no hardware-backed storage
  (HSM/TPM) -- see docs/FUTURE_DIRECTIONS.md for what's still missing.

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

    def _encrypt_and_write(self, path: Path, name: str, algorithm: str, key_type: str,
                            public_key: bytes, secret_key: bytes, passphrase: str,
                            generation: int, status: str = "active") -> None:
        """Shared by save_keypair() and rotate_key() -- one place that
        knows how to encrypt and serialize a key record, so this logic
        can't drift into two subtly different copies (the same class of
        bug src/algorithms/ was refactored to avoid)."""
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
            "generation": generation,
            "status": status,
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

    def save_keypair(self, name: str, algorithm: str, key_type: str,
                      public_key: bytes, secret_key: bytes, passphrase: str,
                      overwrite: bool = False) -> Path:
        """Encrypts and writes a keypair as generation 1. Raises
        KeyStoreError if a key with this name already exists, unless
        overwrite=True."""
        if key_type not in KEY_TYPES:
            raise KeyStoreError(f"key_type must be one of {KEY_TYPES}, got {key_type!r}")
        path = self._path_for(name)
        if path.exists() and not overwrite:
            raise KeyStoreError(f"key {name!r} already exists at {path} (pass overwrite=True to replace it)")

        self._encrypt_and_write(path, name, algorithm, key_type,
                                 public_key, secret_key, passphrase, generation=1)
        return path

    def rotate_key(self, name: str, new_public_key: bytes, new_secret_key: bytes,
                    new_passphrase: str) -> tuple:
        """Archives the current active generation of `name` (status
        becomes "rotated") and writes a new active generation with the
        given key material, encrypted under new_passphrase (which need
        not match whatever passphrase protected the old generation --
        rotation never needs to decrypt the old material at all).
        algorithm/key_type carry over from the key being rotated.

        Returns (archive_path, new_active_path). Raises KeyStoreError if
        there's no active key to rotate, or if it's already revoked."""
        path = self._path_for(name)
        if not path.exists():
            raise KeyStoreError(f"no active key named {name!r} to rotate")

        old_record = json.loads(path.read_text())
        if old_record.get("status") == "revoked":
            raise KeyStoreError(f"key {name!r} is revoked; can't rotate a revoked key")

        generation = old_record.get("generation", 1)
        algorithm = old_record["algorithm"]
        key_type = old_record["key_type"]

        archive_path = self.base_dir / f"{name}.g{generation}.qskey.json"
        if archive_path.exists():
            raise KeyStoreError(f"archive slot {archive_path} already exists -- refusing to overwrite history")

        archived_record = dict(old_record)
        archived_record["status"] = "rotated"
        archived_record["rotated_at"] = datetime.now(timezone.utc).isoformat()
        archive_path.write_text(json.dumps(archived_record, indent=2))
        archive_path.chmod(0o600)

        self._encrypt_and_write(path, name, algorithm, key_type,
                                 new_public_key, new_secret_key, new_passphrase,
                                 generation=generation + 1)
        return archive_path, path

    def revoke_key(self, name: str, reason: str = None) -> None:
        """Marks the active generation of `name` as revoked, in place.
        load_keypair() will refuse it afterwards unless called with
        allow_revoked=True."""
        path = self._path_for(name)
        if not path.exists():
            raise KeyStoreError(f"no key named {name!r} in {self.base_dir}")
        record = json.loads(path.read_text())
        record["status"] = "revoked"
        record["revoked_at"] = datetime.now(timezone.utc).isoformat()
        if reason:
            record["revoked_reason"] = reason
        path.write_text(json.dumps(record, indent=2))
        path.chmod(0o600)

    def load_keypair(self, name: str, passphrase: str, allow_revoked: bool = False) -> dict:
        """Returns {"algorithm", "key_type", "generation", "status",
        "created_utc", "public_key", "secret_key"} with the keys
        decrypted back to bytes. Raises WrongPassphraseError on a bad
        passphrase or corrupted file. Raises KeyStoreError if the key has
        been revoked, unless allow_revoked=True (e.g. to still verify old
        signatures against a revoked signing key's public half)."""
        path = self._path_for(name)
        if not path.exists():
            raise KeyStoreError(f"no key named {name!r} in {self.base_dir}")

        record = json.loads(path.read_text())
        if record.get("status") == "revoked" and not allow_revoked:
            raise KeyStoreError(
                f"key {name!r} is revoked (reason: {record.get('revoked_reason', 'unspecified')}); "
                f"pass allow_revoked=True to load it anyway")
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
            "generation": record.get("generation", 1),
            "status": record.get("status", "active"),
            "created_utc": record["created_utc"],
            "public_key": b64decode(data["public_key"]),
            "secret_key": b64decode(data["secret_key"]),
        }

    def list_keys(self) -> list:
        """Returns metadata (no key material) for every key's *active*
        generation -- archived history entries (status "rotated") are
        deliberately excluded here; use list_history() for those. This
        filters on the record's own status field, not on filename
        pattern, so it can't be fooled by a coincidentally-named file."""
        out = []
        for path in sorted(self.base_dir.glob("*.qskey.json")):
            record = json.loads(path.read_text())
            if record.get("status") == "rotated":
                continue
            out.append({k: record.get(k) for k in
                        ("name", "algorithm", "key_type", "generation", "status", "created_utc")})
        return out

    def list_history(self, name: str) -> list:
        """Returns metadata for every generation of `name`, oldest first
        -- archived (rotated) generations plus the current active one if
        it exists. No key material."""
        out = []
        for path in sorted(self.base_dir.glob(f"{name}.g*.qskey.json")):
            record = json.loads(path.read_text())
            out.append({k: record.get(k) for k in
                        ("name", "algorithm", "key_type", "generation", "status", "created_utc", "rotated_at")})
        active_path = self._path_for(name)
        if active_path.exists():
            record = json.loads(active_path.read_text())
            out.append({k: record.get(k) for k in
                        ("name", "algorithm", "key_type", "generation", "status", "created_utc")})
        out.sort(key=lambda r: r.get("generation", 1))
        return out

    def delete_key(self, name: str) -> None:
        """Deletes the active generation only. Archived history
        (<name>.g<N>.qskey.json files) is left in place -- delete those
        individually if you actually want to purge history, not just
        retire the active key."""
        path = self._path_for(name)
        if not path.exists():
            raise KeyStoreError(f"no key named {name!r} in {self.base_dir}")
        path.unlink()
