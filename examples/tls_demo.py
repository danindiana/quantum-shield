#!/usr/bin/env python3
"""
Demo of src/protocols/tls/demo.py: a real TLS 1.3 handshake using
ML-KEM-768 for key exchange, authenticated with a classical ECDSA
certificate (see the module's docstring for why -- OpenSSL 3.2+ is
needed to authenticate with a PQ-signed certificate, and this project's
build environment is OpenSSL 3.0.2).

Then shows the negative control: pointing the client at a *different*
group than the server offers, proving the positive case above is real
evidence the requested group was used, not a check that passes either
way.

    python3 examples/tls_demo.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.protocols.tls.demo import run_handshake, oqsprovider_available, TLSDemoError


def main():
    if not oqsprovider_available():
        print("⚠️  oqs-provider not found -- build it first "
              "(see README's \"Building liboqs\" section).")
        return 1

    print("🔧 Starting a real TLS 1.3 handshake: classical ECDSA cert for "
          "auth, ML-KEM-768 for key exchange...")
    result = run_handshake(server_group="mlkem768")
    print(f"   connected: {result['connected']}")
    print(f"   protocol:  {result['protocol']}")
    print(f"   cipher:    {result['cipher']}")

    if not result["connected"]:
        print("\n❌ BUG: this should have succeeded")
        print(result["raw_output"])
        return 1

    print("\n🔍 Negative control: client offers a DIFFERENT group "
          "(mlkem1024) than the server (mlkem768)...")
    negative = run_handshake(server_group="mlkem768", client_group="mlkem1024")
    print(f"   connected: {negative['connected']} (expected: False)")
    print(f"   returncode: {negative['returncode']} (expected: nonzero)")

    if negative["connected"]:
        print("\n❌ BUG: mismatched groups should not have connected -- "
              "the positive result above would not be meaningful")
        return 1

    print("\n✅ Confirmed: the handshake only succeeds when the PQ group "
          "actually matches on both sides -- real evidence ML-KEM-768 "
          "was used, not a check that passes regardless.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
