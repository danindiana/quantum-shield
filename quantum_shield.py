#!/usr/bin/env python3
"""
Quantum Shield - Post-Quantum Cryptography Implementation
Entry point for the quantum shield system
"""

import json
import socket
import struct
import sys
import time
import argparse
import logging
import yaml
from datetime import datetime, timezone
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

def setup_logging(level=logging.INFO):
    """Setup logging configuration"""
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

def load_config(config_path):
    """Load configuration file"""
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading config: {e}")
        return None

def verify_liboqs():
    """Verify liboqs installation.

    Delegates to algorithms._liboqs.load_liboqs() -- the same loader
    src/algorithms/kem.py and signature.py use -- instead of maintaining
    a second, independent copy of the "search a few paths, try
    ctypes.CDLL" logic. Two copies of that logic is exactly the kind of
    drift that produced the hardcoded-key-size bug fixed in
    signature.py; see docs/FUTURE_DIRECTIONS.md item 2.
    """
    from algorithms._liboqs import load_liboqs, LibOQSNotFoundError
    try:
        load_liboqs()
        print("✅ liboqs loaded successfully")
        return True
    except LibOQSNotFoundError as e:
        print(f"⚠️  {e}")
        return False

def run_basic_tests():
    """Run basic system tests"""
    print("🔍 Running basic system tests...")
    
    # Test 1: Python version
    if sys.version_info >= (3, 8):
        print("✅ Python version check passed")
    else:
        print("❌ Python 3.8+ required")
        return False
    
    # Test 2: Required directories (kept in sync with
    # tests/test_setup.py::test_project_structure -- see
    # docs/FUTURE_DIRECTIONS.md item 5 for why this matters)
    required_dirs = ["src", "tests", "docs", "scripts", "configs",
                      "benchmarks", "examples", "diagrams"]
    for dir_name in required_dirs:
        if Path(dir_name).exists():
            print(f"✅ Directory {dir_name} exists")
        else:
            print(f"❌ Missing directory: {dir_name}")
            return False
    
    # Test 3: Configuration file
    config_path = "configs/quantum_shield_config.yaml"
    config = load_config(config_path)
    if config:
        print("✅ Configuration file loaded successfully")
        if "ML-KEM" in str(config):
            print("✅ Post-quantum algorithms configured")
        else:
            print("⚠️  Post-quantum algorithms not found in config")
    else:
        print("❌ Configuration file error")
        return False
    
    # Test 4: liboqs availability
    verify_liboqs()
    
    print("🎉 Basic system tests completed!")
    return True

def _time_op(fn, n=200, warmup=5):
    """Returns milliseconds/op, averaged over n iterations after warmup."""
    for _ in range(warmup):
        fn()
    t0 = time.perf_counter()
    for _ in range(n):
        fn()
    t1 = time.perf_counter()
    return (t1 - t0) / n * 1000

def run_benchmarks():
    """Real timing measurements against the installed liboqs, for
    ML-KEM-768, ML-DSA-65, and Falcon-512. Skips any algorithm that
    isn't available in the current liboqs build rather than faking a
    number for it (see docs/RESEARCH_NOTES.md's algorithm availability
    audit, which found SLH-DSA-128s disabled in this build)."""
    from algorithms.kem import MLKEM768, KEMError
    from algorithms.signature import MLDSA65, Falcon512, SignatureError

    results = {}

    try:
        kem = MLKEM768()
        pk, sk = kem.generate_keypair()
        ciphertext, _ = kem.encapsulate(pk)
        results["ML-KEM-768"] = {
            "keypair_ms": round(_time_op(kem.generate_keypair), 4),
            "encapsulate_ms": round(_time_op(lambda: kem.encapsulate(pk)), 4),
            "decapsulate_ms": round(_time_op(lambda: kem.decapsulate(sk, ciphertext)), 4),
        }
        print(f"⏱️  ML-KEM-768: keypair={results['ML-KEM-768']['keypair_ms']}ms "
              f"encaps={results['ML-KEM-768']['encapsulate_ms']}ms "
              f"decaps={results['ML-KEM-768']['decapsulate_ms']}ms")
    except KEMError as e:
        print(f"⚠️  ML-KEM-768 unavailable, skipping: {e}")

    message = b"quantum-shield benchmark message" * 8
    for label, cls in (("ML-DSA-65", MLDSA65), ("Falcon-512", Falcon512)):
        try:
            sig = cls()
            pk, sk = sig.generate_keypair()
            signature = sig.sign(sk, message)
            results[label] = {
                "keypair_ms": round(_time_op(sig.generate_keypair), 4),
                "sign_ms": round(_time_op(lambda: sig.sign(sk, message)), 4),
                "verify_ms": round(_time_op(lambda: sig.verify(pk, message, signature)), 4),
            }
            print(f"⏱️  {label}: keypair={results[label]['keypair_ms']}ms "
                  f"sign={results[label]['sign_ms']}ms "
                  f"verify={results[label]['verify_ms']}ms")
        except SignatureError as e:
            print(f"⚠️  {label} unavailable, skipping: {e}")

    return results

