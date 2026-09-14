"""Tests for src/kms/store.py, using real keypairs from src/algorithms/
(not fabricated bytes) and a real cryptography backend -- not mocked."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.kms.store import KeyStore, KeyStoreError, WrongPassphraseError
from src.algorithms.kem import MLKEM768, KEMError


@pytest.fixture
def store(tmp_path):
    return KeyStore(base_dir=tmp_path / "keystore")


@pytest.fixture(scope="module")
def kem_keypair():
    try:
        kem = MLKEM768()
    except KEMError as exc:
        pytest.skip(f"liboqs / ML-KEM-768 unavailable: {exc}")
    return kem.generate_keypair()  # (public_key, secret_key)


def test_save_creates_encrypted_file_on_disk(store, kem_keypair):
    pk, sk = kem_keypair
    path = store.save_keypair("test-key", "ML-KEM-768", "kem", pk, sk, "correct horse")
    assert path.exists()
    raw = path.read_text()
    # the raw secret key bytes must never appear in plaintext on disk
    assert sk.hex() not in raw
    assert "ciphertext" in raw


def test_save_sets_restrictive_file_permissions(store, kem_keypair):
    pk, sk = kem_keypair
    path = store.save_keypair("perms-key", "ML-KEM-768", "kem", pk, sk, "pw")
    assert (path.stat().st_mode & 0o777) == 0o600


def test_round_trip_with_correct_passphrase(store, kem_keypair):
    pk, sk = kem_keypair
    store.save_keypair("roundtrip", "ML-KEM-768", "kem", pk, sk, "correct horse battery staple")
    loaded = store.load_keypair("roundtrip", "correct horse battery staple")
    assert loaded["public_key"] == pk
    assert loaded["secret_key"] == sk
    assert loaded["algorithm"] == "ML-KEM-768"
    assert loaded["key_type"] == "kem"


def test_wrong_passphrase_raises_and_never_returns_key_material(store, kem_keypair):
    pk, sk = kem_keypair
    store.save_keypair("guarded", "ML-KEM-768", "kem", pk, sk, "the real passphrase")
    with pytest.raises(WrongPassphraseError):
        store.load_keypair("guarded", "a guess")


def test_duplicate_name_without_overwrite_raises(store, kem_keypair):
    pk, sk = kem_keypair
    store.save_keypair("dup", "ML-KEM-768", "kem", pk, sk, "pw")
    with pytest.raises(KeyStoreError):
        store.save_keypair("dup", "ML-KEM-768", "kem", pk, sk, "pw")


def test_overwrite_true_replaces_existing_key(store, kem_keypair):
    pk, sk = kem_keypair
    store.save_keypair("replace-me", "ML-KEM-768", "kem", pk, sk, "old pw")
    pk2, sk2 = kem_keypair[0], b"\x00" * len(kem_keypair[1])  # deliberately different secret
    store.save_keypair("replace-me", "ML-KEM-768", "kem", pk2, sk2, "new pw", overwrite=True)
    loaded = store.load_keypair("replace-me", "new pw")
    assert loaded["secret_key"] == sk2


def test_list_keys_returns_metadata_without_key_material(store, kem_keypair):
    pk, sk = kem_keypair
    store.save_keypair("listed-1", "ML-KEM-768", "kem", pk, sk, "pw")
    store.save_keypair("listed-2", "ML-DSA-65", "signature", pk, sk, "pw")
    keys = store.list_keys()
    names = {k["name"] for k in keys}
    assert {"listed-1", "listed-2"} <= names
    for k in keys:
        assert "public_key" not in k
        assert "secret_key" not in k


def test_delete_key_removes_it(store, kem_keypair):
    pk, sk = kem_keypair
    store.save_keypair("to-delete", "ML-KEM-768", "kem", pk, sk, "pw")
    store.delete_key("to-delete")
    with pytest.raises(KeyStoreError):
        store.load_keypair("to-delete", "pw")


def test_load_nonexistent_key_raises_keystoreerror_not_wrongpassphrase(store):
    with pytest.raises(KeyStoreError):
        store.load_keypair("never-existed", "pw")


def test_invalid_key_type_rejected(store, kem_keypair):
    pk, sk = kem_keypair
    with pytest.raises(KeyStoreError):
        store.save_keypair("bad-type", "ML-KEM-768", "not-a-real-type", pk, sk, "pw")


def test_key_name_path_traversal_rejected(store, kem_keypair):
    pk, sk = kem_keypair
    with pytest.raises(KeyStoreError):
        store.save_keypair("../escape", "ML-KEM-768", "kem", pk, sk, "pw")
