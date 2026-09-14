#!/usr/bin/env python3
"""
Simple test to verify liboqs is working
"""
import ctypes
import os
import sys

# Set up the library path
lib_path = os.path.expanduser("~/.local/lib")
os.environ["LD_LIBRARY_PATH"] = f"{lib_path}:{os.environ.get('LD_LIBRARY_PATH', '')}"

try:
    # Try to load the liboqs library
    liboqs_path = os.path.join(lib_path, "liboqs.so")
    if not os.path.exists(liboqs_path):
        print(f"❌ Library not found at {liboqs_path}")
        sys.exit(1)
    
    lib = ctypes.CDLL(liboqs_path)
    print(f"✅ Successfully loaded liboqs from {liboqs_path}")
    
    # Check if we can call basic functions
    try:
        # Get version (if available)
        version_func = getattr(lib, 'OQS_version', None)
        if version_func:
            version_func.restype = ctypes.c_char_p
            version = version_func()
            print(f"✅ liboqs version: {version.decode() if version else 'unknown'}")
    except Exception as e:
        print(f"⚠️  Could not get version: {e}")
    
    # Check signature algorithms
    try:
        # Define function signatures
        lib.OQS_SIG_alg_count.restype = ctypes.c_size_t
        lib.OQS_SIG_alg_identifier.argtypes = [ctypes.c_size_t]
        lib.OQS_SIG_alg_identifier.restype = ctypes.c_char_p
        
        alg_count = lib.OQS_SIG_alg_count()
        print(f"✅ Available signature algorithms: {alg_count}")
        
        pq_algorithms = []
        for i in range(alg_count):
            alg_name = lib.OQS_SIG_alg_identifier(i)
            if alg_name:
                alg_str = alg_name.decode()
                if any(pq in alg_str.lower() for pq in ['dilithium', 'falcon', 'sphincs', 'ml-dsa', 'slh-dsa']):
                    pq_algorithms.append(alg_str)
        
        print(f"✅ Post-quantum signature algorithms found:")
        for alg in pq_algorithms[:10]:  # Show first 10
            print(f"   - {alg}")
        
        if len(pq_algorithms) > 10:
            print(f"   ... and {len(pq_algorithms) - 10} more")
            
    except Exception as e:
        print(f"❌ Error accessing signature algorithms: {e}")
    
    # Check KEM algorithms
    try:
        lib.OQS_KEM_alg_count.restype = ctypes.c_size_t
        lib.OQS_KEM_alg_identifier.argtypes = [ctypes.c_size_t]
        lib.OQS_KEM_alg_identifier.restype = ctypes.c_char_p
        
        kem_count = lib.OQS_KEM_alg_count()
        print(f"✅ Available KEM algorithms: {kem_count}")
        
        pq_kems = []
        for i in range(kem_count):
            alg_name = lib.OQS_KEM_alg_identifier(i)
            if alg_name:
                alg_str = alg_name.decode()
                if any(pq in alg_str.lower() for pq in ['kyber', 'ml-kem', 'ntru', 'saber', 'bike']):
                    pq_kems.append(alg_str)
        
        print(f"✅ Post-quantum KEM algorithms found:")
        for alg in pq_kems[:10]:  # Show first 10
            print(f"   - {alg}")
            
        if len(pq_kems) > 10:
            print(f"   ... and {len(pq_kems) - 10} more")
            
    except Exception as e:
        print(f"❌ Error accessing KEM algorithms: {e}")

except Exception as e:
    print(f"❌ Failed to load liboqs: {e}")
    sys.exit(1)

print("\n🎉 liboqs appears to be working correctly!")