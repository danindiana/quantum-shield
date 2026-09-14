"""Tests for src/pki/certs.py, against REAL X.509 certificates generated
by openssl + oqs-provider for this test run -- not fabricated DER bytes,
not fixtures checked into the repo. Skips if oqs-provider isn't built on
this machine (it's not vendored -- see README "Building liboqs")."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pki.certs import (
    load_certificate, extract_raw_public_key, verify_certificate_signature,
    is_self_signed_and_valid, algorithm_for_certificate, PKIError,
)


def _oqsprovider_available() -> bool:
    modules_dir = Path.home() / ".local/lib/ossl-modules"
    return (modules_dir / "oqsprovider.so").exists()


pytestmark = pytest.mark.skipif(
    not _oqsprovider_available(),
    reason="oqs-provider not built on this machine (not vendored -- see README)",
)


def _openssl_env():
    env = dict(os.environ)
    home = Path.home()
    env["OPENSSL_MODULES"] = str(home / ".local/lib/ossl-modules")
    env["LD_LIBRARY_PATH"] = f"{home / '.local/lib'}:{env.get('LD_LIBRARY_PATH', '')}"
    return env


def _generate_self_signed_cert(tmp_path, alg: str, cn: str, days: int = 1) -> Path:
    """Generates a real self-signed cert via openssl + oqs-provider,
    the same way test_pq_tls.py does. Returns the cert's path."""
    key_path = tmp_path / f"{cn}.key"
    cert_path = tmp_path / f"{cn}.crt"
    env = _openssl_env()

    subprocess.run(
        ["openssl", "genpkey", "-algorithm", alg, "-out", str(key_path),
         "-provider", "default", "-provider", "oqsprovider"],
        check=True, capture_output=True, env=env,
    )
    subprocess.run(
        ["openssl", "req", "-new", "-x509", "-key", str(key_path), "-out", str(cert_path),
         "-days", str(days), "-provider", "default", "-provider", "oqsprovider",
         "-subj", f"/CN={cn}"],
        check=True, capture_output=True, env=env,
    )
    return cert_path


@pytest.fixture(scope="module")
def mldsa_cert(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("pki-mldsa")
    cert_path = _generate_self_signed_cert(tmp_path, "mldsa65", "test-mldsa-ca")
    return load_certificate(cert_path.read_bytes())


@pytest.fixture(scope="module")
def falcon_cert(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("pki-falcon")
    cert_path = _generate_self_signed_cert(tmp_path, "falcon512", "test-falcon-ca")
    return load_certificate(cert_path.read_bytes())


def test_algorithm_detected_from_oid_mldsa(mldsa_cert):
    assert algorithm_for_certificate(mldsa_cert) == "ML-DSA-65"


def test_algorithm_detected_from_oid_falcon(falcon_cert):
    assert algorithm_for_certificate(falcon_cert) == "Falcon-512"


def test_extract_raw_public_key_matches_expected_size_mldsa(mldsa_cert):
    pk = extract_raw_public_key(mldsa_cert)
    assert len(pk) == 1952  # ML-DSA-65's real public key size, per src/algorithms/signature.py


def test_extract_raw_public_key_matches_expected_size_falcon(falcon_cert):
    pk = extract_raw_public_key(falcon_cert)
    assert len(pk) == 897  # Falcon-512's real public key size


def test_verify_real_self_signed_certificate_mldsa(mldsa_cert):
    pk = extract_raw_public_key(mldsa_cert)
    assert verify_certificate_signature(mldsa_cert, pk, "ML-DSA-65") is True


def test_verify_real_self_signed_certificate_falcon(falcon_cert):
    pk = extract_raw_public_key(falcon_cert)
    assert verify_certificate_signature(falcon_cert, pk, "Falcon-512") is True


def test_verify_fails_with_wrong_public_key(mldsa_cert, falcon_cert):
    """A wrong-sized key (Falcon-512's, 897 bytes, against an ML-DSA-65
    verify call that expects 1952) must not silently verify -- it either
    raises on the size mismatch or returns False. It must never return
    True."""
    wrong_pk = extract_raw_public_key(falcon_cert)
    try:
        result = verify_certificate_signature(mldsa_cert, wrong_pk, "ML-DSA-65")
    except Exception:
        return  # raising is an acceptable rejection
    assert result is False


def test_verify_fails_with_a_different_valid_key_same_algorithm(mldsa_cert, tmp_path):
    """A different, unrelated ML-DSA-65 public key of the correct size
    must fail verification, not just a wrong-sized one."""
    other_cert_path = _generate_self_signed_cert(tmp_path, "mldsa65", "unrelated-ca")
    other_cert = load_certificate(other_cert_path.read_bytes())
    other_pk = extract_raw_public_key(other_cert)
    assert len(other_pk) == 1952
    assert verify_certificate_signature(mldsa_cert, other_pk, "ML-DSA-65") is False


def test_is_self_signed_and_valid_mldsa(mldsa_cert):
    assert is_self_signed_and_valid(mldsa_cert) is True


def test_is_self_signed_and_valid_falcon(falcon_cert):
    assert is_self_signed_and_valid(falcon_cert) is True


def test_is_self_signed_and_valid_explicit_algorithm(mldsa_cert):
    assert is_self_signed_and_valid(mldsa_cert, algorithm="ML-DSA-65") is True


def test_unrecognized_oid_raises_pkierror():
    class FakeOID:
        dotted_string = "1.2.3.4.5.6.7.8.9"

    class FakeCert:
        signature_algorithm_oid = FakeOID()

    with pytest.raises(PKIError):
        algorithm_for_certificate(FakeCert())


def test_load_certificate_rejects_garbage():
    with pytest.raises(PKIError):
        load_certificate(b"this is not a certificate")
