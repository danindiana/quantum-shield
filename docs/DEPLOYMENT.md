# Deployment Guide - Quantum Shield

## Quick Deploy Checklist

### Immediate Actions (Week 1)
- [ ] **Run Setup**: `./scripts/setup.sh`
- [ ] **Install Dependencies**: liboqs, Python libraries
- [ ] **Configure Environment**: Edit `configs/quantum_shield_config.yaml`
- [ ] **Verify Installation**: `make test`
- [ ] **Security Scan**: `make security`

### Critical Systems (Week 1-2)
- [ ] **TLS/SSL Endpoints**: Enable ML-KEM + ML-DSA
- [ ] **Database Encryption**: Implement hybrid AES + ML-KEM
- [ ] **API Security**: JWT with ML-DSA signatures
- [ ] **User Authentication**: Multi-factor with PQ algorithms

### Phase 1 Deployment (Week 1-4)

#### Day 1: Environment Preparation
```bash
# 1. Setup quantum shield
cd ~/programs/quantum-shield
./scripts/setup.sh

# 2. Verify installation
source venv/bin/activate
python quantum_shield.py setup
make test

# 3. Security baseline
make security
```

#### Day 2-3: Core Algorithm Implementation
- [ ] Integrate liboqs library
- [ ] Implement ML-KEM key encapsulation
- [ ] Implement ML-DSA digital signatures
- [ ] Add SLH-DSA for long-term signatures
- [ ] Create algorithm test suite

#### Day 4-7: Protocol Integration
- [ ] TLS 1.3 post-quantum extensions
- [ ] X.509 certificate with PQ public keys
- [ ] JWT token signing with ML-DSA
- [ ] Database connection encryption
- [ ] API endpoint protection

#### Week 2-4: System Integration
- [ ] Key Management System (KMS)
- [ ] Certificate Authority (CA) setup
- [ ] Monitoring and logging
- [ ] Performance optimization
- [ ] Documentation and training

## Production Deployment Steps

### Pre-Deployment Checklist
```bash
# System requirements check
./scripts/system_check.sh

# Security audit
./scripts/security_audit.sh  

# Performance baseline
./scripts/benchmark.sh

# Backup current configuration
./scripts/backup_config.sh
```

### Deployment Phases

#### Phase 1: Pilot Deployment (Non-Critical Systems)
1. **Development Environment**
   ```bash
   # Deploy to dev environment
   ./scripts/deploy.sh --env=dev --mode=pilot
   
   # Verify functionality
   ./scripts/verify_deployment.sh --env=dev
   ```

2. **Staging Environment**
   ```bash
   # Deploy to staging with monitoring
   ./scripts/deploy.sh --env=staging --monitor=true
   
   # Load testing with PQ algorithms
   ./scripts/load_test.sh --duration=1h
   ```

#### Phase 2: Production Rollout (Critical Systems)
1. **Blue-Green Deployment**
   ```bash
   # Prepare green environment
   ./scripts/deploy.sh --env=prod --slot=green --prepare-only
   
   # Switch traffic gradually
   ./scripts/traffic_switch.sh --percentage=10
   ./scripts/traffic_switch.sh --percentage=50
   ./scripts/traffic_switch.sh --percentage=100
   ```

2. **Rollback Plan**
   ```bash
   # If issues detected
   ./scripts/rollback.sh --env=prod --immediate
   
   # Verify rollback
   ./scripts/verify_rollback.sh
   ```

### Configuration Management

#### Production Configuration
```yaml
# configs/production.yaml
environment: "production"

security:
  minimum_level: 5          # Highest security for production
  enforce_pq_only: true    # No classical fallbacks
  hsm_required: true       # Hardware security modules required

monitoring:
  alert_threshold: 0.05    # 50ms max latency
  audit_level: "FULL"      # Complete audit logging
  real_time_monitoring: true

performance:
  connection_pool_size: 100
  cache_ttl: 3600
  batch_operations: true
```

#### Staging Configuration  
```yaml
# configs/staging.yaml
environment: "staging"

security:
  minimum_level: 3         # Moderate security for testing
  enforce_pq_only: false   # Allow hybrid mode
  test_vectors: true       # Enable test vector validation

monitoring:
  alert_threshold: 0.1     # 100ms tolerance for testing
  debug_logging: true      # Detailed logging for debugging
```

