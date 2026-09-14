# TLS/HTTPS Post-Quantum Cryptography Research

**Date:** October 12, 2025  
**Project:** Quantum Shield Phase 3  
**Objective:** Implement PQ-resistant TLS/HTTPS  

---

## Current System Assessment

### Infrastructure Status:
- **OpenSSL Version:** 3.0.2 (March 2022)
- **Web Servers:** None installed (nginx/apache)
- **Running Services:** Open-WebUI on port 8080 (HTTP)
- **liboqs Status:** Built locally in project (v0.14.1-dev)
  - Located: `~/programs/quantum-shield/liboqs/build/lib/`
  - 221 signature algorithms
  - 35 KEM algorithms

### Key Findings:
✅ liboqs is available and functional  
❌ No system-wide liboqs installation  
❌ No PQ-enabled OpenSSL (using vanilla 3.0.2)  
❌ No web servers to configure yet  

---

## Implementation Options

### Option 1: OQS-OpenSSL Provider (RECOMMENDED) ⭐

**What:** OpenSSL 3.x provider that adds PQ algorithms via liboqs  
**Repository:** https://github.com/open-quantum-safe/oqs-provider  
**Advantages:**
- Works with existing OpenSSL 3.x (we have 3.0.2)
- No need to replace system OpenSSL
- Provides PQ algorithms as OpenSSL provider
- Supports hybrid classical+PQ modes
- Actively maintained by Open Quantum Safe project

**Requirements:**
- OpenSSL 3.0+ ✅ (we have 3.0.2)
- liboqs built and installed ✅ (we have it)
- CMake for building

**Integration Path:**
```bash
# 1. Install liboqs system-wide
cd ~/programs/quantum-shield/liboqs/build
sudo make install
sudo ldconfig

# 2. Clone and build oqs-provider
git clone https://github.com/open-quantum-safe/oqs-provider.git
cd oqs-provider
cmake -S . -B build
cmake --build build
sudo cmake --install build

# 3. Configure OpenSSL to use provider
# Add to /etc/ssl/openssl.cnf
```

### Option 2: OQS-OpenSSL Fork

**What:** Complete OpenSSL fork with PQ algorithms built-in  
**Repository:** https://github.com/open-quantum-safe/openssl  
**Advantages:**
- Deeper integration
- Well-tested PQ support
- Complete replacement

**Disadvantages:**
- Requires replacing system OpenSSL (risky!)
- More complex maintenance
- May conflict with package manager
- ❌ NOT RECOMMENDED for production systems

### Option 3: BoringSSL with PQ

**What:** Google's BoringSSL fork with experimental PQ support  
**Status:** Experimental, not production-ready  
**Verdict:** ❌ Skip for now

### Option 4: Python-based TLS with liboqs

**What:** Pure Python implementation using ctypes/cffi to call liboqs  
**Advantages:**
- Full control
- Easy to prototype
- Good for testing

**Disadvantages:**
- Not suitable for high-performance production
- Missing many TLS features
- Would need to implement TLS 1.3 handshake

**Use Case:** Testing and demonstration only

---

## Recommended Approach: OQS-Provider

### Architecture:

```
┌─────────────────────────────────────────┐
│         Application Layer               │
│  (nginx, python, node.js, etc.)        │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│         OpenSSL 3.0.2                   │
│    (System-provided, unmodified)        │
└─────────────────┬───────────────────────┘
                  │
                  ├──► Classical Crypto (built-in)
                  │    RSA, ECDSA, AES, etc.
                  │
                  └──► OQS Provider (plugin)
                       ├─► ML-KEM (Kyber)
                       ├─► ML-DSA (Dilithium)
                       ├─► Falcon
                       ├─► SPHINCS+
                       └─► Hybrid modes
┌──────────────────────────────────────────┐
│           liboqs library                 │
│  (PQ algorithm implementations)          │
└──────────────────────────────────────────┘
```

### Supported PQ Algorithms (via OQS-Provider):

**Key Exchange (KEM):**
- ML-KEM-512, ML-KEM-768, ML-KEM-1024 (NIST FIPS 203)
- Kyber512, Kyber768, Kyber1024
- Hybrid: X25519+Kyber768, P-256+Kyber768

**Signatures:**
- ML-DSA-44, ML-DSA-65, ML-DSA-87 (NIST FIPS 204)
- Falcon-512, Falcon-1024
- SPHINCS+-SHA2-128s, SPHINCS+-SHA2-256s
- Hybrid: RSA+ML-DSA, ECDSA+ML-DSA

### Cipher Suites:

Modern TLS 1.3 with PQ:
```
TLS_MLKEM768_ECDHE_WITH_AES_256_GCM_SHA384
TLS_KYBER768_X25519_WITH_CHACHA20_POLY1305_SHA256
TLS_KYBER1024_WITH_AES_256_GCM_SHA384
```

Hybrid approach (recommended):
```
TLS_X25519_KYBER768_WITH_AES_256_GCM_SHA384
TLS_ECDHE_RSA_WITH_KYBER768_AES_256_GCM
```

---

## Implementation Plan

### Phase 3.1: Foundation (Week 1)
1. ✅ Research PQ-TLS options
2. ⏳ Install liboqs system-wide
3. ⏳ Build and install oqs-provider
4. ⏳ Verify PQ algorithms available in OpenSSL
5. ⏳ Test basic certificate generation

### Phase 3.2: Web Server Setup (Week 2)
1. Install nginx or apache
2. Generate PQ certificates
3. Configure web server with PQ cipher suites
4. Set up test HTTPS endpoint

