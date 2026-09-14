# SSH Post-Quantum Security Implementation Guide

## Executive Summary

This document provides comprehensive guidance for implementing post-quantum cryptographic algorithms in SSH infrastructure, following NIST standards and security best practices. The implementation ensures protection against both classical and quantum computing attacks.

## Table of Contents
1. [Current SSH Vulnerability](#current-ssh-vulnerability)
2. [Post-Quantum SSH Architecture](#post-quantum-ssh-architecture) 
3. [Implementation Strategy](#implementation-strategy)
4. [Key Generation Procedures](#key-generation-procedures)
5. [Server Configuration](#server-configuration)
6. [Client Configuration](#client-configuration)
7. [Migration Planning](#migration-planning)
8. [Security Monitoring](#security-monitoring)
9. [Troubleshooting Guide](#troubleshooting-guide)

## Current SSH Vulnerability

### Classical Cryptography Risks
```
Current SSH Algorithms (VULNERABLE to Quantum Attacks):
├── Host Key Algorithms:
│   ├── RSA-2048/4096      ❌ Vulnerable to Shor's algorithm
│   ├── ECDSA (P-256/384)  ❌ Vulnerable to Shor's algorithm  
│   └── Ed25519           ❌ Vulnerable to Shor's algorithm
├── Key Exchange:
│   ├── ECDH              ❌ Vulnerable to Shor's algorithm
│   └── DH                ❌ Vulnerable to Shor's algorithm
└── Ciphers:
    ├── AES-256           ✅ Quantum-resistant (128-bit security)
    └── ChaCha20          ✅ Quantum-resistant (128-bit security)
```

### Quantum Computing Timeline
- **Conservative Estimate**: 10-15 years to cryptographically relevant quantum computer
- **Aggressive Preparation**: Begin migration immediately
- **Critical Infrastructure**: Should prioritize post-quantum SSH now

## Post-Quantum SSH Architecture

### NIST-Approved PQ Algorithms for SSH
```
Post-Quantum SSH Stack:
├── Host Authentication:
│   ├── ML-DSA-65 (Dilithium3)     🛡️ NIST FIPS 204
│   └── SLH-DSA-128s (SPHINCS+)    🛡️ NIST FIPS 205 (backup)
├── Key Exchange:
│   ├── ML-KEM-768 (Kyber768)      🛡️ NIST FIPS 203
│   └── Hybrid: X25519+ML-KEM-768  🛡️ Transition approach
└── Symmetric Encryption:
    ├── AES-256-GCM               ✅ Already quantum-resistant
    └── ChaCha20-Poly1305         ✅ Already quantum-resistant
```

### Security Levels Mapping
| NIST Level | Classical Equivalent | SSH Use Case | Recommended Algorithm |
|------------|---------------------|--------------|----------------------|
| 1 | RSA-2048 / AES-128 | Development/Testing | ML-DSA-44 |
| 3 | RSA-3072 / AES-192 | **Production Recommended** | ML-DSA-65 |
| 5 | RSA-15360 / AES-256 | High Security | ML-DSA-87 |

## Implementation Strategy

### Phase 1: Hybrid Deployment (Weeks 1-4)
**Approach**: Run classical and post-quantum algorithms simultaneously
```bash
# Server supports both classical and PQ
PubkeyAcceptedKeyTypes ssh-rsa,ssh-ed25519,ssh-ml-dsa-65
HostKeyAlgorithms ssh-rsa,ssh-ed25519,ssh-ml-dsa-65

# Key exchange supports hybrid mode
KexAlgorithms curve25519-sha256,ml-kem-768,hybrid-x25519-ml-kem-768
```

### Phase 2: PQ-Preferred (Weeks 5-8)
**Approach**: Prioritize post-quantum with classical fallback
```bash
# Prefer PQ algorithms first
PubkeyAcceptedKeyTypes ssh-ml-dsa-65,ssh-slh-dsa-128s,ssh-ed25519
HostKeyAlgorithms ssh-ml-dsa-65,ssh-slh-dsa-128s,ssh-ed25519

# PQ-first key exchange
KexAlgorithms ml-kem-768,hybrid-x25519-ml-kem-768,curve25519-sha256
```

### Phase 3: PQ-Only (Weeks 9-12)
**Approach**: Post-quantum algorithms only
```bash
# Post-quantum only
PubkeyAcceptedKeyTypes ssh-ml-dsa-65,ssh-slh-dsa-128s
HostKeyAlgorithms ssh-ml-dsa-65,ssh-slh-dsa-128s
KexAlgorithms ml-kem-768

# Disable classical algorithms
PubkeyAcceptedKeyTypes -ssh-rsa,-ssh-dss,-ecdsa-sha2-*,-ssh-ed25519
```

## Key Generation Procedures

### Host Key Generation

#### ML-DSA Host Keys (Primary)
```bash
#!/bin/bash
# Generate post-quantum SSH host keys

# ML-DSA-65 (Dilithium3) - Primary host key
ssh-keygen -t ml-dsa-65 -f /etc/ssh/ssh_host_ml_dsa_65_key -N "" \
  -C "$(hostname)-ml-dsa-65-$(date +%Y%m%d)"

# SLH-DSA-128s (SPHINCS+) - Backup host key  
ssh-keygen -t slh-dsa-128s -f /etc/ssh/ssh_host_slh_dsa_128s_key -N "" \
  -C "$(hostname)-slh-dsa-128s-$(date +%Y%m%d)"

# Set proper permissions
chmod 600 /etc/ssh/ssh_host_*_key
chmod 644 /etc/ssh/ssh_host_*_key.pub
chown root:root /etc/ssh/ssh_host_*_key*

# Backup existing classical keys (DO NOT DELETE until migration complete)
mkdir -p /etc/ssh/classical_backup
cp /etc/ssh/ssh_host_*rsa* /etc/ssh/classical_backup/ 2>/dev/null || true
cp /etc/ssh/ssh_host_*ed25519* /etc/ssh/classical_backup/ 2>/dev/null || true
```

### User Key Generation

#### ML-DSA User Keys
```bash
#!/bin/bash
# Generate post-quantum SSH user keys

# Primary user key - ML-DSA-65
ssh-keygen -t ml-dsa-65 -f ~/.ssh/id_ml_dsa_65 -N "" \
  -C "$(whoami)@$(hostname)-ml-dsa-65-$(date +%Y%m%d)"

# Backup user key - SLH-DSA-128s (for high-security environments)  
ssh-keygen -t slh-dsa-128s -f ~/.ssh/id_slh_dsa_128s -N "" \
  -C "$(whoami)@$(hostname)-slh-dsa-128s-$(date +%Y%m%d)"

# Set proper permissions
chmod 600 ~/.ssh/id_*
chmod 644 ~/.ssh/id_*.pub

echo "✅ Post-quantum SSH keys generated:"
echo "   Primary: ~/.ssh/id_ml_dsa_65"
echo "   Backup:  ~/.ssh/id_slh_dsa_128s"
echo ""
echo "📋 Add public key to authorized_keys:"
echo "   cat ~/.ssh/id_ml_dsa_65.pub >> ~/.ssh/authorized_keys"
```

## Server Configuration

### OpenSSH Server Configuration (sshd_config)

#### Production Configuration Template
```bash
# /etc/ssh/sshd_config - Post-Quantum SSH Configuration
# Quantum Shield SSH Security - NIST Compliant

# Protocol and Port Configuration
Protocol 2
Port 22
AddressFamily any

# Host Key Configuration (Post-Quantum + Hybrid)
HostKey /etc/ssh/ssh_host_ml_dsa_65_key
HostKey /etc/ssh/ssh_host_slh_dsa_128s_key
HostKey /etc/ssh/ssh_host_ed25519_key  # Keep during transition

# Algorithm Selection (PQ-Preferred)
HostKeyAlgorithms ssh-ml-dsa-65,ssh-slh-dsa-128s,ssh-ed25519,rsa-sha2-512
PubkeyAcceptedKeyTypes ssh-ml-dsa-65,ssh-slh-dsa-128s,ssh-ed25519,rsa-sha2-512

# Key Exchange (Post-Quantum)
KexAlgorithms ml-kem-768,hybrid-x25519-ml-kem-768,curve25519-sha256@libssh.org

# Symmetric Ciphers (Already Quantum-Resistant)
Ciphers aes256-gcm@openssh.com,chacha20-poly1305@openssh.com,aes256-ctr

# MAC Algorithms (Already Quantum-Resistant)
MACs hmac-sha2-256-etm@openssh.com,hmac-sha2-512-etm@openssh.com

# Authentication Configuration  
PubkeyAuthentication yes
AuthorizedKeysFile .ssh/authorized_keys .ssh/authorized_keys2
PasswordAuthentication no  # Force key-based auth
PermitEmptyPasswords no
ChallengeResponseAuthentication no

# Security Hardening
PermitRootLogin no
MaxAuthTries 3
MaxSessions 10
LoginGraceTime 30
ClientAliveInterval 300
ClientAliveCountMax 2

# Logging and Monitoring
LogLevel VERBOSE  # Detailed logging for PQ algorithm tracking
SyslogFacility AUTH

# Network Configuration
TCPKeepAlive yes
UseDNS no  # Reduce attack surface
PermitUserEnvironment no

# Advanced Security
AllowUsers quantum-admin  # Restrict allowed users
DenyUsers root
DenyGroups root

# Quantum Shield Specific
# Force post-quantum algorithms for specific users
Match User quantum-admin
    PubkeyAcceptedKeyTypes ssh-ml-dsa-65,ssh-slh-dsa-128s
    HostKeyAlgorithms ssh-ml-dsa-65,ssh-slh-dsa-128s
    KexAlgorithms ml-kem-768

# Development/Testing Users (Hybrid Mode)
Match User dev-*
    PubkeyAcceptedKeyTypes ssh-ml-dsa-65,ssh-ed25519
    HostKeyAlgorithms ssh-ml-dsa-65,ssh-ed25519
    KexAlgorithms hybrid-x25519-ml-kem-768,ml-kem-768
```

#### Security Validation Script
```bash
#!/bin/bash
# validate_ssh_pq_config.sh - Validate SSH PQ Configuration

echo "🔍 Validating SSH Post-Quantum Configuration..."

# Check host keys exist
echo "📋 Checking host keys:"
for key_type in ml_dsa_65 slh_dsa_128s; do
    key_file="/etc/ssh/ssh_host_${key_type}_key"
    if [[ -f "$key_file" ]]; then
        echo "  ✅ $key_file exists"
        # Check permissions
        perms=$(stat -c "%a" "$key_file")
        if [[ "$perms" == "600" ]]; then
            echo "  ✅ $key_file permissions correct (600)"
        else
            echo "  ❌ $key_file permissions incorrect ($perms), should be 600"
        fi
    else
        echo "  ❌ $key_file missing"
    fi
done

# Validate configuration syntax
echo "📋 Validating sshd_config syntax:"
if sshd -t; then
    echo "  ✅ sshd_config syntax valid"
else
    echo "  ❌ sshd_config syntax errors"
fi

# Check if PQ algorithms are supported
echo "📋 Checking PQ algorithm support:"
ssh -Q kex | grep -E "(ml-kem|kyber)" && echo "  ✅ ML-KEM support detected" || echo "  ⚠️  ML-KEM not detected"
ssh -Q key | grep -E "(ml-dsa|dilithium)" && echo "  ✅ ML-DSA support detected" || echo "  ⚠️  ML-DSA not detected"

echo "🎉 SSH PQ validation complete!"
```

## Client Configuration

### SSH Client Configuration Template
```bash
# ~/.ssh/config - Post-Quantum SSH Client Configuration

# Global Defaults (Post-Quantum Preferred)
Host *
    # Key Exchange - Prefer PQ
    KexAlgorithms ml-kem-768,hybrid-x25519-ml-kem-768,curve25519-sha256
    
    # Host Key Verification - Prefer PQ
    HostKeyAlgorithms ssh-ml-dsa-65,ssh-slh-dsa-128s,ssh-ed25519
    
    # Public Key Authentication - Prefer PQ
    PubkeyAcceptedKeyTypes ssh-ml-dsa-65,ssh-slh-dsa-128s,ssh-ed25519
    
    # Identity Files - PQ Keys First
    IdentityFile ~/.ssh/id_ml_dsa_65
    IdentityFile ~/.ssh/id_slh_dsa_128s  
    IdentityFile ~/.ssh/id_ed25519  # Fallback
    
    # Ciphers - Already Quantum-Resistant
    Ciphers aes256-gcm@openssh.com,chacha20-poly1305@openssh.com
    
    # MACs - Already Quantum-Resistant  
    MACs hmac-sha2-256-etm@openssh.com,hmac-sha2-512-etm@openssh.com
    
    # Security Settings
    HashKnownHosts yes
    VerifyHostKeyDNS ask
    StrictHostKeyChecking ask
    UserKnownHostsFile ~/.ssh/known_hosts ~/.ssh/known_hosts_pq

# High-Security Hosts (PQ-Only)
Host secure-* quantum-* prod-*
    KexAlgorithms ml-kem-768
    HostKeyAlgorithms ssh-ml-dsa-65,ssh-slh-dsa-128s
    PubkeyAcceptedKeyTypes ssh-ml-dsa-65,ssh-slh-dsa-128s
    IdentityFile ~/.ssh/id_ml_dsa_65
    StrictHostKeyChecking yes

# Development Hosts (Hybrid Mode)
Host dev-* test-* staging-*
    KexAlgorithms hybrid-x25519-ml-kem-768,ml-kem-768,curve25519-sha256
    HostKeyAlgorithms ssh-ml-dsa-65,ssh-ed25519
    PubkeyAcceptedKeyTypes ssh-ml-dsa-65,ssh-ed25519
    StrictHostKeyChecking no  # For development flexibility

# Legacy Hosts (During Migration)
Host legacy-* old-*
    KexAlgorithms curve25519-sha256,diffie-hellman-group16-sha512
    HostKeyAlgorithms ssh-ed25519,rsa-sha2-512
    PubkeyAcceptedKeyTypes ssh-ed25519,rsa-sha2-512
    IdentityFile ~/.ssh/id_ed25519
    IdentityFile ~/.ssh/id_rsa
```

### Client Key Management Script
```bash
#!/bin/bash
# ssh_pq_client_setup.sh - Setup PQ SSH Client

echo "🔧 Setting up Post-Quantum SSH Client..."

# Create SSH directory if it doesn't exist
mkdir -p ~/.ssh
chmod 700 ~/.ssh

# Generate PQ keys if they don't exist
if [[ ! -f ~/.ssh/id_ml_dsa_65 ]]; then
    echo "🔑 Generating ML-DSA-65 key..."
    ssh-keygen -t ml-dsa-65 -f ~/.ssh/id_ml_dsa_65 -N "" \
        -C "$(whoami)@$(hostname)-ml-dsa-65-$(date +%Y%m%d)"
fi

if [[ ! -f ~/.ssh/id_slh_dsa_128s ]]; then
    echo "🔑 Generating SLH-DSA-128s key..."
    ssh-keygen -t slh-dsa-128s -f ~/.ssh/id_slh_dsa_128s -N "" \
        -C "$(whoami)@$(hostname)-slh-dsa-128s-$(date +%Y%m%d)"
fi

# Set proper permissions
chmod 600 ~/.ssh/id_*
chmod 644 ~/.ssh/id_*.pub

# Create separate known_hosts for PQ
touch ~/.ssh/known_hosts_pq
chmod 644 ~/.ssh/known_hosts_pq

echo "✅ Post-quantum SSH client setup complete!"
echo "📋 Public keys generated:"
ls -la ~/.ssh/id_*.pub

echo ""
echo "🚀 Next steps:"
echo "1. Copy public key to servers: ssh-copy-id -i ~/.ssh/id_ml_dsa_65.pub user@server"
echo "2. Update ~/.ssh/config with PQ preferences"
echo "3. Test connection: ssh -v user@server"
```

## Migration Planning

### Migration Timeline (12-Week Plan)

#### Week 1-2: Preparation
- [ ] Inventory all SSH servers and clients
- [ ] Update SSH software to PQ-capable versions
- [ ] Generate PQ host keys on all servers
- [ ] Create migration documentation

#### Week 3-4: Pilot Deployment
- [ ] Deploy hybrid configuration on development servers
- [ ] Generate PQ user keys for admin team
- [ ] Test PQ connections in controlled environment
- [ ] Document any compatibility issues

#### Week 5-8: Gradual Rollout
- [ ] Deploy hybrid mode to staging environments
- [ ] Begin user key migration program
- [ ] Implement monitoring for PQ algorithm usage
- [ ] Train operations team on PQ troubleshooting

#### Week 9-12: Full Deployment
- [ ] Deploy PQ-preferred mode to production
- [ ] Gradually disable classical algorithms
- [ ] Complete user key migration
- [ ] Final validation and certification

### Migration Checklist Template
```bash
# SSH PQ Migration Checklist for: [SERVER/CLIENT NAME]

## Pre-Migration
- [ ] Current SSH version: ____________
- [ ] PQ algorithms supported: ____________
- [ ] Backup created: ____________
- [ ] Change window scheduled: ____________

## Migration Steps  
- [ ] Generate PQ host keys
- [ ] Update sshd_config with hybrid mode
- [ ] Restart SSH service
- [ ] Verify classical connections still work
- [ ] Test PQ connections
- [ ] Update monitoring configuration

## Post-Migration Validation
- [ ] PQ algorithms in use: ____________
- [ ] No connection failures: ____________
- [ ] Logs show PQ usage: ____________
- [ ] Performance acceptable: ____________

## Rollback Plan (if needed)
- [ ] Restore original sshd_config
- [ ] Restart SSH service
- [ ] Verify classical connections restored

Completed by: ____________ Date: ____________
```

## Security Monitoring

### SSH PQ Usage Monitoring

#### Log Analysis Script
```bash
#!/bin/bash
# ssh_pq_monitor.sh - Monitor SSH PQ Algorithm Usage

echo "📊 SSH Post-Quantum Usage Analysis"
echo "=================================="

# Analyze authentication log for PQ algorithm usage
echo "🔍 Key Exchange Algorithms:"
grep "kex:" /var/log/auth.log | grep -E "(ml-kem|kyber|hybrid)" | \
    awk '{print $NF}' | sort | uniq -c | sort -nr

echo ""
echo "🔍 Host Key Algorithms:"  
grep "hostkey:" /var/log/auth.log | grep -E "(ml-dsa|dilithium|slh-dsa)" | \
    awk '{print $NF}' | sort | uniq -c | sort -nr

echo ""
echo "🔍 User Authentication Methods:"
grep "Accepted publickey" /var/log/auth.log | grep -E "(ML-DSA|SLH-DSA)" | \
    awk '{print $(NF-1), $NF}' | sort | uniq -c | sort -nr

# Check for classical algorithm usage (potential security risk)
echo ""
echo "⚠️  Classical Algorithm Usage (Security Risk):"
grep -E "(ssh-rsa|ecdsa-sha2|ssh-dss)" /var/log/auth.log | tail -10

# Performance metrics
echo ""
echo "📈 Connection Performance:"
grep "Connection established" /var/log/auth.log | \
    grep -o "time=[0-9]*ms" | \
    awk -F= '{sum+=$2; count++} END {if(count>0) print "Average handshake time:", sum/count "ms"}'
```

#### Real-time Monitoring with systemd
```bash
# /etc/systemd/system/ssh-pq-monitor.service
[Unit]
Description=SSH Post-Quantum Algorithm Monitor
After=ssh.service

[Service]
Type=oneshot
ExecStart=/usr/local/bin/ssh_pq_monitor.sh
User=root

[Install]
WantedBy=multi-user.target

# /etc/systemd/system/ssh-pq-monitor.timer  
[Unit]
Description=Run SSH PQ Monitor every 15 minutes
Requires=ssh-pq-monitor.service

[Timer]
OnCalendar=*:0/15
Persistent=true

[Install]
WantedBy=timers.target
```

### Security Alerting

#### Critical Alerts Configuration
```yaml
# SSH PQ Security Alerts

alerts:
  - name: "Classical SSH Algorithm Used"
    condition: 'grep -q "ssh-rsa\|ecdsa-sha2" /var/log/auth.log'
    severity: "HIGH"
    action: "immediate_notification"
    description: "Classical cryptography detected in SSH connection"
    
  - name: "SSH PQ Algorithm Failure"  
    condition: 'grep -q "no matching key exchange method\|no matching host key type" /var/log/auth.log'
    severity: "MEDIUM" 
    action: "investigation_required"
    description: "Post-quantum algorithm negotiation failed"
    
  - name: "Excessive SSH Connection Failures"
    condition: 'grep -c "Connection closed by authenticating user" /var/log/auth.log | awk "{if($1>10) exit 0; else exit 1}"'
    severity: "MEDIUM"
    action: "security_review"
    description: "High number of SSH authentication failures"

  - name: "SSH Configuration Changed"
    condition: 'inotifywait -e modify /etc/ssh/sshd_config'
    severity: "HIGH"
    action: "immediate_validation"
    description: "SSH configuration file modified"
```

## Troubleshooting Guide

### Common Issues and Solutions

#### Issue 1: PQ Algorithm Not Supported
**Symptoms**: `no matching key exchange method found` or `no matching host key type found`

**Diagnosis**:
```bash
# Check SSH version and PQ support
ssh -V
ssh -Q kex | grep -E "(ml-kem|kyber)"
ssh -Q key | grep -E "(ml-dsa|dilithium)"
```

**Solution**:
```bash
# Upgrade OpenSSH to PQ-capable version
# Ubuntu/Debian
sudo apt update && sudo apt install openssh-server openssh-client

# Or compile from source with PQ support
wget https://github.com/open-quantum-safe/openssh/releases/latest
./configure --with-liboqs
make && sudo make install
```

#### Issue 2: Host Key Verification Failed
**Symptoms**: `Host key verification failed` with PQ keys

**Diagnosis**:
```bash
# Check if PQ host key is in known_hosts
ssh-keygen -F hostname -f ~/.ssh/known_hosts
```

**Solution**:
```bash
# Remove old host key and accept new PQ key
ssh-keygen -R hostname
ssh -o StrictHostKeyChecking=ask hostname
```

#### Issue 3: Performance Degradation
**Symptoms**: Slow SSH connection establishment

**Diagnosis**:
```bash
# Time SSH connection with verbose output
time ssh -v hostname
```

**Solution**:
```bash
# Optimize SSH configuration
# In /etc/ssh/sshd_config:
UseDNS no
GSSAPIAuthentication no

# Prefer faster PQ algorithms
KexAlgorithms ml-kem-768  # Faster than hybrid modes
```

#### Issue 4: Key Generation Failure
**Symptoms**: `ssh-keygen: unknown key type ml-dsa-65`

**Diagnosis**:
```bash
# Check available key types
ssh-keygen -?
```

**Solution**:
```bash
# Install PQ-capable OpenSSH or use alternative tools
# Generate keys with liboqs directly:
oqs-keygen -a ml-dsa-65 -o ml_dsa_65_key
```

### Emergency Procedures

#### Fallback to Classical Crypto
```bash
#!/bin/bash
# emergency_ssh_fallback.sh - Emergency fallback to classical crypto

echo "🚨 EMERGENCY: Reverting to classical SSH configuration"

# Backup current PQ configuration
cp /etc/ssh/sshd_config /etc/ssh/sshd_config.pq_backup

# Create emergency classical configuration
cat > /etc/ssh/sshd_config.emergency << EOF
# Emergency Classical SSH Configuration
Protocol 2
Port 22

# Classical host keys only
HostKey /etc/ssh/ssh_host_ed25519_key
HostKey /etc/ssh/ssh_host_rsa_key

# Classical algorithms only
HostKeyAlgorithms ssh-ed25519,rsa-sha2-512
PubkeyAcceptedKeyTypes ssh-ed25519,rsa-sha2-512
KexAlgorithms curve25519-sha256,diffie-hellman-group16-sha512

# Standard security settings
PubkeyAuthentication yes
PasswordAuthentication no
PermitRootLogin no
EOF

# Apply emergency configuration
cp /etc/ssh/sshd_config.emergency /etc/ssh/sshd_config
systemctl restart ssh

echo "✅ Emergency fallback complete. SSH service restored with classical crypto."
echo "⚠️  Remember to investigate PQ issues and restore PQ configuration when resolved."
```

## Best Practices Summary

### Security Recommendations
1. **Always use hybrid mode** during migration period
2. **Generate separate PQ keys** - don't replace classical keys immediately
3. **Monitor algorithm usage** to ensure PQ adoption
4. **Implement proper key rotation** for PQ keys
5. **Test thoroughly** in non-production environments first

### Performance Optimization
1. **Use ML-KEM-768** for optimal performance/security balance
2. **Disable unnecessary features** (DNS lookups, GSSAPI)
3. **Implement connection multiplexing** for frequent connections
4. **Monitor handshake performance** and alert on degradation

### Operational Excellence
1. **Maintain detailed migration logs** 
2. **Implement automated testing** of PQ connections
3. **Train operations team** on PQ troubleshooting
4. **Plan rollback procedures** for each deployment phase
5. **Regular security audits** of PQ implementation

---

**Document Version**: 1.0  
**Last Updated**: October 12, 2025  
**Classification**: Internal Use - Quantum Shield Project  
**Next Review**: November 12, 2025