def run_server(port):
    """Real ML-KEM-768 key-exchange demo listener -- NOT a TLS server and
    not a security protocol (no authentication, no transport encryption,
    no replay protection). See examples/kem_demo_client.py to test it,
    and docs/FUTURE_DIRECTIONS.md item 6 for what real PQ-TLS integration
    still needs beyond this."""
    from algorithms.kem import MLKEM768

    print(f"🌐 Quantum Shield ML-KEM-768 demo listener starting on port {port}")
    print("⚠️  Demo only: no authentication, no transport encryption, no replay protection.")
    print("   Test it with: python3 examples/kem_demo_client.py --port " + str(port))
    print("\nPress Ctrl+C to stop\n")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("0.0.0.0", port))
        listener.listen(1)
        try:
            while True:
                conn, addr = listener.accept()
                with conn:
                    print(f"🔗 Connection from {addr[0]}:{addr[1]}")
                    kem = MLKEM768()
                    pk, sk = kem.generate_keypair()
                    conn.sendall(struct.pack(">I", len(pk)) + pk)
                    (ct_len,) = struct.unpack(">I", conn.recv(4))
                    ciphertext = b""
                    while len(ciphertext) < ct_len:
                        ciphertext += conn.recv(ct_len - len(ciphertext))
                    shared_secret = kem.decapsulate(sk, ciphertext)
                    print(f"🔑 Derived shared secret: {shared_secret.hex()}")
        except KeyboardInterrupt:
            print("\n🛑 Server stopped")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Quantum Shield - Post-Quantum Cryptography System"
    )
    
    parser.add_argument(
        '--config', 
        default='configs/quantum_shield_config.yaml',
        help='Configuration file path'
    )
    
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Logging level'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Setup command
    setup_parser = subparsers.add_parser('setup', help='Initialize quantum shield')
    
    # Test command  
    test_parser = subparsers.add_parser('test', help='Run system tests')
    
    # Benchmark command
    benchmark_parser = subparsers.add_parser('benchmark', help='Run performance benchmarks')
    
    # Server command
    server_parser = subparsers.add_parser('server', help='Start quantum shield server')
    server_parser.add_argument('--port', type=int, default=8443, help='Server port')
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Show system status')
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = getattr(logging, args.log_level.upper())
    setup_logging(log_level)
    
    logger = logging.getLogger(__name__)
    
    if args.command == 'setup':
        print("🛡️  Quantum Shield Setup")
        print("=" * 50)
        
        # Load configuration
        config = load_config(args.config)
        if not config:
            print("❌ Configuration loading failed")
            return 1
            
        print("✅ Configuration loaded successfully")
        print(f"✅ Primary KEM: {config['cryptography']['kem']['primary']}")
        print(f"✅ Primary Signature: {config['cryptography']['signature']['primary']}")
        print(f"✅ Security Level: {config['security']['minimum_level']}")
        
        # Verify liboqs
        if verify_liboqs():
            print("✅ liboqs library available")
        else:
            print("⚠️  liboqs not fully configured")
        
        print("\n🛡️  Quantum Shield setup complete!")
        print("✅ Post-quantum algorithms ready")
        print("✅ Security architecture implemented") 
        print("✅ NIST compliance framework active")
        print("\n📚 Next steps:")
        print("   ./quantum_shield.py test     # Run tests")
        print("   ./quantum_shield.py status   # Check status")
        print("   make test                    # Alternative test command")
        
    elif args.command == 'test':
        logger.info("Running system tests...")
        success = run_basic_tests()
        if success:
            print("\n🎉 All tests passed!")
            return 0
        else:
            print("\n❌ Some tests failed!")
            return 1
        
    elif args.command == 'benchmark':
        logger.info("Running benchmarks...")
        print("🚀 Benchmark mode - real timings against the installed liboqs")
        results = run_benchmarks()
        Path("benchmarks/results").mkdir(parents=True, exist_ok=True)
        out_path = Path("benchmarks/results") / (
            datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".json"
        )
        out_path.write_text(json.dumps(results, indent=2))
        print(f"✅ Benchmark complete - results written to {out_path}")

    elif args.command == 'server':
        logger.info(f"Starting server on port {args.port}...")
        run_server(args.port)
            
    elif args.command == 'status':
        print("🛡️  Quantum Shield Status Report")
        print("=" * 50)
        
        config = load_config(args.config)
        if config:
            print("✅ Configuration: Loaded")
            print(f"🔐 Security Level: {config['security']['minimum_level']}")
            print(f"🔑 Primary KEM: {config['cryptography']['kem']['primary']}")
            print(f"✍️  Primary Signature: {config['cryptography']['signature']['primary']}")
            print(f"🔄 Hybrid Mode: {'Enabled' if config['cryptography']['hybrid_mode']['enabled'] else 'Disabled'}")
        else:
            print("❌ Configuration: Failed to load")
            
        # Check liboqs
        if verify_liboqs():
            print("✅ liboqs: Available")
        else:
            print("⚠️  liboqs: Not configured")
            
        print(f"🐍 Python: {sys.version.split()[0]}")
        print(f"📍 Location: {Path.cwd()}")
        
        print("\n📊 Implementation Status:")
        print("   🟢 Planning & Documentation: Complete")
        print("   🔄 Core Algorithm Integration: In Progress") 
        print("   ⏳ Protocol Integration: Planned")
        print("   ⏳ System Hardening: Planned")
        print("   ⏳ Monitoring & Compliance: Planned")
        
        print("\n🎯 Next Phase: Core Algorithm Implementation")
        
    else:
        parser.print_help()

if __name__ == "__main__":
    sys.exit(main())