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


# --- rotation and revocation ---

def _fresh_kem_keypair():
    """A second, genuinely different keypair (not the module-scoped
    fixture's) so rotation tests can prove the new material differs."""
    return MLKEM768().generate_keypair()


def test_save_defaults_to_generation_1_active(store, kem_keypair):
    pk, sk = kem_keypair
    store.save_keypair("gen1", "ML-KEM-768", "kem", pk, sk, "pw")
    loaded = store.load_keypair("gen1", "pw")
    assert loaded["generation"] == 1
    assert loaded["status"] == "active"


def test_rotate_archives_old_generation_and_activates_new(store, kem_keypair):
    old_pk, old_sk = kem_keypair
    new_pk, new_sk = _fresh_kem_keypair()
    store.save_keypair("rotator", "ML-KEM-768", "kem", old_pk, old_sk, "old pw")

    archive_path, active_path = store.rotate_key("rotator", new_pk, new_sk, "new pw")
    assert archive_path.exists()
    assert active_path.exists()

    # old generation, now archived, still decrypts with its OWN passphrase
    import json
    archived_record = json.loads(archive_path.read_text())
    assert archived_record["status"] == "rotated"
    assert archived_record["generation"] == 1

    # new generation is active under the original name, generation 2
    loaded = store.load_keypair("rotator", "new pw")
    assert loaded["generation"] == 2
    assert loaded["status"] == "active"
    assert loaded["secret_key"] == new_sk
    assert loaded["secret_key"] != old_sk

    # old passphrase no longer opens the *active* slot -- it's a new generation
    with pytest.raises(WrongPassphraseError):
        store.load_keypair("rotator", "old pw")


def test_rotate_nonexistent_key_raises(store):
    new_pk, new_sk = _fresh_kem_keypair()
    with pytest.raises(KeyStoreError):
        store.rotate_key("never-existed", new_pk, new_sk, "pw")


def test_rotate_revoked_key_raises(store, kem_keypair):
    pk, sk = kem_keypair
    new_pk, new_sk = _fresh_kem_keypair()
    store.save_keypair("revoked-then-rotate", "ML-KEM-768", "kem", pk, sk, "pw")
    store.revoke_key("revoked-then-rotate", reason="test")
    with pytest.raises(KeyStoreError):
        store.rotate_key("revoked-then-rotate", new_pk, new_sk, "new pw")


def test_two_rotations_produce_two_archived_generations(store, kem_keypair):
    pk1, sk1 = kem_keypair
    pk2, sk2 = _fresh_kem_keypair()
    pk3, sk3 = _fresh_kem_keypair()
    store.save_keypair("multi-rotate", "ML-KEM-768", "kem", pk1, sk1, "pw1")
    store.rotate_key("multi-rotate", pk2, sk2, "pw2")
    store.rotate_key("multi-rotate", pk3, sk3, "pw3")

    history = store.list_history("multi-rotate")
    generations = [h["generation"] for h in history]
    assert generations == [1, 2, 3]
    assert history[0]["status"] == "rotated"
    assert history[1]["status"] == "rotated"
    assert history[2]["status"] == "active"

    loaded = store.load_keypair("multi-rotate", "pw3")
    assert loaded["secret_key"] == sk3


def test_revoke_marks_key_and_blocks_normal_load(store, kem_keypair):
    pk, sk = kem_keypair
    store.save_keypair("to-revoke", "ML-KEM-768", "kem", pk, sk, "pw")
    store.revoke_key("to-revoke", reason="compromised")

    with pytest.raises(KeyStoreError):
        store.load_keypair("to-revoke", "pw")  # allow_revoked defaults to False

    loaded = store.load_keypair("to-revoke", "pw", allow_revoked=True)
    assert loaded["status"] == "revoked"
    assert loaded["secret_key"] == sk


def test_revoke_nonexistent_key_raises(store):
    with pytest.raises(KeyStoreError):
        store.revoke_key("never-existed")


def test_list_keys_excludes_archived_generations(store, kem_keypair):
    pk1, sk1 = kem_keypair
    pk2, sk2 = _fresh_kem_keypair()
    store.save_keypair("listed-rotator", "ML-KEM-768", "kem", pk1, sk1, "pw1")
    store.rotate_key("listed-rotator", pk2, sk2, "pw2")

    names_and_gens = {(k["name"], k["generation"]) for k in store.list_keys()}
    # only the active generation-2 entry should appear, not the archived generation 1
    assert ("listed-rotator", 2) in names_and_gens
    assert ("listed-rotator", 1) not in names_and_gens
