#!/usr/bin/env python3
"""
Quantum Shield SSH Key Generator using liboqs

Key generation itself is delegated to src/algorithms/signature.py, which
reads real key sizes from liboqs's OQS_SIG struct at runtime instead of
hardcoding them -- this script used to hardcode them here directly, and
one of those hardcoded values (ML-DSA-65's secret key length) was simply
wrong (4864 vs. the actual 4032), silently zero-padding every generated
key. See signature.py's module docstring.
"""
import os
import sys
import argparse
import getpass
import base64
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from src.algorithms.signature import Signature, SignatureError
from src.kms.store import KeyStore, KeyStoreError

def _prompt_passphrase():
    """Prompts twice (no echo) and requires the two entries to match --
    same convention ssh-keygen itself uses."""
    while True:
        p1 = getpass.getpass("Enter passphrase to encrypt the private key: ")
        p2 = getpass.getpass("Confirm passphrase: ")
        if p1 != p2:
            print("❌ Passphrases didn't match, try again.")
            continue
        if not p1:
            print("❌ Passphrase can't be empty.")
            continue
        return p1

def generate_ssh_keys(algorithm, key_name, ssh_dir, encrypt=False, passphrase=None):
    """Generate SSH keys using liboqs.

    encrypt=False (default, unchanged from before): writes the raw
    private key bytes to ssh_dir, same as always.

    encrypt=True: does NOT write a plaintext private key file at all.
    Instead stores the private key encrypted at rest via
    src/kms/store.py's KeyStore, under the passphrase provided (prompted
    interactively if not passed in). Only the public key -- which isn't
    secret -- still gets written to ssh_dir as a plain file. This closes
    the gap noted in docs/FUTURE_DIRECTIONS.md: previously this script
    had no way to avoid writing raw secret key bytes to disk.
    """
    print(f"🔑 Generating {algorithm} keypair...")

    try:
        sig = Signature(algorithm)
        public_key_raw, private_key_raw = sig.generate_keypair()

        public_key_path = Path(ssh_dir) / f"id_{key_name}.pub"

        # Write public key in SSH format -- always plaintext, it isn't secret
        with open(public_key_path, 'w') as f:
            encoded_public = base64.b64encode(public_key_raw).decode()
            hostname = subprocess.run(['hostname'], capture_output=True, text=True).stdout.strip()
            username = os.getenv('USER', 'user')
            f.write(f"ssh-{algorithm.lower().replace('-', '')} {encoded_public} {username}@{hostname}\n")
        os.chmod(public_key_path, 0o644)

        if encrypt:
            if passphrase is None:
                passphrase = _prompt_passphrase()
            store = KeyStore()
            store_path = store.save_keypair(
                key_name, algorithm, "signature",
                public_key_raw, private_key_raw, passphrase,
            )
            print(f"✅ Generated keys:")
            print(f"   Public:            {public_key_path}")
            print(f"   Private (encrypted): {store_path}")
            print(f"   Load it back with: KeyStore().load_keypair({key_name!r}, <passphrase>)")
        else:
            private_key_path = Path(ssh_dir) / f"id_{key_name}"
            with open(private_key_path, 'w') as f:
                f.write("-----BEGIN OPENSSH PRIVATE KEY-----\n")
                encoded_private = base64.b64encode(private_key_raw).decode()
                for i in range(0, len(encoded_private), 64):
                    f.write(encoded_private[i:i+64] + "\n")
                f.write("-----END OPENSSH PRIVATE KEY-----\n")
            os.chmod(private_key_path, 0o600)

            print(f"✅ Generated keys:")
            print(f"   Private: {private_key_path}  (plaintext -- use --encrypt to avoid this)")
            print(f"   Public:  {public_key_path}")

        return True

    except Exception as e:
        print(f"❌ Failed to generate {algorithm} keys: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Quantum Shield SSH Key Generator")
    parser.add_argument(
        '--encrypt', action='store_true',
        help="Store the private key encrypted at rest via src/kms/store.py "
             "instead of writing it as a plaintext file to ~/.ssh/",
    )
    args = parser.parse_args()

    print("🛡️  Quantum Shield SSH Key Generator")
    print("=====================================")

    ssh_dir = Path.home() / ".ssh"
    ssh_dir.mkdir(exist_ok=True, mode=0o700)

    algorithms = [
        ("ML-DSA-65", "ml_dsa_65"),
        ("Falcon-512", "falcon_512"),
    ]

    print(f"\n📂 SSH directory: {ssh_dir}")
    if args.encrypt:
        print("🔐 --encrypt: private keys will be stored encrypted, not written as plaintext files")
    print("\nAvailable algorithms:")
    for i, (alg, _) in enumerate(algorithms, 1):
        print(f"  {i}) {alg}")

    try:
        choice = input("\nSelect algorithm (1-2) or 'all': ").strip()

        if choice.lower() == 'all':
            selected_algorithms = algorithms
        else:
            idx = int(choice) - 1
            if 0 <= idx < len(algorithms):
                selected_algorithms = [algorithms[idx]]
            else:
                print("❌ Invalid choice")
                return 1

        # Prompt once up front (not per-algorithm) so generating multiple
        # keys with 'all' doesn't ask for the passphrase repeatedly. Each
        # key still gets its own independent salt/nonce in KeyStore.
        passphrase = _prompt_passphrase() if args.encrypt else None

        print(f"\n🔒 Generating post-quantum SSH keys...")
        success_count = 0
        successes = []

        for alg_name, key_name in selected_algorithms:
            if generate_ssh_keys(alg_name, key_name, ssh_dir, encrypt=args.encrypt, passphrase=passphrase):
                success_count += 1
                successes.append((alg_name, key_name))

        print(f"\n🎉 Successfully generated {success_count}/{len(selected_algorithms)} keypairs!")

        if success_count > 0:
            print("\n📋 Next steps:")
            if args.encrypt:
                print("Private keys are encrypted at rest. Decrypt with:")
                for _, key_name in successes:
                    print(f"   KeyStore().load_keypair({key_name!r}, <your passphrase>)")
                print("\n(Public keys were still written as plaintext to ~/.ssh/ -- they")
                print(" aren't secret. Note: these are demo/toy SSH keys, not directly")
                print(" usable by a real ssh client -- see the README's disclaimer.)")
            else:
                print("1. Copy public key to server:")
                for _, key_name in successes:
                    print(f"   ssh-copy-id -i ~/.ssh/id_{key_name}.pub user@server")

                print("2. Test connection:")
                for _, key_name in successes:
                    print(f"   ssh -i ~/.ssh/id_{key_name} user@server")

        return 0 if success_count > 0 else 1

    except KeyboardInterrupt:
        print("\n\n❌ Operation cancelled by user")
        return 1
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())