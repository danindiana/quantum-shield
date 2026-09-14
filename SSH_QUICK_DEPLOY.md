# SSH Post-Quantum Quick Deployment Guide

## 🚀 Quick Start: Secure SSH with Post-Quantum Cryptography

### Prerequisites Checklist
- [ ] SSH version 8.0+ (check: `ssh -V`)
- [ ] Root/sudo access for server configuration
- [ ] Backup of existing SSH configuration
- [ ] Test environment for validation

### 1. Generate Post-Quantum SSH Keys

#### For Servers (Host Keys):
```bash
# Generate PQ host keys
sudo ./scripts/ssh/generate_ssh_host_keys_pq.sh

# Verify keys generated
ls -la /etc/ssh/ssh_host_*_key*
```

#### For Users (Client Keys):
```bash
# Generate PQ user keys
./scripts/ssh/generate_ssh_user_keys_pq.sh

# Verify keys generated
ls -la ~/.ssh/id_*
```

### 2. Configure SSH Server

```bash
# Backup existing configuration
sudo cp /etc/ssh/sshd_config /etc/ssh/sshd_config.backup

# Apply Quantum Shield SSH configuration
sudo cp configs/ssh/sshd_config_quantum_shield.conf /etc/ssh/sshd_config

# Validate configuration
sudo sshd -t

# Restart SSH service
sudo systemctl restart ssh
# OR: sudo service ssh restart
```

### 3. Configure SSH Client

```bash
# Backup existing configuration
cp ~/.ssh/config ~/.ssh/config.backup 2>/dev/null || true

# Apply Quantum Shield client configuration
cp configs/ssh/ssh_config_quantum_shield.conf ~/.ssh/config

# Create connections directory for multiplexing
mkdir -p ~/.ssh/connections
chmod 700 ~/.ssh/connections
```

### 4. Test Post-Quantum Connection

```bash
# Test with verbose output to verify PQ algorithms
ssh -v username@server

# Look for these indicators in output:
# - "kex: ml-kem-768" (PQ key exchange)
# - "server host key: ssh-ml-dsa-65" (PQ host authentication)
# - "Offering public key: ~/.ssh/id_ml_dsa_65" (PQ user auth)
```

### 5. Monitor Usage

```bash
# Run SSH monitoring analysis
sudo ./scripts/ssh/ssh_pq_monitor.sh

# Real-time monitoring
sudo ./scripts/ssh/ssh_pq_monitor.sh --realtime

# Quick statistics
sudo ./scripts/ssh/ssh_pq_monitor.sh --stats
```

## 🛡️ Security Validation

### Verify Post-Quantum Algorithms Active

```bash
# Check server configuration
sudo grep -E "(ml-dsa|ml-kem|slh-dsa)" /etc/ssh/sshd_config

# Check client configuration  
grep -E "(ml-dsa|ml-kem|slh-dsa)" ~/.ssh/config

# Test algorithm support
ssh -Q kex | grep -E "(ml-kem|kyber)"
ssh -Q key | grep -E "(ml-dsa|dilithium)"
```

### Connection Test Script
```bash
#!/bin/bash
# Quick SSH PQ test

echo "🔍 Testing SSH Post-Quantum Connection..."

# Test connection with algorithm verification
ssh -o ConnectTimeout=10 -v user@server 'echo "SSH PQ test successful"' 2>&1 | \
  grep -E "(kex:|server host key:|Offering public key:)" | \
  while read line; do
    if echo "$line" | grep -qE "(ml-kem|ml-dsa|slh-dsa)"; then
      echo "✅ PQ: $line"
    else
      echo "⚠️  Classical: $line"
    fi
  done
```

## 📊 Migration Phases

### Phase 1: Hybrid Mode (Current Configuration)
- ✅ Both classical and PQ algorithms supported
- ✅ Gradual user migration possible
- ✅ Fallback to classical if PQ fails

### Phase 2: PQ-Preferred (Week 2-4)
```bash
# Update server to prefer PQ algorithms first
# In /etc/ssh/sshd_config:
HostKeyAlgorithms ssh-ml-dsa-65,ssh-slh-dsa-128s,ssh-ed25519
PubkeyAcceptedKeyTypes ssh-ml-dsa-65,ssh-slh-dsa-128s,ssh-ed25519
KexAlgorithms ml-kem-768,hybrid-x25519-ml-kem-768
```

### Phase 3: PQ-Only (Week 5-8)
```bash
# Disable classical algorithms entirely
# In /etc/ssh/sshd_config:
HostKeyAlgorithms ssh-ml-dsa-65,ssh-slh-dsa-128s
PubkeyAcceptedKeyTypes ssh-ml-dsa-65,ssh-slh-dsa-128s
KexAlgorithms ml-kem-768
```

## 🚨 Troubleshooting

### Common Issues

**Issue**: `no matching key exchange method found`
**Solution**: 
```bash
# Update SSH to PQ-capable version or use hybrid mode
KexAlgorithms hybrid-x25519-ml-kem-768,curve25519-sha256
```

**Issue**: `Host key verification failed`
**Solution**:
```bash
# Remove old host key and accept new PQ key
ssh-keygen -R hostname
ssh -o StrictHostKeyChecking=ask hostname
```

**Issue**: `Permission denied (publickey)`
**Solution**:
```bash
# Copy PQ public key to server
ssh-copy-id -i ~/.ssh/id_ml_dsa_65.pub user@server
# OR manually append to ~/.ssh/authorized_keys
```

### Emergency Fallback
```bash
# If PQ causes connection issues, temporarily fallback:
ssh -o HostKeyAlgorithms=ssh-ed25519 \
    -o KexAlgorithms=curve25519-sha256 \
    -o PubkeyAcceptedKeyTypes=ssh-ed25519 \
    user@server
```

## 📈 Success Metrics

### Security Goals
- [ ] 100% of SSH connections use post-quantum algorithms
- [ ] No classical-only authentication methods
- [ ] All host keys upgraded to ML-DSA or SLH-DSA
- [ ] Real-time monitoring shows >90% PQ adoption

### Performance Targets
- [ ] SSH handshake time <200ms with PQ algorithms
- [ ] No connection failures due to algorithm incompatibility
- [ ] Monitoring shows stable performance metrics

## 🔄 Automation Setup

### Cron Job for Monitoring
```bash
# Add to crontab (crontab -e):
# Monitor SSH PQ usage every 15 minutes
*/15 * * * * /path/to/quantum-shield/scripts/ssh/ssh_pq_monitor.sh --stats >> /var/log/quantum-shield/ssh_monitor.log 2>&1

# Daily detailed analysis
0 2 * * * /path/to/quantum-shield/scripts/ssh/ssh_pq_monitor.sh --analyze
```

### Log Rotation
```bash
# Add to /etc/logrotate.d/quantum-shield-ssh:
/var/log/quantum-shield/ssh/*.log {
    daily
    rotate 30
    compress
    missingok
    notifempty
    create 644 root root
}
```

## 📚 Additional Resources

- **Complete Guide**: `docs/SSH_POST_QUANTUM_GUIDE.md`
- **NIST Standards**: `docs/NIST_COMPLIANCE.md`
- **Security Architecture**: `docs/SECURITY_ARCHITECTURE.md`
- **Project Status**: `PROGRESS.md`

---

**⚡ Ready to Deploy**: Your SSH infrastructure is now quantum-resistant!