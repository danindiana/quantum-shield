#!/bin/bash
# Quantum Shield - Quick Status Viewer
# Shows links to all important documentation

echo ""
echo "🛡️  ═══════════════════════════════════════════════════════════"
echo "   QUANTUM SHIELD - QUICK STATUS & DOCUMENTATION"
echo "   ═══════════════════════════════════════════════════════════"
echo ""

PROJECT_DIR="$HOME/programs/quantum-shield"

# Check if we're in the project directory
if [ ! -d "$PROJECT_DIR" ]; then
    echo "❌ Error: Project directory not found: $PROJECT_DIR"
    exit 1
fi

cd "$PROJECT_DIR"

echo "📊 PROJECT OVERVIEW:"
echo "   Location: $PROJECT_DIR"
echo ""

# Latest Session Summary
if [ -L "LATEST_SESSION.md" ]; then
    LATEST=$(readlink LATEST_SESSION.md)
    echo "📅 LATEST SESSION SUMMARY:"
    echo "   $LATEST"
    echo "   View: cat $PROJECT_DIR/$LATEST"
    echo "   Link: $PROJECT_DIR/LATEST_SESSION.md"
    echo ""
fi

# Status Documents
echo "📋 STATUS DOCUMENTS:"
echo "   📊 Overall Status:    OVERALL_SYSTEM_STATUS.md"
echo "   🔐 TLS/HTTPS Status:  TLS_IMPLEMENTATION_STATUS.md"
echo "   🛡️  SSH Status:        PROJECT_STATUS.md"
echo ""

# Quick Deploy Guides
echo "🚀 QUICK DEPLOY GUIDES:"
echo "   🔑 SSH Keys:          SSH_QUICK_DEPLOY.md"
echo "   🔐 TLS Certs:         docs/tls/TLS_PQ_RESEARCH.md"
echo ""

# Session Archive
echo "📚 SESSION SUMMARIES:"
SESSION_COUNT=$(ls -1 SESSION_SUMMARY_*.md 2>/dev/null | wc -l)
if [ $SESSION_COUNT -gt 0 ]; then
    echo "   Found $SESSION_COUNT session(s):"
    ls -1 SESSION_SUMMARY_*.md | while read file; do
        SIZE=$(du -h "$file" | cut -f1)
        echo "   • $file ($SIZE)"
    done
else
    echo "   No session summaries found"
fi
echo ""

# Git Status
echo "🔄 GIT STATUS:"
COMMITS=$(git log --oneline | wc -l 2>/dev/null || echo "0")
LATEST_COMMIT=$(git log --oneline -1 2>/dev/null || echo "Not available")
echo "   Total Commits: $COMMITS"
echo "   Latest: $LATEST_COMMIT"
echo ""

# Progress Check
echo "📈 QUICK PROGRESS CHECK:"
if [ -f "OVERALL_SYSTEM_STATUS.md" ]; then
    PROGRESS=$(grep -m 1 "Overall Progress:" OVERALL_SYSTEM_STATUS.md | grep -oP '\d+%' || echo "Unknown")
    PHASE=$(grep -m 1 "Project Phase:" OVERALL_SYSTEM_STATUS.md | cut -d: -f2 | xargs || echo "Unknown")
    echo "   Progress: $PROGRESS"
    echo "   Phase: $PHASE"
else
    echo "   Status file not found"
fi
echo ""

# Working Features
echo "✅ WORKING FEATURES:"
echo "   • SSH Post-Quantum Security"
echo "   • PQ Key Generation (ML-DSA, Falcon)"
echo "   • PQ Certificate Generation"
echo "   • OQS-Provider Integration"
echo "   • System MOTD with Updates"
echo ""

# Quick Commands
echo "⚡ QUICK COMMANDS:"
echo "   View latest session:   cat LATEST_SESSION.md | less"
echo "   Overall status:        cat OVERALL_SYSTEM_STATUS.md | less"
echo "   Generate SSH key:      python3 simple_ssh_keygen.py"
echo "   Test PQ TLS:           python3 test_pq_tls.py"
echo "   Announce update:       ./scripts/announce_session_summary.sh DATE"
echo ""

# System Integration
echo "🔗 SYSTEM INTEGRATION:"
echo "   MOTD File:     /etc/update-motd.d/90-quantum-shield-ssh"
echo "   Test MOTD:     sudo run-parts /etc/update-motd.d/"
echo "   Wall Announce: ./scripts/announce_session_summary.sh"
echo ""

echo "   ═══════════════════════════════════════════════════════════"
echo "   Use: ./scripts/quick_status.sh to view this anytime"
echo "   ═══════════════════════════════════════════════════════════"
echo ""
