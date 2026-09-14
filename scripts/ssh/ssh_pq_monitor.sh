#!/bin/bash
# ssh_pq_monitor.sh - SSH Post-Quantum Algorithm Usage Monitor
# Part of Quantum Shield Project

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
AUTH_LOG="/var/log/auth.log"
SSHD_LOG="/var/log/sshd.log"
SECURE_LOG="/var/log/secure"
REPORT_DIR="/var/log/quantum-shield/ssh"
DATE=$(date +%Y%m%d_%H%M%S)

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

# Determine which log file to use
detect_log_file() {
    if [[ -f "$AUTH_LOG" && -r "$AUTH_LOG" ]]; then
        LOG_FILE="$AUTH_LOG"
    elif [[ -f "$SSHD_LOG" && -r "$SSHD_LOG" ]]; then
        LOG_FILE="$SSHD_LOG"
    elif [[ -f "$SECURE_LOG" && -r "$SECURE_LOG" ]]; then
        LOG_FILE="$SECURE_LOG"
    else
        print_error "Cannot find readable SSH log file"
        print_error "Checked: $AUTH_LOG, $SSHD_LOG, $SECURE_LOG"
        exit 1
    fi
    
    print_status "Using log file: $LOG_FILE"
}

# Create report directory
setup_reporting() {
    if [[ ! -d "$REPORT_DIR" ]]; then
        sudo mkdir -p "$REPORT_DIR" 2>/dev/null || {
            REPORT_DIR="/tmp/quantum-shield-ssh"
            mkdir -p "$REPORT_DIR"
            print_warning "Using temporary report directory: $REPORT_DIR"
        }
    fi
}

# Analyze key exchange algorithms
analyze_kex_algorithms() {
    print_status "Analyzing Key Exchange Algorithms..."
    
    echo "🔑 Key Exchange Algorithm Usage (Last 24 hours):"
    echo "=============================================="
    
    # Look for key exchange patterns in logs
    kex_analysis=$(grep -E "(kex:|negotiated)" "$LOG_FILE" 2>/dev/null | \
        grep -E "(ml-kem|kyber|hybrid|curve25519|diffie-hellman)" | \
        tail -100 | \
        awk '{print $NF}' | \
        sort | uniq -c | sort -nr)
    
    if [[ -n "$kex_analysis" ]]; then
        while read -r count algorithm; do
            if [[ "$algorithm" =~ (ml-kem|kyber) ]]; then
                echo -e "  🛡️  $count connections using $algorithm (Post-Quantum)"
            elif [[ "$algorithm" =~ hybrid ]]; then
                echo -e "  🔄 $count connections using $algorithm (Hybrid)"  
            else
                echo -e "  ⚠️  $count connections using $algorithm (Classical)"
            fi
        done <<< "$kex_analysis"
    else
        print_warning "No key exchange algorithm data found in logs"
    fi
    
    echo ""
}

# Analyze host key algorithms
analyze_host_keys() {
    print_status "Analyzing Host Key Algorithms..."
    
    echo "🔐 Host Key Algorithm Usage (Last 24 hours):"
    echo "==========================================="
    
    # Look for host key patterns
    hostkey_analysis=$(grep -E "(hostkey:|Server host key)" "$LOG_FILE" 2>/dev/null | \
        grep -E "(ml-dsa|dilithium|slh-dsa|sphincs|ssh-ed25519|ssh-rsa|ecdsa)" | \
        tail -100 | \
        awk '{print $NF}' | \
        sort | uniq -c | sort -nr)
    
    if [[ -n "$hostkey_analysis" ]]; then
        while read -r count algorithm; do
            if [[ "$algorithm" =~ (ml-dsa|dilithium|slh-dsa|sphincs) ]]; then
                echo -e "  🛡️  $count connections using $algorithm (Post-Quantum)"
            elif [[ "$algorithm" =~ ssh-ed25519 ]]; then
                echo -e "  🔑 $count connections using $algorithm (Modern Classical)"
            else
                echo -e "  ⚠️  $count connections using $algorithm (Legacy Classical)"
            fi
        done <<< "$hostkey_analysis"
    else
        print_warning "No host key algorithm data found in logs"
    fi
    
    echo ""
}

