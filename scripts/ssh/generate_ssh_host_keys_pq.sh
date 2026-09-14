#!/bin/bash
# generate_ssh_host_keys_pq.sh - Generate Post-Quantum SSH Host Keys
# Part of Quantum Shield Project

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SSH_DIR="/etc/ssh"
BACKUP_DIR="/etc/ssh/classical_backup"
DATE=$(date +%Y%m%d_%H%M%S)
HOSTNAME=$(hostname -f)

# Function to print status
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "This script must be run as root"
        exit 1
    fi
}

# Check SSH version and PQ support
check_ssh_support() {
    print_status "Checking SSH version and post-quantum support..."
    
    SSH_VERSION=$(ssh -V 2>&1 | head -1)
    print_status "SSH Version: $SSH_VERSION"
    
    # Check for PQ algorithm support
    if ssh -Q kex 2>/dev/null | grep -q "ml-kem\|kyber"; then
        print_success "ML-KEM support detected"
        PQ_KEX_SUPPORT=true
    else
        print_warning "ML-KEM support not detected"
        PQ_KEX_SUPPORT=false
    fi
    
    if ssh -Q key 2>/dev/null | grep -q "ml-dsa\|dilithium"; then
        print_success "ML-DSA support detected"
        PQ_KEY_SUPPORT=true
    else
        print_warning "ML-DSA support not detected"
        PQ_KEY_SUPPORT=false
    fi
    
    if [[ "$PQ_KEY_SUPPORT" == false ]]; then
        print_error "Post-quantum key algorithms not supported by current SSH version"
        print_warning "Consider upgrading to PQ-capable OpenSSH or using liboqs-based tools"
        return 1
    fi
}

# Backup existing keys
backup_existing_keys() {
    print_status "Creating backup of existing SSH host keys..."
    
    mkdir -p "$BACKUP_DIR"
    
    # Backup classical keys
    for key_type in rsa ecdsa ed25519 dsa; do
        if [[ -f "$SSH_DIR/ssh_host_${key_type}_key" ]]; then
            cp "$SSH_DIR/ssh_host_${key_type}_key" "$BACKUP_DIR/ssh_host_${key_type}_key.${DATE}"
            cp "$SSH_DIR/ssh_host_${key_type}_key.pub" "$BACKUP_DIR/ssh_host_${key_type}_key.pub.${DATE}"
            print_success "Backed up $key_type host key"
        fi
    done
    
    print_success "Backup completed in $BACKUP_DIR"
}

# Generate post-quantum host keys using liboqs (fallback method)
generate_pq_keys_liboqs() {
    print_status "Generating post-quantum keys using liboqs..."
    
    # Check if liboqs is available
    if ! command -v oqs-keygen &> /dev/null; then
        print_error "liboqs tools not found. Install liboqs and try again."
        return 1
    fi
    
    # ML-DSA-65 (Primary)
    print_status "Generating ML-DSA-65 host key..."
    oqs-keygen -a ML-DSA-65 -o "$SSH_DIR/ssh_host_ml_dsa_65_key"
    chmod 600 "$SSH_DIR/ssh_host_ml_dsa_65_key"
    
    # Extract public key
    oqs-pubkey -i "$SSH_DIR/ssh_host_ml_dsa_65_key" -o "$SSH_DIR/ssh_host_ml_dsa_65_key.pub"
    chmod 644 "$SSH_DIR/ssh_host_ml_dsa_65_key.pub"
    
    # SLH-DSA-128s (Backup)
    print_status "Generating SLH-DSA-128s host key..."
    oqs-keygen -a SLH-DSA-128s -o "$SSH_DIR/ssh_host_slh_dsa_128s_key"
    chmod 600 "$SSH_DIR/ssh_host_slh_dsa_128s_key"
    
    # Extract public key
    oqs-pubkey -i "$SSH_DIR/ssh_host_slh_dsa_128s_key" -o "$SSH_DIR/ssh_host_slh_dsa_128s_key.pub"
    chmod 644 "$SSH_DIR/ssh_host_slh_dsa_128s_key.pub"
    
    print_success "Post-quantum host keys generated using liboqs"
}

# Generate post-quantum host keys using OpenSSH (preferred method)
generate_pq_keys_openssh() {
    print_status "Generating post-quantum keys using OpenSSH..."
    
    # ML-DSA-65 (Dilithium3) - Primary host key
    print_status "Generating ML-DSA-65 host key..."
    if ssh-keygen -t ml-dsa-65 -f "$SSH_DIR/ssh_host_ml_dsa_65_key" -N "" \
       -C "$HOSTNAME-ml-dsa-65-$DATE" >/dev/null 2>&1; then
        print_success "ML-DSA-65 host key generated"
    else
        print_error "Failed to generate ML-DSA-65 key with ssh-keygen"
        return 1
    fi
    
    # SLH-DSA-128s (SPHINCS+) - Backup host key
    print_status "Generating SLH-DSA-128s host key..."
    if ssh-keygen -t slh-dsa-128s -f "$SSH_DIR/ssh_host_slh_dsa_128s_key" -N "" \
       -C "$HOSTNAME-slh-dsa-128s-$DATE" >/dev/null 2>&1; then
        print_success "SLH-DSA-128s host key generated"
    else
        print_warning "Failed to generate SLH-DSA-128s key with ssh-keygen"
        print_warning "This is non-critical - ML-DSA-65 is sufficient for most use cases"
    fi
    
    print_success "Post-quantum host keys generated using OpenSSH"
}

