#!/usr/bin/env python3
"""
Demo of src/pki/certs.py: generate a real self-signed ML-DSA-65
certificate via openssl + oqs-provider (the same way test_pq_tls.py
does), then verify its signature using ONLY this project's own liboqs
binding (src/algorithms/signature.py) -- no openssl involved in the
verification step at all.

Requires oqs-provider to be built (see README "Building liboqs"); exits
early with a clear message if it isn't.

    python3 examples/pki_verify_demo.py
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.pki.certs import (
    load_certificate, extract_raw_public_key, verify_certificate_signature,
    is_self_signed_and_valid, algorithm_for_certificate,
)


def main():
    modules_dir = Path.home() / ".local/lib/ossl-modules"
    if not (modules_dir / "oqsprovider.so").exists():
        print(f"⚠️  oqs-provider not found at {modules_dir} -- build it first "
              f"(see README's \"Building liboqs\" section).")
        return 1

    env = dict(os.environ)
    env["OPENSSL_MODULES"] = str(modules_dir)
    env["LD_LIBRARY_PATH"] = f"{Path.home() / '.local/lib'}:{env.get('LD_LIBRARY_PATH', '')}"

    with tempfile.TemporaryDirectory() as tmpdir:
        key_path = Path(tmpdir) / "ca.key"
        cert_path = Path(tmpdir) / "ca.crt"

        print("🔧 Generating a real ML-DSA-65 self-signed cert via openssl + oqs-provider...")
        subprocess.run(
            ["openssl", "genpkey", "-algorithm", "mldsa65", "-out", str(key_path),
             "-provider", "default", "-provider", "oqsprovider"],
            check=True, env=env, capture_output=True,
        )
        subprocess.run(
            ["openssl", "req", "-new", "-x509", "-key", str(key_path), "-out", str(cert_path),
             "-days", "1", "-provider", "default", "-provider", "oqsprovider",
             "-subj", "/CN=pki-verify-demo"],
            check=True, env=env, capture_output=True,
        )
        print(f"   Wrote {cert_path}")

        cert = load_certificate(cert_path.read_bytes())
        print(f"\n📜 Parsed with cryptography's X.509 parser (structure only -- it")
        print(f"   can't verify this signature algorithm itself):")
        print(f"   subject: {cert.subject}")
        print(f"   signature algorithm OID: {cert.signature_algorithm_oid.dotted_string}")

        algorithm = algorithm_for_certificate(cert)
        print(f"   -> recognized as: {algorithm}")

        public_key = extract_raw_public_key(cert)
        print(f"\n🔑 Extracted raw public key from SubjectPublicKeyInfo: {len(public_key)} bytes")

        print(f"\n🛡️  Verifying the certificate's signature using ONLY "
              f"src/algorithms/signature.py (no openssl):")
        ok = verify_certificate_signature(cert, public_key, algorithm)
        print(f"   verify_certificate_signature(...) -> {ok}")

        ok2 = is_self_signed_and_valid(cert)
        print(f"   is_self_signed_and_valid(cert) -> {ok2}")

        if not (ok and ok2):
            print("\n❌ BUG: a freshly generated, unexpired self-signed cert should verify")
            return 1

    print("\n✅ Verified a real X.509 certificate's PQ signature end-to-end, "
          "openssl only used to generate it, not to check it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