## Infrastructure Requirements

### Hardware Specifications

#### Minimum Requirements
- **CPU**: 4 cores, 2.4GHz (with AES-NI support)
- **RAM**: 8GB DDR4
- **Storage**: 100GB SSD
- **Network**: 1Gbps connection

#### Recommended Production
- **CPU**: 16 cores, 3.2GHz (with cryptographic acceleration)
- **RAM**: 32GB DDR4 ECC
- **Storage**: 500GB NVMe SSD (enterprise grade)
- **Network**: 10Gbps redundant connections
- **HSM**: Hardware Security Module (FIPS 140-2 Level 3+)

### Software Dependencies

#### Operating System
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install build-essential cmake git python3 python3-pip libssl-dev

# CentOS/RHEL
sudo yum groupinstall "Development Tools"
sudo yum install cmake git python3 python3-pip openssl-devel

# Alpine (containers)
apk add build-base cmake git python3 py3-pip openssl-dev
```

#### Container Deployment
```dockerfile
# Dockerfile for Quantum Shield
FROM ubuntu:22.04

# Install dependencies
RUN apt-get update && apt-get install -y \
    build-essential cmake git python3 python3-pip libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy application
COPY . /app
WORKDIR /app

# Setup application
RUN ./scripts/setup.sh

# Expose secure port
EXPOSE 8443

# Start quantum shield
CMD ["python3", "quantum_shield.py", "server", "--port", "8443"]
```

### Network Security Configuration

#### Firewall Rules
```bash
# Allow only post-quantum secured connections
iptables -A INPUT -p tcp --dport 8443 -j ACCEPT  # Quantum Shield
iptables -A INPUT -p tcp --dport 443 -j DROP     # Block classical HTTPS
iptables -A INPUT -p tcp --dport 80 -j DROP      # Block HTTP

# Log rejected classical crypto attempts
iptables -A INPUT -p tcp --dport 443 -j LOG --log-prefix "CLASSICAL-CRYPTO-BLOCKED: "
```

#### Load Balancer Configuration
```nginx
# nginx.conf for post-quantum load balancing
upstream quantum_shield_backend {
    server 10.0.1.10:8443 max_fails=3 fail_timeout=30s;
    server 10.0.1.11:8443 max_fails=3 fail_timeout=30s;
    server 10.0.1.12:8443 max_fails=3 fail_timeout=30s;
}

server {
    listen 8443 ssl http2;
    server_name secure.example.com;
    
    # Post-quantum certificate
    ssl_certificate /etc/ssl/certs/quantum-shield.crt;
    ssl_certificate_key /etc/ssl/private/quantum-shield.key;
    
    # Post-quantum cipher suites only
    ssl_ciphers 'TLS_KYBER768_WITH_AES_256_GCM_SHA384:TLS_DILITHIUM3_WITH_AES_256_GCM_SHA384';
    ssl_prefer_server_ciphers on;
    ssl_protocols TLSv1.3;
    
    location / {
        proxy_pass https://quantum_shield_backend;
        proxy_set_header X-Post-Quantum-Enabled "true";
    }
}
```

## Monitoring and Alerting

### Key Performance Indicators (KPIs)

#### Security Metrics
- **PQ Algorithm Usage**: 100% of connections use post-quantum crypto
- **Certificate Validation**: <5 second validation time
- **Key Rotation**: Automated rotation every 30 days
- **Quantum Threat Detection**: Real-time monitoring active

#### Performance Metrics  
- **Handshake Latency**: <100ms average
- **Signature Generation**: <5ms average
- **Verification Time**: <2ms average  
- **System Availability**: >99.9% uptime

#### Compliance Metrics
- **NIST Compliance**: 100% adherence to standards
- **Audit Trail**: Complete logging of all crypto operations
- **Incident Response**: <1 hour response time
- **Recovery Time**: <4 hours RTO with PQ intact

### Alerting Configuration
```yaml
# monitoring/alerts.yaml
alerts:
  - name: "Classical Crypto Detected"
    condition: "classical_crypto_usage > 0"
    severity: "CRITICAL"
    action: "immediate_block"
    
  - name: "High PQ Latency"
    condition: "pq_handshake_time > 100ms"
    severity: "WARNING"
    action: "scale_resources"
    
  - name: "Key Rotation Failure"
    condition: "key_rotation_failed == true"
    severity: "HIGH"
    action: "manual_intervention"
    
  - name: "Quantum Threat Detected"
    condition: "quantum_attack_pattern == true"
    severity: "CRITICAL"
    action: "emergency_protocol"
