#!/bin/bash
# generate_ssh_user_keys_pq.sh - Generate Post-Quantum SSH User Keys
# Part of Quantum Shield Project

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SSH_DIR="$HOME/.ssh"
DATE=$(date +%Y%m%d_%H%M%S)
USERNAME=$(whoami)
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

# Setup SSH directory
setup_ssh_directory() {
    print_status "Setting up SSH directory..."
    
    if [[ ! -d "$SSH_DIR" ]]; then
        mkdir -p "$SSH_DIR"
        chmod 700 "$SSH_DIR"
        print_success "Created SSH directory: $SSH_DIR"
    else
        print_status "SSH directory exists: $SSH_DIR"
    fi
    
    # Check permissions
    perms=$(stat -c "%a" "$SSH_DIR")
    if [[ "$perms" != "700" ]]; then
        chmod 700 "$SSH_DIR"
        print_warning "Fixed SSH directory permissions (was $perms, now 700)"
    fi
}

# Check SSH client support
check_ssh_support() {
    print_status "Checking SSH client version and post-quantum support..."
    
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
}

# Backup existing keys
backup_existing_keys() {
    print_status "Backing up existing SSH keys..."
    
    backup_dir="$SSH_DIR/backup_$DATE"
    mkdir -p "$backup_dir"
    
    # Backup existing keys
    for key_file in "$SSH_DIR"/id_*; do
        if [[ -f "$key_file" ]]; then
            cp "$key_file" "$backup_dir/"
            print_success "Backed up $(basename "$key_file")"
        fi
    done
    
    if [[ $(ls -A "$backup_dir" 2>/dev/null) ]]; then
        print_success "Backup completed in $backup_dir"
    else
        print_status "No existing keys to backup"
        rmdir "$backup_dir"
    fi
}

# Generate post-quantum user keys using OpenSSH
generate_pq_keys_openssh() {
    print_status "Generating post-quantum user keys using OpenSSH..."
    
    # ML-DSA-65 (Primary user key)
    print_status "Generating ML-DSA-65 user key..."
    key_comment="$USERNAME@$HOSTNAME-ml-dsa-65-$DATE"
    
    if ssh-keygen -t ml-dsa-65 -f "$SSH_DIR/id_ml_dsa_65" -N "" -C "$key_comment" >/dev/null 2>&1; then
        print_success "ML-DSA-65 user key generated: $SSH_DIR/id_ml_dsa_65"
    else
        print_error "Failed to generate ML-DSA-65 key with ssh-keygen"
        return 1
    fi
    
    # SLH-DSA-128s (Backup user key for high-security)
    print_status "Generating SLH-DSA-128s user key..."
    key_comment="$USERNAME@$HOSTNAME-slh-dsa-128s-$DATE"
    
    if ssh-keygen -t slh-dsa-128s -f "$SSH_DIR/id_slh_dsa_128s" -N "" -C "$key_comment" >/dev/null 2>&1; then
        print_success "SLH-DSA-128s user key generated: $SSH_DIR/id_slh_dsa_128s"
    else
        print_warning "Failed to generate SLH-DSA-128s key"
        print_warning "This is non-critical - ML-DSA-65 is sufficient for most use cases"
    fi
}

# Generate post-quantum keys using liboqs (fallback)
generate_pq_keys_liboqs() {
    print_status "Generating post-quantum keys using liboqs..."
    
    # Check if liboqs is available
    if ! command -v oqs-keygen &> /dev/null; then
        print_error "liboqs tools not found. Please install liboqs."
        print_error "Run: export LD_LIBRARY_PATH=$HOME/.local/lib:$LD_LIBRARY_PATH"
        return 1
    fi
    
    # ML-DSA-65 (Primary)
    print_status "Generating ML-DSA-65 user key with liboqs..."
    oqs-keygen -a ML-DSA-65 -o "$SSH_DIR/id_ml_dsa_65"
    
    # Extract public key
    oqs-pubkey -i "$SSH_DIR/id_ml_dsa_65" -o "$SSH_DIR/id_ml_dsa_65.pub"
    
    # SLH-DSA-128s (Backup)
    print_status "Generating SLH-DSA-128s user key with liboqs..."
    oqs-keygen -a SLH-DSA-128s -o "$SSH_DIR/id_slh_dsa_128s"
    
    # Extract public key
    oqs-pubkey -i "$SSH_DIR/id_slh_dsa_128s" -o "$SSH_DIR/id_slh_dsa_128s.pub"
    
    print_success "Post-quantum user keys generated using liboqs"
}

