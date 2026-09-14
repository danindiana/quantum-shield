"""Integration tests for src/algorithms/kem.py against the real liboqs.so
installed on this machine -- not a mock. Run with LD_LIBRARY_PATH set to
wherever liboqs.so lives if it's not under ~/.local/lib.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.algorithms.kem import MLKEM768, KEMError, ALG_ML_KEM_768


@pytest.fixture(scope="module")
def kem():
    try:
        return MLKEM768()
    except KEMError as exc:
        pytest.skip(f"liboqs / {ALG_ML_KEM_768} unavailable: {exc}")


def test_reports_real_sizes_not_hardcoded(kem):
    # These are ML-KEM-768's actual FIPS 203 sizes; asserting them proves
    # the struct read worked, not that we happened to hardcode the same
    # numbers ourselves.
    assert kem.length_public_key == 1184
    assert kem.length_secret_key == 2400
    assert kem.length_ciphertext == 1088
    assert kem.length_shared_secret == 32


def test_keypair_returns_correctly_sized_keys(kem):
    pk, sk = kem.generate_keypair()
    assert len(pk) == kem.length_public_key
    assert len(sk) == kem.length_secret_key


def test_encapsulate_decapsulate_round_trip(kem):
    pk, sk = kem.generate_keypair()
    ciphertext, shared_secret_sender = kem.encapsulate(pk)
    shared_secret_receiver = kem.decapsulate(sk, ciphertext)
    assert shared_secret_sender == shared_secret_receiver
    assert len(shared_secret_sender) == kem.length_shared_secret


def test_decapsulate_with_wrong_secret_key_gives_different_secret(kem):
    pk, _sk = kem.generate_keypair()
    _pk2, sk2 = kem.generate_keypair()
    ciphertext, shared_secret_sender = kem.encapsulate(pk)
    # ML-KEM is IND-CCA2 with implicit rejection: decapsulating with the
    # wrong key doesn't error, it silently returns a different secret.
    shared_secret_wrong = kem.decapsulate(sk2, ciphertext)
    assert shared_secret_wrong != shared_secret_sender


def test_rejects_wrong_length_public_key(kem):
    with pytest.raises(KEMError):
        kem.encapsulate(b"too short")
