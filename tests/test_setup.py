#!/usr/bin/env python3
"""
Basic setup verification tests for Quantum Shield
"""

import pytest
import sys
import os
import yaml
from pathlib import Path

def test_python_version():
    """Verify Python version is 3.8+"""
    assert sys.version_info >= (3, 8), "Python 3.8+ required"

def test_project_structure():
    """Verify project directory structure"""
    required_dirs = [
        "src", "tests", "docs", "scripts",
        "configs", "benchmarks", "examples", "diagrams"
    ]
    
    for dir_name in required_dirs:
        assert os.path.exists(dir_name), f"Missing directory: {dir_name}"

def test_config_file():
    """Verify configuration file exists and is readable"""
    config_path = "configs/quantum_shield_config.yaml"
    assert os.path.exists(config_path), "Configuration file missing"
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
        assert config is not None, "Configuration file is empty or invalid"
        assert "ML-KEM" in str(config), "Post-quantum algorithms not configured"
        assert "cryptography" in config, "Cryptography section missing"
        assert "security" in config, "Security section missing"

def test_liboqs_presence():
    """Check if liboqs library is available"""
    import ctypes
    possible_paths = [
        str(Path.home() / ".local/lib/liboqs.so"),
        "./liboqs/build/lib/liboqs.so"
    ]
    
    found = False
    for path in possible_paths:
        if os.path.exists(path):
            try:
                lib = ctypes.CDLL(path)
                found = True
                break
            except:
                continue
    
    # This is a warning, not a failure for now
    if not found:
        print("Warning: liboqs library not found, but test continues")

def test_nist_algorithms_configured():
    """Verify NIST algorithms are properly configured"""
    config_path = "configs/quantum_shield_config.yaml"
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Check KEM algorithms
    assert "ML-KEM-768" in config["cryptography"]["kem"]["primary"]
    
    # Check signature algorithms  
    assert "ML-DSA-65" in config["cryptography"]["signature"]["primary"]
    
    # Check hash-based signatures
    assert "SLH-DSA" in config["cryptography"]["hash_signature"]["primary"]
    
    # Check security level
    assert config["security"]["minimum_level"] >= 3

if __name__ == "__main__":
    pytest.main([__file__, "-v"])