# Analyze authentication methods
analyze_authentication() {
    print_status "Analyzing Authentication Methods..."
    
    echo "🔓 Authentication Method Usage (Last 24 hours):"
    echo "============================================="
    
    # Successful authentications
    auth_success=$(grep "Accepted publickey" "$LOG_FILE" 2>/dev/null | \
        tail -100 | \
        grep -E "(ML-DSA|SLH-DSA|ssh-ed25519|ssh-rsa)" | \
        awk '{for(i=1;i<=NF;i++) if($i~/^(ML-DSA|SLH-DSA|ssh-ed25519|ssh-rsa)/) print $i}' | \
        sort | uniq -c | sort -nr)
    
    if [[ -n "$auth_success" ]]; then
        echo "✅ Successful Authentications:"
        while read -r count keytype; do
            if [[ "$keytype" =~ (ML-DSA|SLH-DSA) ]]; then
                echo -e "  🛡️  $count authentications using $keytype (Post-Quantum)"
            else
                echo -e "  🔑 $count authentications using $keytype (Classical)"
            fi
        done <<< "$auth_success"
    else
        print_warning "No authentication data found"
    fi
    
    # Failed authentications
    auth_failures=$(grep -E "(authentication failure|Failed publickey)" "$LOG_FILE" 2>/dev/null | \
        tail -50 | wc -l)
    
    if [[ "$auth_failures" -gt 0 ]]; then
        echo ""
        echo -e "❌ Failed Authentications: $auth_failures"
        
        if [[ "$auth_failures" -gt 10 ]]; then
            print_warning "High number of authentication failures detected"
        fi
    fi
    
    echo ""
}

# Check for security issues
analyze_security_issues() {
    print_status "Analyzing Security Issues..."
    
    echo "🚨 Security Analysis (Last 24 hours):"
    echo "===================================="
    
    # Classical algorithm usage (security risk)
    classical_usage=$(grep -E "(ssh-rsa|ecdsa-sha2|ssh-dss)" "$LOG_FILE" 2>/dev/null | \
        tail -20 | wc -l)
    
    if [[ "$classical_usage" -gt 0 ]]; then
        echo -e "⚠️  Classical Algorithm Usage: $classical_usage instances"
        print_warning "Classical cryptography detected - vulnerable to quantum attacks"
        
        # Show recent classical usage
        echo "   Recent classical algorithm connections:"
        grep -E "(ssh-rsa|ecdsa-sha2|ssh-dss)" "$LOG_FILE" 2>/dev/null | \
            tail -5 | \
            awk '{print "   " $1 " " $2 " " $3 " - " $NF}' || true
    else
        print_success "No classical algorithm usage detected"
    fi
    
    # Connection failures due to algorithm mismatch
    algo_failures=$(grep -E "(no matching|algorithm negotiation failed)" "$LOG_FILE" 2>/dev/null | \
        tail -10 | wc -l)
    
    if [[ "$algo_failures" -gt 0 ]]; then
        echo -e "❌ Algorithm Negotiation Failures: $algo_failures"
        print_warning "Clients may not support post-quantum algorithms"
    else
        print_success "No algorithm negotiation failures"
    fi
    
    # Brute force attempts
    brute_force=$(grep -E "(Invalid user|Failed password)" "$LOG_FILE" 2>/dev/null | \
        tail -50 | wc -l)
    
    if [[ "$brute_force" -gt 5 ]]; then
        echo -e "🔥 Potential Brute Force: $brute_force attempts"
        print_error "High number of invalid login attempts detected"
    fi
    
    echo ""
}

# Performance analysis
analyze_performance() {
    print_status "Analyzing Connection Performance..."
    
    echo "⚡ Performance Metrics:"
    echo "===================="
    
    # Connection establishment times (if available in logs)
    connection_times=$(grep -E "(Connection established|session opened)" "$LOG_FILE" 2>/dev/null | \
        grep -o "time=[0-9]*ms" | \
        awk -F= '{sum+=$2; count++} END {if(count>0) printf "%.1f", sum/count}')
    
    if [[ -n "$connection_times" && "$connection_times" != "0.0" ]]; then
        echo "📊 Average Connection Time: ${connection_times}ms"
        
        if (( $(echo "$connection_times > 1000" | bc -l 2>/dev/null || echo 0) )); then
            print_warning "Connection times exceed 1000ms - performance issue detected"
        fi
    else
        print_status "Connection timing data not available in logs"
    fi
    
    # Active connections
    active_connections=$(ss -tn | grep ":22 " | wc -l 2>/dev/null || echo "N/A")
    echo "🔌 Current Active SSH Connections: $active_connections"
    
    echo ""
}