```

## Validation and Testing

### Pre-Deployment Testing
```bash
# Comprehensive test suite
./scripts/run_all_tests.sh

# Security penetration testing
./scripts/pentest.sh --quantum-aware

# Performance benchmarking
./scripts/benchmark.sh --production-load

# Compliance verification
./scripts/nist_compliance_check.sh
```

### Post-Deployment Verification
```bash
# Verify PQ algorithms are active
./scripts/verify_pq_active.sh

# Check certificate chain
./scripts/verify_certificates.sh

# Performance validation
./scripts/performance_check.sh

# Security posture assessment
./scripts/security_assessment.sh
```

### Continuous Testing
- **Daily**: Automated security scans
- **Weekly**: Performance regression tests
- **Monthly**: Full compliance audits
- **Quarterly**: Penetration testing

## Troubleshooting Guide

### Common Issues

#### Issue: High Latency with PQ Algorithms
**Symptoms**: >100ms handshake time
**Solution**:
```bash
# Enable hardware acceleration
echo "crypto_acceleration=true" >> configs/quantum_shield_config.yaml

# Increase connection pool
sed -i 's/connection_pool_size: 50/connection_pool_size: 200/' configs/production.yaml

# Restart service
./scripts/restart.sh --graceful
```

#### Issue: Certificate Validation Failures
**Symptoms**: PQ certificate not recognized
**Solution**:
```bash
# Update certificate chain
./scripts/update_certificates.sh --force

# Verify certificate format
openssl x509 -in quantum-shield.crt -text -noout | grep -i "public key algorithm"

# Regenerate if needed
./scripts/generate_certificates.sh --algorithm=ML-DSA-65
```

#### Issue: Key Rotation Failures
**Symptoms**: Automated key rotation not working
**Solution**:
```bash
# Check HSM connectivity
./scripts/hsm_status.sh

# Manual key rotation
./scripts/rotate_keys.sh --manual --force

# Update rotation schedule
crontab -e  # Add: 0 2 * * 0 /path/to/quantum-shield/scripts/rotate_keys.sh
```

### Emergency Procedures

#### Quantum Breakthrough Detected
```bash
# Immediate response protocol
./scripts/emergency/quantum_breach_response.sh

# Steps:
# 1. Activate highest security level
# 2. Disable all classical crypto fallbacks  
# 3. Force immediate key rotation
# 4. Enable maximum signature security
# 5. Alert all stakeholders
```

#### System Compromise
```bash
# Incident response
./scripts/emergency/incident_response.sh

# Steps:
# 1. Isolate affected systems
# 2. Preserve forensic evidence
# 3. Activate backup systems
# 4. Notify authorities if required
# 5. Begin recovery procedures
```

## Maintenance Schedule

### Daily Tasks
- [ ] Monitor system performance
- [ ] Check security alerts
- [ ] Verify backup systems
- [ ] Review audit logs

### Weekly Tasks  
- [ ] Performance optimization review
- [ ] Security patch updates
- [ ] Configuration backup
- [ ] Team status meeting

### Monthly Tasks
- [ ] Full security audit
- [ ] Compliance report generation
- [ ] Disaster recovery testing
- [ ] Training updates

### Quarterly Tasks
- [ ] Architecture review
- [ ] Third-party penetration testing
- [ ] Business continuity testing
- [ ] Strategic planning session

## Support and Resources

### Internal Documentation
- [Implementation Plan](IMPLEMENTATION_PLAN.md)
- [NIST Compliance Guide](NIST_COMPLIANCE.md)  
- [Security Architecture](SECURITY_ARCHITECTURE.md)
- [API Documentation](API.md)

### External Resources
- **NIST Post-Quantum Cryptography**: https://csrc.nist.gov/projects/post-quantum-cryptography
- **Open Quantum Safe**: https://openquantumsafe.org/
- **liboqs Documentation**: https://github.com/open-quantum-safe/liboqs

### Emergency Contacts
- **Security Team**: security@company.com
- **Operations Team**: ops@company.com
- **Management Escalation**: ciso@company.com
- **24/7 Hotline**: +1-800-QUANTUM