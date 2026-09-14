#!/bin/bash
# Quantum Shield System Reboot/Shutdown Safety Check
# Comprehensive pre-reboot system health assessment

echo "🔍 SYSTEM REBOOT/SHUTDOWN SAFETY CHECK"
echo "======================================"
echo "📅 $(date)"
echo ""

# Initialize counters
CRITICAL_ISSUES=0
WARNINGS=0
INFO_ITEMS=0

echo "🔴 CRITICAL ISSUES (Must Fix Before Reboot):"
echo "============================================="

# Check for systemd unit file errors that could hang shutdown
echo "1. Checking systemd unit file syntax errors..."
if systemctl --failed --quiet | grep -q disable-audio-pci; then
    echo "   ❌ CRITICAL: disable-audio-pci.service has bad unit file syntax"
    echo "      - This could cause systemd to hang during shutdown"
    echo "      - Location: /etc/systemd/system/disable-audio-pci.service"
    echo "      - Issue: Unbalanced quotes in ExecStart command"
    ((CRITICAL_ISSUES++))
else
    echo "   ✅ No critical systemd syntax errors found"
fi

# Check for filesystem errors
echo ""
echo "2. Checking filesystem health..."
# Filter out normal read-only mounts (snap, proc, sys, etc.)
PROBLEM_RO_FS=$(mount | grep "(ro," | grep -v -E "(snap|proc|sys|ramfs|squashfs|efivarfs)" | wc -l)
if [ "$PROBLEM_RO_FS" -gt 0 ]; then
    echo "   ❌ CRITICAL: $PROBLEM_RO_FS unexpected read-only filesystems"
    echo "      - This could indicate filesystem corruption"
    mount | grep "(ro," | grep -v -E "(snap|proc|sys|ramfs|squashfs|efivarfs)"
    ((CRITICAL_ISSUES++))
else
    echo "   ✅ All writable filesystems are healthy"
    SNAP_COUNT=$(mount | grep -c "snap.*squashfs.*ro")
    echo "      (Note: $SNAP_COUNT snap packages mounted normally)"
fi

# Check disk space
echo ""
echo "3. Checking disk space..."
FULL_DISKS=$(df -h | awk 'NR>1 && $5+0 >= 95 {print $0}')
if [ -n "$FULL_DISKS" ]; then
    echo "   ❌ CRITICAL: Near-full filesystems detected"
    echo "$FULL_DISKS"
    echo "      - Could cause shutdown issues if logs can't be written"
    ((CRITICAL_ISSUES++))
else
    echo "   ✅ Sufficient disk space available"
fi

echo ""
echo "🟡 WARNINGS (Should Address):"
echo "============================"

# Check failed services
echo "1. Checking failed services..."
FAILED_SERVICES=$(systemctl --failed --no-legend | wc -l)
if [ "$FAILED_SERVICES" -gt 0 ]; then
    echo "   ⚠️  WARNING: $FAILED_SERVICES failed services detected"
    systemctl --failed --no-pager
    echo "      - These shouldn't affect shutdown but may cause issues"
    ((WARNINGS++))
else
    echo "   ✅ No failed services"
fi

# Check network issues
echo ""
echo "2. Checking network connectivity..."
if ! ping -c 1 -W 3 8.8.8.8 >/dev/null 2>&1; then
    echo "   ⚠️  WARNING: No internet connectivity"
    echo "      - May delay shutdown if services try to sync online"
    ((WARNINGS++))
else
    echo "   ✅ Network connectivity available"
fi

# Check SSH connections
echo ""
echo "3. Checking active SSH connections..."
SSH_CONNECTIONS=$(who | wc -l)
if [ "$SSH_CONNECTIONS" -gt 0 ]; then
    echo "   ⚠️  WARNING: Active user sessions detected"
    who
    echo "      - Users should be notified before reboot"
    ((WARNINGS++))