# Generate usage statistics
generate_statistics() {
    print_status "Generating Usage Statistics..."
    
    echo "📊 Post-Quantum Adoption Statistics:"
    echo "=================================="
    
    # Calculate PQ adoption percentage
    total_connections=$(grep "Accepted publickey\|Connection established" "$LOG_FILE" 2>/dev/null | \
        tail -100 | wc -l)
    
    pq_connections=$(grep -E "(ml-kem|ml-dsa|slh-dsa)" "$LOG_FILE" 2>/dev/null | \
        tail -100 | wc -l)
    
    if [[ "$total_connections" -gt 0 ]]; then
        pq_percentage=$((pq_connections * 100 / total_connections))
        echo "📈 Post-Quantum Adoption: $pq_percentage% ($pq_connections/$total_connections connections)"
        
        if [[ "$pq_percentage" -ge 80 ]]; then
            print_success "Excellent post-quantum adoption rate"
        elif [[ "$pq_percentage" -ge 50 ]]; then
            print_warning "Good post-quantum adoption rate"
        else
            print_error "Low post-quantum adoption rate - migration needed"
        fi
    else
        print_status "Insufficient data for statistics"
    fi
    
    echo ""
}

# Check SSH configuration
check_ssh_configuration() {
    print_status "Checking SSH Configuration..."
    
    echo "⚙️  SSH Configuration Status:"
    echo "============================"
    
    # Check if sshd_config supports PQ algorithms
    if sudo grep -q "ml-dsa\|ml-kem" /etc/ssh/sshd_config 2>/dev/null; then
        print_success "Post-quantum algorithms configured in sshd_config"
    else
        print_warning "Post-quantum algorithms not found in sshd_config"
    fi
    
    # Check if PQ host keys exist
    pq_host_keys_found=false
    for key_type in ml_dsa_65 slh_dsa_128s; do
        if [[ -f "/etc/ssh/ssh_host_${key_type}_key" ]]; then
            print_success "Found PQ host key: ssh_host_${key_type}_key"
            pq_host_keys_found=true
        fi
    done
    
    if [[ "$pq_host_keys_found" == false ]]; then
        print_warning "No post-quantum host keys found"
        print_status "Run: sudo ./scripts/ssh/generate_ssh_host_keys_pq.sh"
    fi
    
    # Check SSH version
    ssh_version=$(ssh -V 2>&1 | head -1)
    echo "📋 SSH Version: $ssh_version"
    
    # Test algorithm support
    if ssh -Q kex 2>/dev/null | grep -q "ml-kem\|kyber"; then
        print_success "ML-KEM support detected"
    else
        print_warning "ML-KEM support not detected"
    fi
    
    if ssh -Q key 2>/dev/null | grep -q "ml-dsa\|dilithium"; then
        print_success "ML-DSA support detected"
    else
        print_warning "ML-DSA support not detected"
    fi
    
    echo ""
}

# Save detailed report
save_detailed_report() {
    print_status "Saving detailed report..."
    
    report_file="$REPORT_DIR/ssh_pq_analysis_$DATE.txt"
    
    {
        echo "Quantum Shield SSH Post-Quantum Analysis Report"
        echo "=============================================="
        echo "Generated: $(date)"
        echo "Log File: $LOG_FILE"
        echo "Report File: $report_file"
        echo ""
        
        echo "=== KEY EXCHANGE ALGORITHMS ==="
        analyze_kex_algorithms
        
        echo "=== HOST KEY ALGORITHMS ==="
        analyze_host_keys
        
        echo "=== AUTHENTICATION METHODS ==="
        analyze_authentication
        
        echo "=== SECURITY ISSUES ==="
        analyze_security_issues
        
        echo "=== PERFORMANCE METRICS ==="
        analyze_performance
        
        echo "=== USAGE STATISTICS ==="
        generate_statistics
        
        echo "=== CONFIGURATION STATUS ==="
        check_ssh_configuration
        
        echo "=== RAW LOG SAMPLE (Last 20 SSH entries) ==="
        grep -E "(sshd|ssh)" "$LOG_FILE" 2>/dev/null | tail -20 || echo "No SSH entries found"
        
    } > "$report_file" 2>&1
    
    print_success "Detailed report saved to: $report_file"
}

