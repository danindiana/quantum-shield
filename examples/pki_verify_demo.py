#!/usr/bin/env python3
"""
Demo of src/pki/certs.py: generate a real self-signed ML-DSA-65
certificate via openssl + oqs-provider (the same way test_pq_tls.py
does), then verify its signature using ONLY this project's own liboqs
binding (src/algorithms/signature.py) -- no openssl involved in the
verification step at all. Then generates a real 2-level chain (a CA
cert plus a leaf cert actually signed by that CA, not self-signed) and
verifies verify_chain() against both the real issuer and a deliberately
unrelated CA, to prove the check discriminates rather than passing
either way.

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
    is_self_signed_and_valid, verify_chain, algorithm_for_certificate,
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

        print("\n" + "=" * 60)
        print("🔗 Now a real 2-level chain: a CA cert, and a LEAF cert")
        print("   actually signed by that CA (not self-signed)...")
        ca_key, ca_crt = Path(tmpdir) / "ca2.key", Path(tmpdir) / "ca2.crt"
        leaf_key = Path(tmpdir) / "leaf.key"
        leaf_csr = Path(tmpdir) / "leaf.csr"
        leaf_crt = Path(tmpdir) / "leaf.crt"

        subprocess.run(
            ["openssl", "req", "-x509", "-new", "-newkey", "mldsa65", "-keyout", str(ca_key),
             "-out", str(ca_crt), "-days", "3650", "-nodes", "-subj", "/CN=demo-root-ca",
             "-provider", "default", "-provider", "oqsprovider"],
            check=True, env=env, capture_output=True,
        )
        subprocess.run(
            ["openssl", "genpkey", "-algorithm", "mldsa65", "-out", str(leaf_key),
             "-provider", "default", "-provider", "oqsprovider"],
            check=True, env=env, capture_output=True,
        )
        subprocess.run(
            ["openssl", "req", "-new", "-key", str(leaf_key), "-out", str(leaf_csr),
             "-subj", "/CN=leaf.example", "-provider", "default", "-provider", "oqsprovider"],
            check=True, env=env, capture_output=True,
        )
        subprocess.run(
            ["openssl", "x509", "-req", "-in", str(leaf_csr), "-CA", str(ca_crt),
             "-CAkey", str(ca_key), "-CAcreateserial", "-out", str(leaf_crt), "-days", "365",
             "-provider", "default", "-provider", "oqsprovider"],
            check=True, env=env, capture_output=True,
        )

        ca = load_certificate(ca_crt.read_bytes())
        leaf = load_certificate(leaf_crt.read_bytes())
        print(f"   leaf issuer: {leaf.issuer}  (matches CA subject: {ca.subject})")

        chain_ok = verify_chain(leaf, ca)
        print(f"   verify_chain(leaf, real_ca) -> {chain_ok} (expected: True)")

        print("\n🔍 Negative control: an UNRELATED CA that did not sign this leaf...")
        unrelated_ca_key = Path(tmpdir) / "unrelated_ca.key"
        unrelated_ca_crt = Path(tmpdir) / "unrelated_ca.crt"
        subprocess.run(
            ["openssl", "req", "-x509", "-new", "-newkey", "mldsa65", "-keyout", str(unrelated_ca_key),
             "-out", str(unrelated_ca_crt), "-days", "3650", "-nodes", "-subj", "/CN=unrelated-ca",
             "-provider", "default", "-provider", "oqsprovider"],
            check=True, env=env, capture_output=True,
        )
        unrelated_ca = load_certificate(unrelated_ca_crt.read_bytes())
        chain_bad = verify_chain(leaf, unrelated_ca)
        print(f"   verify_chain(leaf, unrelated_ca) -> {chain_bad} (expected: False)")

        if not (chain_ok and not chain_bad):
            print("\n❌ BUG: chain verification did not discriminate correctly")
            return 1

    print("\n✅ Verified a real X.509 certificate's PQ signature end-to-end, and a real\n"
          "   2-level chain that correctly rejects an unrelated issuer -- openssl only\n"
          "   used to generate certs, never to verify them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
