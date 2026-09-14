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
import base64
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from src.algorithms.signature import Signature, SignatureError

def generate_ssh_keys(algorithm, key_name, ssh_dir):
    """Generate SSH keys using liboqs"""
    print(f"🔑 Generating {algorithm} keypair...")

    try:
        sig = Signature(algorithm)
        public_key_raw, private_key_raw = sig.generate_keypair()

        # Create SSH key format
        private_key_path = Path(ssh_dir) / f"id_{key_name}"
        public_key_path = Path(ssh_dir) / f"id_{key_name}.pub"
        
        # Write private key in OpenSSH format (simplified)
        with open(private_key_path, 'w') as f:
            f.write("-----BEGIN OPENSSH PRIVATE KEY-----\n")
            encoded_private = base64.b64encode(private_key_raw).decode()
            # Split into 64-character lines
            for i in range(0, len(encoded_private), 64):
                f.write(encoded_private[i:i+64] + "\n")
            f.write("-----END OPENSSH PRIVATE KEY-----\n")
        
        # Write public key in SSH format
        with open(public_key_path, 'w') as f:
            encoded_public = base64.b64encode(public_key_raw).decode()
            hostname = subprocess.run(['hostname'], capture_output=True, text=True).stdout.strip()
            username = os.getenv('USER', 'user')
            f.write(f"ssh-{algorithm.lower().replace('-', '')} {encoded_public} {username}@{hostname}\n")
        
        # Set proper permissions
        os.chmod(private_key_path, 0o600)
        os.chmod(public_key_path, 0o644)
        
        print(f"✅ Generated keys:")
        print(f"   Private: {private_key_path}")
        print(f"   Public:  {public_key_path}")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to generate {algorithm} keys: {e}")
        return False

def main():
    print("🛡️  Quantum Shield SSH Key Generator")
    print("=====================================")
    
    ssh_dir = Path.home() / ".ssh"
    ssh_dir.mkdir(exist_ok=True, mode=0o700)
    
    algorithms = [
        ("ML-DSA-65", "ml_dsa_65"),
        ("Falcon-512", "falcon_512"),
    ]
    
    print(f"\n📂 SSH directory: {ssh_dir}")
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
        
        print(f"\n🔒 Generating post-quantum SSH keys...")
        success_count = 0
        
        for alg_name, key_name in selected_algorithms:
            if generate_ssh_keys(alg_name, key_name, ssh_dir):
                success_count += 1
        
        print(f"\n🎉 Successfully generated {success_count}/{len(selected_algorithms)} keypairs!")
        
        if success_count > 0:
            print("\n📋 Next steps:")
            print("1. Copy public key to server:")
            for _, key_name in selected_algorithms[:success_count]:
                print(f"   ssh-copy-id -i ~/.ssh/id_{key_name}.pub user@server")
            
            print("2. Test connection:")
            for _, key_name in selected_algorithms[:success_count]:
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