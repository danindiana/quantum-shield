#!/usr/bin/env python3
"""
Demo of src/kms/store.py: generate a real ML-DSA-65 keypair, store it
encrypted at rest under a passphrase, then load it back and prove the
round trip worked -- all against a temporary keystore directory so this
script is safe to run repeatedly without touching anything persistent.

    python3 examples/kms_demo.py

This is a usage example, not a CLI tool for managing real keys -- there's
no prompt-based passphrase entry here (see getpass in the standard
library if you build that). Notably, simple_ssh_keygen.py does NOT use
this store yet; it still writes raw key bytes to ~/.ssh/ -- see
docs/FUTURE_DIRECTIONS.md for that integration as a next step.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.algorithms.signature import MLDSA65
from src.kms.store import KeyStore, WrongPassphraseError


def main():
    sig = MLDSA65()
    public_key, secret_key = sig.generate_keypair()
    print(f"Generated a real ML-DSA-65 keypair "
          f"({len(public_key)}-byte public key, {len(secret_key)}-byte secret key)")

    with tempfile.TemporaryDirectory() as tmpdir:
        store = KeyStore(base_dir=tmpdir)
        passphrase = "correct horse battery staple"

        path = store.save_keypair(
            "demo-signing-key", "ML-DSA-65", "signature",
            public_key, secret_key, passphrase,
        )
        print(f"Saved, encrypted at rest, to {path}")

        on_disk = path.read_text()
        assert secret_key.hex() not in on_disk
        print("Confirmed: the raw secret key does not appear anywhere in the file")

        loaded = store.load_keypair("demo-signing-key", passphrase)
        assert loaded["secret_key"] == secret_key
        print("Loaded it back with the correct passphrase -- secret key matches")

        try:
            store.load_keypair("demo-signing-key", "wrong passphrase")
            print("BUG: wrong passphrase should have raised an error")
            return 1
        except WrongPassphraseError:
            print("Confirmed: a wrong passphrase is correctly rejected")

    print("\nAll good -- see src/kms/store.py for the KeyStore API.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
