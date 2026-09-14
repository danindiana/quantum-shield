"""Integration tests for src/algorithms/signature.py against the real
liboqs.so installed on this machine -- not a mock.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.algorithms.signature import (
    MLDSA65, SLHDSA128s, SignatureError, ALG_ML_DSA_65, ALG_SLH_DSA_128S,
)


@pytest.fixture(scope="module")
def sig():
    try:
        return MLDSA65()
    except SignatureError as exc:
        pytest.skip(f"liboqs / {ALG_ML_DSA_65} unavailable: {exc}")


@pytest.fixture(scope="module")
def slh_sig():
    try:
        return SLHDSA128s()
    except SignatureError as exc:
        pytest.skip(f"liboqs / {ALG_SLH_DSA_128S} unavailable: {exc}")


def test_reports_real_sizes_not_hardcoded(sig):
    # ML-DSA-65's actual FIPS 204 sizes -- these must come from the
    # struct, since simple_ssh_keygen.py's old hardcoded values (1952 /
    # 4864) were for public/secret key only and never had a signature
    # length at all.
    assert sig.length_public_key == 1952
    assert sig.length_secret_key == 4032
    assert sig.length_signature == 3309


def test_keypair_returns_correctly_sized_keys(sig):
    pk, sk = sig.generate_keypair()
    assert len(pk) == sig.length_public_key
    assert len(sk) == sig.length_secret_key


def test_sign_verify_round_trip(sig):
    pk, sk = sig.generate_keypair()
    message = b"quantum-shield integration test"
    signature = sig.sign(sk, message)
    assert sig.verify(pk, message, signature) is True


def test_verify_fails_on_tampered_message(sig):
    pk, sk = sig.generate_keypair()
    signature = sig.sign(sk, b"original message")
    assert sig.verify(pk, b"tampered message", signature) is False


def test_verify_fails_with_wrong_public_key(sig):
    pk1, sk1 = sig.generate_keypair()
    pk2, _sk2 = sig.generate_keypair()
    message = b"quantum-shield integration test"
    signature = sig.sign(sk1, message)
    assert sig.verify(pk2, message, signature) is False


def test_rejects_wrong_length_secret_key(sig):
    with pytest.raises(SignatureError):
        sig.sign(b"too short", b"message")


# --- SLH-DSA-SHA2-128s: was previously (incorrectly) logged as
# "disabled in this liboqs build" -- it was never disabled, the
# identifier string ("SLH-DSA-128s") just didn't match liboqs's actual
# one ("SLH_DSA_PURE_SHA2_128S"). See ALG_SLH_DSA_128S's comment in
# src/algorithms/signature.py and docs/RESEARCH_NOTES.md's corrected
# entry. Fewer tests than ML-DSA-65 above -- same coverage shape,
# not duplicated line for line.

def test_slh_dsa_reports_real_fips205_sizes(slh_sig):
    # SLH-DSA-SHA2-128s's actual FIPS 205 sizes.
    assert slh_sig.length_public_key == 32
    assert slh_sig.length_secret_key == 64
    assert slh_sig.length_signature == 7856


def test_slh_dsa_sign_verify_round_trip(slh_sig):
    pk, sk = slh_sig.generate_keypair()
    message = b"quantum-shield SLH-DSA integration test"
    signature = slh_sig.sign(sk, message)
    assert slh_sig.verify(pk, message, signature) is True


def test_slh_dsa_verify_fails_on_tampered_message(slh_sig):
    pk, sk = slh_sig.generate_keypair()
    signature = slh_sig.sign(sk, b"original message")
    assert slh_sig.verify(pk, b"tampered message", signature) is False
