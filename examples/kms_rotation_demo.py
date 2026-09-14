#!/usr/bin/env python3
"""
Demo of src/kms/store.py's rotate_key() and revoke_key(): generate a
keypair, store it, rotate it to a new keypair (archiving the old one),
inspect the full generation history, then revoke the active key and
show that a normal load is refused afterwards.

    python3 examples/kms_rotation_demo.py

Safe to run repeatedly -- uses a temporary keystore directory.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.algorithms.kem import MLKEM768
from src.kms.store import KeyStore, KeyStoreError


def main():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = KeyStore(base_dir=tmpdir)
        kem = MLKEM768()

        pk1, sk1 = kem.generate_keypair()
        store.save_keypair("service-kex-key", "ML-KEM-768", "kem", pk1, sk1, "gen1 pw")
        print("Saved generation 1")

        pk2, sk2 = kem.generate_keypair()
        archive_path, active_path = store.rotate_key("service-kex-key", pk2, sk2, "gen2 pw")
        print(f"Rotated: generation 1 archived to {archive_path.name}, "
              f"generation 2 now active at {active_path.name}")

        print("\nFull history:")
        for entry in store.list_history("service-kex-key"):
            print(f"  generation {entry['generation']}: status={entry['status']}")

        active = store.load_keypair("service-kex-key", "gen2 pw")
        assert active["secret_key"] == sk2
        print(f"\nActive key confirmed at generation {active['generation']}")

        try:
            store.load_keypair("service-kex-key", "gen1 pw")
            print("BUG: the old passphrase should not open the current active slot")
            return 1
        except Exception:
            print("Confirmed: the old (generation 1) passphrase no longer opens the active slot")

        store.revoke_key("service-kex-key", reason="demo: rotating off this key entirely")
        try:
            store.load_keypair("service-kex-key", "gen2 pw")
            print("BUG: a revoked key should not load without allow_revoked=True")
            return 1
        except KeyStoreError as e:
            print(f"Confirmed: revoked key refuses a normal load ({e})")

        revoked = store.load_keypair("service-kex-key", "gen2 pw", allow_revoked=True)
        print(f"With allow_revoked=True: status={revoked['status']}, key material still accessible")

    print("\nAll good -- see src/kms/store.py for the full rotate_key()/revoke_key()/list_history() API.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