# Generate alerts if needed
generate_alerts() {
    print_status "Checking for alert conditions..."
    
    alerts_found=false
    
    # High classical algorithm usage
    classical_count=$(grep -E "(ssh-rsa|ecdsa-sha2)" "$LOG_FILE" 2>/dev/null | \
        tail -50 | wc -l)
    
    if [[ "$classical_count" -gt 10 ]]; then
        print_error "ALERT: High classical algorithm usage ($classical_count instances)"
        alerts_found=true
    fi
    
    # Algorithm negotiation failures
    nego_failures=$(grep -E "(no matching|algorithm negotiation)" "$LOG_FILE" 2>/dev/null | \
        tail -10 | wc -l)
    
    if [[ "$nego_failures" -gt 5 ]]; then
        print_error "ALERT: Multiple algorithm negotiation failures ($nego_failures)"
        alerts_found=true
    fi
    
    # Authentication failures
    auth_failures=$(grep -E "(authentication failure|Failed)" "$LOG_FILE" 2>/dev/null | \
        tail -30 | wc -l)
    
    if [[ "$auth_failures" -gt 20 ]]; then
        print_error "ALERT: High authentication failure rate ($auth_failures)"
        alerts_found=true
    fi
    
    if [[ "$alerts_found" == false ]]; then
        print_success "No alerts detected"
    fi
    
    echo ""
}

# Real-time monitoring mode
realtime_monitor() {
    print_status "Starting real-time SSH monitoring (Press Ctrl+C to stop)..."
    
    echo "🔍 Monitoring SSH connections for post-quantum algorithm usage..."
    echo "================================================================"
    
    tail -f "$LOG_FILE" | while read -r line; do
        if echo "$line" | grep -q "sshd"; then
            timestamp=$(echo "$line" | awk '{print $1 " " $2 " " $3}')
            
            if echo "$line" | grep -qE "(ml-kem|ml-dsa|slh-dsa)"; then
                echo -e "$timestamp: ${GREEN}[PQ]${NC} $line"
            elif echo "$line" | grep -qE "(ssh-rsa|ecdsa-sha2|ssh-dss)"; then
                echo -e "$timestamp: ${RED}[CLASSICAL]${NC} $line"
            elif echo "$line" | grep -q "Accepted publickey"; then
                echo -e "$timestamp: ${BLUE}[AUTH]${NC} $line"
            elif echo "$line" | grep -qE "(Failed|Invalid)"; then
                echo -e "$timestamp: ${YELLOW}[FAIL]${NC} $line"
            fi
        fi
    done
}

# Display help
show_help() {
    echo "Quantum Shield SSH Post-Quantum Monitor"
    echo "======================================"
    echo ""
    echo "Usage: $0 [OPTION]"
    echo ""
    echo "Options:"
    echo "  -a, --analyze     Perform complete analysis (default)"
    echo "  -r, --realtime    Start real-time monitoring"
    echo "  -s, --stats       Show statistics only"
    echo "  -c, --config      Check configuration only"
    echo "  -h, --help        Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                # Run complete analysis"
    echo "  $0 --realtime     # Monitor connections in real-time"
    echo "  $0 --stats        # Show adoption statistics"
    echo ""
}

# Main execution
main() {
    # Parse command line options
    case "${1:-}" in
        -r|--realtime)
            detect_log_file
            realtime_monitor
            exit 0
            ;;
        -s|--stats)
            detect_log_file
            generate_statistics
            exit 0
            ;;
        -c|--config)
            check_ssh_configuration
            exit 0
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        -a|--analyze|"")
            # Default: full analysis
            ;;
        *)
            print_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
    
    echo "🛡️  Quantum Shield SSH Post-Quantum Monitor"
    echo "=========================================="
    echo ""
    
    detect_log_file
    setup_reporting
    
    # Run complete analysis
    analyze_kex_algorithms
    analyze_host_keys  
    analyze_authentication
    analyze_security_issues
    analyze_performance
    generate_statistics
    check_ssh_configuration
    generate_alerts
    
    # Save detailed report
    save_detailed_report
    
    echo ""
    print_success "🎉 SSH Post-Quantum Analysis Complete!"
    echo ""
    echo "📋 Summary:"
    echo "- Detailed report saved to: $REPORT_DIR"
    echo "- Run with --realtime for live monitoring"
    echo "- Run with --stats for quick statistics"
    echo ""
    echo "🚀 Next Steps:"
    echo "1. Review any security warnings above"
    echo "2. Update configurations to prefer PQ algorithms"
    echo "3. Migrate remaining classical connections"
    echo "4. Set up automated monitoring with cron"
    echo ""
    echo "📚 Documentation: docs/SSH_POST_QUANTUM_GUIDE.md"
}

# Execute main function
main "$@"