# Set proper permissions
set_permissions() {
    print_status "Setting proper permissions..."
    
    # Private keys: 600 (read/write for owner only)
    chmod 600 "$SSH_DIR"/id_* 2>/dev/null || true
    
    # Public keys: 644 (readable by all)
    chmod 644 "$SSH_DIR"/id_*.pub 2>/dev/null || true
    
    print_success "Key permissions set correctly"
}

# Verify generated keys
verify_keys() {
    print_status "Verifying generated keys..."
    
    echo ""
    echo "🔑 Generated SSH User Keys:"
    echo "=========================="
    
    for key_file in "$SSH_DIR"/id_*.pub; do
        if [[ -f "$key_file" ]]; then
            key_info=$(ssh-keygen -l -f "$key_file" 2>/dev/null)
            key_type=$(echo "$key_info" | awk '{print $4}' | tr -d '()')
            key_bits=$(echo "$key_info" | awk '{print $1}')
            key_comment=$(echo "$key_info" | awk '{for(i=5;i<=NF;i++) printf $i" "; print ""}')
            
            if [[ "$key_type" =~ (ML-DSA|SLH-DSA|ml-dsa|slh-dsa) ]]; then
                echo "  🛡️  $(basename "$key_file")"
                echo "     Type: $key_type (Post-Quantum)"
                echo "     Bits: $key_bits"
                echo "     Comment: $key_comment"
            else
                echo "  🔑 $(basename "$key_file")"
                echo "     Type: $key_type (Classical)"
                echo "     Bits: $key_bits"
            fi
            echo ""
        fi
    done
}

# Generate SSH client configuration
generate_ssh_config() {
    print_status "Generating SSH client configuration..."
    
    config_file="$SSH_DIR/config_pq_template"
    
    cat > "$config_file" << EOF
# SSH Post-Quantum Client Configuration Template
# Generated by Quantum Shield on $(date)
# Copy relevant sections to ~/.ssh/config

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
    IdentityFile ~/.ssh/id_ed25519
    
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
    StrictHostKeyChecking no
EOF
    
    # Create separate known_hosts for PQ
    touch "$SSH_DIR/known_hosts_pq"
    chmod 644 "$SSH_DIR/known_hosts_pq"
    
    print_success "SSH client configuration template saved to $config_file"
}

# Display usage instructions
display_instructions() {
    echo ""
    print_success "🎉 Post-quantum SSH user key generation complete!"
    echo ""
    echo "📋 Your New Post-Quantum Keys:"
    
    if [[ -f "$SSH_DIR/id_ml_dsa_65.pub" ]]; then
        echo "  Primary: $SSH_DIR/id_ml_dsa_65.pub"
    fi
    
    if [[ -f "$SSH_DIR/id_slh_dsa_128s.pub" ]]; then
        echo "  Backup:  $SSH_DIR/id_slh_dsa_128s.pub"
    fi
    
    echo ""
    echo "🚀 Next Steps:"
    echo ""
    echo "1. Copy public key to servers:"
    if [[ -f "$SSH_DIR/id_ml_dsa_65.pub" ]]; then
        echo "   ssh-copy-id -i $SSH_DIR/id_ml_dsa_65.pub user@server"
    fi
    echo ""
    
    echo "2. Manually add to authorized_keys (if ssh-copy-id not available):"
    if [[ -f "$SSH_DIR/id_ml_dsa_65.pub" ]]; then
        echo "   cat $SSH_DIR/id_ml_dsa_65.pub"
        echo "   # Copy output and append to ~/.ssh/authorized_keys on target server"
    fi
    echo ""
    
    echo "3. Update your SSH client configuration:"
    echo "   cp $SSH_DIR/config_pq_template ~/.ssh/config"
    echo "   # Edit as needed for your environment"
    echo ""
    
    echo "4. Test post-quantum connection:"
    echo "   ssh -v user@server"
    echo "   # Look for 'ml-dsa-65' or 'ml-kem' in verbose output"
    echo ""
    
    echo "📚 Documentation:"
    echo "   docs/SSH_POST_QUANTUM_GUIDE.md - Complete implementation guide"
    echo ""
    
    echo "⚠️  Important Notes:"
    echo "   - Keep classical keys as backup during migration"
    echo "   - Verify servers support post-quantum algorithms"
    echo "   - Update authorized_keys on all target servers"
    echo "   - Test connections before relying on PQ keys"
}