### Phase 3.3: Integration (Week 3)
1. Migrate Open-WebUI to HTTPS with PQ
2. Create Python TLS wrapper library
3. Implement hybrid classical+PQ mode
4. Performance benchmarking

### Phase 3.4: Production (Week 4)
1. Security testing
2. Documentation
3. Deployment scripts
4. Monitoring tools

---

## Certificate Strategy

### Approach: Hybrid Certificates

**Why Hybrid?**
- Backward compatibility with non-PQ clients
- Defense in depth (both classical and PQ security)
- Smooth migration path

**Certificate Chain:**
```
Root CA (RSA 4096 + ML-DSA-87)
  └─► Intermediate CA (ECDSA P-384 + ML-DSA-65)
      └─► Server Cert (ECDSA P-256 + ML-DSA-65)
          └─► Signature over public key uses both algorithms
```

### Certificate Generation Tools:

Using oqs-provider with OpenSSL:
```bash
# Generate hybrid private key
openssl genpkey -algorithm mldsa65 -out server-pq.key

# Generate classical key
openssl ecparam -genkey -name prime256v1 -out server-ec.key

# Create hybrid CSR
openssl req -new -key server-pq.key -key2 server-ec.key \
  -out server-hybrid.csr

# Self-sign (for testing)
openssl x509 -req -in server-hybrid.csr -signkey server-pq.key \
  -out server-hybrid.crt -days 365
```

---

## Performance Considerations

### Expected Overhead:

| Operation | Classical | PQ (ML-KEM) | Overhead |
|-----------|-----------|-------------|----------|
| Key Generation | 1ms | 5-10ms | 5-10x |
| Handshake | 2-5ms | 8-15ms | 2-3x |
| Certificate Verify | 0.5ms | 2-5ms | 4-10x |
| Data Encryption | 100MB/s | 95MB/s | 5% |

**Mitigation Strategies:**
- Session resumption (TLS session tickets)
- Connection pooling
- Hardware acceleration (if available)
- Caching of expensive operations

### Bandwidth Impact:

- **Classical cert:** ~2KB
- **PQ cert (ML-DSA-65):** ~5-7KB
- **Hybrid cert:** ~7-9KB
- **Extra overhead:** ~5KB per connection

For modern networks: Negligible impact

---

## Security Considerations

### Threat Model:

**Protected Against:**
✅ Future quantum computer attacks on recorded traffic  
✅ "Harvest now, decrypt later" attacks  
✅ Cryptanalytic quantum algorithms (Shor's, Grover's)  

**Not Protected Against:**
❌ Side-channel attacks (need separate mitigation)  
❌ Implementation bugs (requires auditing)  
❌ Compromised endpoints (need endpoint security)  

### Recommended Security Levels:

| Use Case | KEM | Signature | Security Level |
|----------|-----|-----------|----------------|
| Testing | Kyber512 | Falcon-512 | NIST Level 1 |
| **Production** | **ML-KEM-768** | **ML-DSA-65** | **NIST Level 3** ⭐ |
| High Security | ML-KEM-1024 | ML-DSA-87 | NIST Level 5 |

**Recommendation: NIST Level 3 (ML-KEM-768 + ML-DSA-65)**
- Best balance of security and performance
- Matches SSH implementation
- NIST recommended for most applications

---

## Testing Strategy

### Test Levels:

1. **Unit Tests:**
   - Algorithm availability
   - Key generation
   - Certificate creation
   - Signature verification

2. **Integration Tests:**
   - TLS handshake completion
   - Hybrid mode fallback
   - Client compatibility
   - Session resumption

3. **Performance Tests:**
   - Handshake latency
   - Throughput measurements
   - Connection rate limits
   - Memory usage

4. **Security Tests:**
   - Protocol downgrade attacks
   - Certificate validation
   - Cipher suite negotiation
   - Man-in-the-middle detection

### Test Tools:

```bash
# OpenSSL s_client (PQ-aware)
openssl s_client -connect localhost:8443 -curves kyber768

# Custom test script
python3 test_pq_tls.py --algorithm mlkem768 --hybrid

# Load testing
wrk -t4 -c100 -d30s https://localhost:8443/
```

---

## Next Steps

### Immediate Actions:

1. ✅ Complete this research document
2. ⏳ Install liboqs system-wide
3. ⏳ Clone and build oqs-provider
4. ⏳ Test OpenSSL PQ algorithm availability
5. ⏳ Generate first PQ certificate

### This Week:

- [ ] Get oqs-provider working with OpenSSL
- [ ] Install nginx
- [ ] Create test HTTPS endpoint
- [ ] Generate hybrid certificates
- [ ] Document configuration

### This Month:

- [ ] Migrate Open-WebUI to PQ-HTTPS
- [ ] Create Python TLS library
- [ ] Full integration testing
- [ ] Production deployment

---

## References

- **OQS-Provider:** https://github.com/open-quantum-safe/oqs-provider
- **liboqs:** https://github.com/open-quantum-safe/liboqs
- **NIST PQC:** https://csrc.nist.gov/projects/post-quantum-cryptography
- **RFC 8446:** TLS 1.3 Specification
- **Hybrid TLS Draft:** https://datatracker.ietf.org/doc/draft-ietf-tls-hybrid-design/

---

**Status:** Research Complete ✅  
**Next:** Install oqs-provider  
**Updated:** October 12, 2025