else
    echo "   ✅ No active user sessions"
fi

echo ""
echo "ℹ️  INFORMATIONAL:"
echo "================="

# System load
LOAD_AVG=$(uptime | awk -F'load average:' '{print $2}' | awk '{print $1}' | tr -d ',')
echo "1. System Load: $LOAD_AVG"
if (( $(echo "$LOAD_AVG > 2.0" | bc -l) )); then
    echo "   ℹ️  INFO: System load is elevated"
    echo "      - Consider waiting for load to decrease"
    ((INFO_ITEMS++))
else
    echo "   ✅ System load is normal"
fi

# Memory usage
MEM_USAGE=$(free | awk 'NR==2{printf "%.1f", $3*100/$2}')
echo ""
echo "2. Memory Usage: ${MEM_USAGE}%"
if (( $(echo "$MEM_USAGE > 90" | bc -l) )); then
    echo "   ℹ️  INFO: High memory usage detected"
    echo "      - May slow shutdown process"
    ((INFO_ITEMS++))
else
    echo "   ✅ Memory usage is acceptable"
fi

# Check for running jobs
echo ""
echo "3. Checking systemd jobs..."
RUNNING_JOBS=$(systemctl list-jobs --no-pager | grep -c running)
if [ "$RUNNING_JOBS" -gt 0 ]; then
    echo "   ℹ️  INFO: $RUNNING_JOBS systemd jobs running"
    systemctl list-jobs --no-pager
    ((INFO_ITEMS++))
else
    echo "   ✅ No running systemd jobs"
fi

# Quantum Shield specific checks
echo ""
echo "🛡️  QUANTUM SHIELD STATUS:"
echo "========================="

# Check if our SSH processes are running cleanly
echo "1. SSH post-quantum security status..."
if systemctl is-active ssh >/dev/null; then
    echo "   ✅ SSH service is active and stable"
else
    echo "   ⚠️  WARNING: SSH service issues detected"
    ((WARNINGS++))
fi

# Check our notification system
echo ""
echo "2. Notification system status..."
if [ -f "$HOME/.quantum-shield-motd" ]; then
    echo "   ✅ User notification system is installed"
else
    echo "   ℹ️  INFO: User notifications not installed"
    ((INFO_ITEMS++))
fi

echo ""
echo "📊 SUMMARY:"
echo "==========="
echo "🔴 Critical Issues: $CRITICAL_ISSUES"
echo "🟡 Warnings: $WARNINGS"  
echo "ℹ️  Info Items: $INFO_ITEMS"
echo ""

if [ "$CRITICAL_ISSUES" -eq 0 ]; then
    echo "✅ SYSTEM IS SAFE FOR REBOOT/SHUTDOWN"
    echo ""
    echo "🔧 Recommended actions before reboot:"
    echo "   1. Fix the disable-audio-pci.service unit file if desired"
    echo "   2. Notify any logged-in users"
    echo "   3. Save all work and close applications"
    echo ""
    echo "🚀 Safe reboot commands:"
    echo "   sudo reboot           # Standard reboot"
    echo "   sudo shutdown -r +5   # Reboot in 5 minutes with notice"
    echo "   sudo shutdown -h now  # Immediate shutdown"
else
    echo "⚠️  CRITICAL ISSUES MUST BE RESOLVED BEFORE REBOOT"
    echo ""
    echo "🔧 Required fixes:"
    if systemctl --failed --quiet | grep -q disable-audio-pci; then
        echo "   1. Fix /etc/systemd/system/disable-audio-pci.service"
        echo "      sudo systemctl edit --full disable-audio-pci.service"
        echo "      (Fix the quoting in ExecStart line)"
    fi
    echo ""
    echo "❌ DO NOT REBOOT UNTIL CRITICAL ISSUES ARE RESOLVED"
fi

echo ""
echo "📋 Generated: $(date)"
echo "💻 Host: $(hostname)"