# Interactive key type selection
select_key_types() {
    echo ""
    print_status "Select which post-quantum key types to generate:"
    echo ""
    echo "1) ML-DSA-65 only (recommended for most users)"
    echo "2) ML-DSA-65 + SLH-DSA-128s (high security environments)"
    echo "3) Custom selection"
    echo ""
    
    while true; do
        read -p "Choose option [1-3]: " choice
        case $choice in
            1)
                GENERATE_ML_DSA=true
                GENERATE_SLH_DSA=false
                break
                ;;
            2)
                GENERATE_ML_DSA=true
                GENERATE_SLH_DSA=true
                break
                ;;
            3)
                echo ""
                read -p "Generate ML-DSA-65 key? [Y/n]: " -n 1 -r
                echo ""
                [[ $REPLY =~ ^[Nn]$ ]] && GENERATE_ML_DSA=false || GENERATE_ML_DSA=true
                
                read -p "Generate SLH-DSA-128s key? [y/N]: " -n 1 -r
                echo ""
                [[ $REPLY =~ ^[Yy]$ ]] && GENERATE_SLH_DSA=true || GENERATE_SLH_DSA=false
                break
                ;;
            *)
                print_error "Invalid option. Please choose 1, 2, or 3."
                ;;
        esac
    done
}

# Main execution
main() {
    echo "🛡️  Quantum Shield - SSH User Key Generator"
    echo "=========================================="
    echo ""
    
    # Setup and checks
    setup_ssh_directory
    check_ssh_support
    
    # Key type selection
    select_key_types
    
    if [[ "$GENERATE_ML_DSA" == false && "$GENERATE_SLH_DSA" == false ]]; then
        print_status "No keys selected for generation. Exiting."
        exit 0
    fi
    
    # Backup existing keys
    backup_existing_keys
    
    echo ""
    print_warning "About to generate post-quantum SSH user keys."
    print_status "This will create new key files in $SSH_DIR"
    echo ""
    read -p "Do you want to continue? [Y/n]: " -n 1 -r
    echo ""
    
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        print_status "Operation cancelled by user"
        exit 0
    fi
    
    # Generate keys
    if [[ "$PQ_KEY_SUPPORT" == true ]]; then
        # Use OpenSSH if PQ support detected
        if [[ "$GENERATE_ML_DSA" == true ]]; then
            ssh-keygen -t ml-dsa-65 -f "$SSH_DIR/id_ml_dsa_65" -N "" -C "$USERNAME@$HOSTNAME-ml-dsa-65-$DATE"
        fi
        
        if [[ "$GENERATE_SLH_DSA" == true ]]; then
            ssh-keygen -t slh-dsa-128s -f "$SSH_DIR/id_slh_dsa_128s" -N "" -C "$USERNAME@$HOSTNAME-slh-dsa-128s-$DATE" || print_warning "SLH-DSA generation failed, continuing..."
        fi
    else
        # Fallback to liboqs
        print_warning "Using liboqs fallback method..."
        generate_pq_keys_liboqs || {
            print_error "Failed to generate keys with liboqs"
            exit 1
        }
    fi
    
    set_permissions
    verify_keys
    generate_ssh_config
    display_instructions
}

# Execute main function
main "$@"