# Set proper permissions and ownership
set_permissions() {
    print_status "Setting proper permissions and ownership..."
    
    # Set permissions for private keys
    chmod 600 "$SSH_DIR"/ssh_host_*_key 2>/dev/null || true
    
    # Set permissions for public keys  
    chmod 644 "$SSH_DIR"/ssh_host_*_key.pub 2>/dev/null || true
    
    # Set ownership
    chown root:root "$SSH_DIR"/ssh_host_*_key* 2>/dev/null || true
    
    print_success "Permissions and ownership set correctly"
}

# Verify generated keys
verify_keys() {
    print_status "Verifying generated keys..."
    
    echo ""
    echo "📋 Generated SSH Host Keys:"
    echo "=========================="
    
    for key_file in "$SSH_DIR"/ssh_host_*_key.pub; do
        if [[ -f "$key_file" ]]; then
            key_type=$(ssh-keygen -l -f "$key_file" 2>/dev/null | awk '{print $4}' | tr -d '()')
            key_bits=$(ssh-keygen -l -f "$key_file" 2>/dev/null | awk '{print $1}')
            key_comment=$(ssh-keygen -l -f "$key_file" 2>/dev/null | awk '{for(i=5;i<=NF;i++) printf $i" "; print ""}')
            
            if [[ "$key_type" =~ (ML-DSA|SLH-DSA|ml-dsa|slh-dsa) ]]; then
                echo "  🛡️  $key_file"
                echo "     Type: $key_type (Post-Quantum)"
                echo "     Bits: $key_bits"
                echo "     Comment: $key_comment"
            else
                echo "  🔑 $key_file"  
                echo "     Type: $key_type (Classical)"
                echo "     Bits: $key_bits"
            fi
            echo ""
        fi
    done
}

# Generate SSH configuration snippet
generate_config_snippet() {
    print_status "Generating SSH configuration snippet..."
    
    cat > "/tmp/sshd_config_pq_snippet.conf" << EOF
# Post-Quantum SSH Configuration Snippet
# Generated by Quantum Shield on $(date)
# Add this to /etc/ssh/sshd_config

# Host Key Configuration (Post-Quantum + Hybrid)
HostKey /etc/ssh/ssh_host_ml_dsa_65_key
HostKey /etc/ssh/ssh_host_slh_dsa_128s_key
HostKey /etc/ssh/ssh_host_ed25519_key

# Algorithm Selection (PQ-Preferred)
HostKeyAlgorithms ssh-ml-dsa-65,ssh-slh-dsa-128s,ssh-ed25519,rsa-sha2-512
PubkeyAcceptedKeyTypes ssh-ml-dsa-65,ssh-slh-dsa-128s,ssh-ed25519,rsa-sha2-512

# Key Exchange (Post-Quantum preferred)
KexAlgorithms ml-kem-768,hybrid-x25519-ml-kem-768,curve25519-sha256@libssh.org

# Symmetric Ciphers (Already Quantum-Resistant)
Ciphers aes256-gcm@openssh.com,chacha20-poly1305@openssh.com,aes256-ctr

# MAC Algorithms (Already Quantum-Resistant)  
MACs hmac-sha2-256-etm@openssh.com,hmac-sha2-512-etm@openssh.com
EOF
    
    print_success "Configuration snippet saved to /tmp/sshd_config_pq_snippet.conf"
}

# Main execution
main() {
    echo "🛡️  Quantum Shield - SSH Host Key Generator"
    echo "==========================================="
    echo ""
    
    # Perform checks
    check_root
    check_ssh_support || {
        print_warning "Continuing with liboqs fallback method..."
    }
    
    # Get user confirmation
    echo ""
    print_warning "This script will generate new post-quantum SSH host keys."
    print_warning "Existing keys will be backed up but clients may need to accept new host keys."
    echo ""
    read -p "Do you want to continue? [y/N]: " -n 1 -r
    echo ""
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_status "Operation cancelled by user"
        exit 0
    fi
    
    # Execute key generation
    backup_existing_keys
    
    # Try OpenSSH method first, fallback to liboqs
    if [[ "$PQ_KEY_SUPPORT" == true ]]; then
        generate_pq_keys_openssh || generate_pq_keys_liboqs
    else
        generate_pq_keys_liboqs
    fi
    
    set_permissions
    verify_keys
    generate_config_snippet
    
    echo ""
    print_success "🎉 Post-quantum SSH host key generation complete!"
    echo ""
    echo "📋 Next Steps:"
    echo "1. Review configuration snippet: cat /tmp/sshd_config_pq_snippet.conf"
    echo "2. Update /etc/ssh/sshd_config with post-quantum settings"
    echo "3. Test configuration: sshd -t"
    echo "4. Restart SSH service: systemctl restart ssh"
    echo "5. Update client known_hosts files"
    echo ""
    echo "⚠️  Important:"
    echo "- Clients will need to accept new host keys"
    echo "- Test connections from a different terminal session"
    echo "- Keep backup keys until migration is complete"
    echo ""
    echo "📚 Documentation: docs/SSH_POST_QUANTUM_GUIDE.md"
}

# Execute main function
main "$@"