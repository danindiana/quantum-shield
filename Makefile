# Quantum Shield Makefile

.PHONY: help setup test clean install benchmark docs security

help:
	@echo "🛡️  Quantum Shield - Post-Quantum Cryptography Implementation"
	@echo ""
	@echo "Available commands:"
	@echo "  setup     - Run initial project setup"
	@echo "  test      - Run all tests"
	@echo "  install   - Install in development mode"  
	@echo "  clean     - Clean build artifacts"
	@echo "  benchmark - Run performance benchmarks"
	@echo "  docs      - Generate documentation"
	@echo "  security  - Run security scans"
	@echo "  status    - Show project status"

setup:
	@echo "🛡️  Setting up Quantum Shield..."
	source venv/bin/activate && ./quantum_shield.py setup

test:
	@echo "🧪 Running Quantum Shield tests..."
	source venv/bin/activate && ./quantum_shield.py test

install:
	@echo "📦 Installing Quantum Shield in development mode..."
	source venv/bin/activate && pip install -e .

clean:
	@echo "🧹 Cleaning build artifacts..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	rm -rf build/ dist/ *.egg-info/

benchmark:
	@echo "🚀 Running performance benchmarks..."
	source venv/bin/activate && ./quantum_shield.py benchmark

docs:
	@echo "📚 Quantum Shield Documentation"
	@echo "  - Implementation Plan: docs/IMPLEMENTATION_PLAN.md"
	@echo "  - NIST Compliance: docs/NIST_COMPLIANCE.md"
	@echo "  - Security Architecture: docs/SECURITY_ARCHITECTURE.md"
	@echo "  - Deployment Guide: docs/DEPLOYMENT.md"
	@echo "  - Quick Reference: QUICK_REFERENCE.md"
	@echo "  - Project Status: PROJECT_STATUS.md"

security:
	@echo "🔍 Running security scans..."
	source venv/bin/activate && bandit -r src/ || echo "No source files to scan yet"
	source venv/bin/activate && safety check

status:
	@echo "📊 Quantum Shield Status"
	source venv/bin/activate && ./quantum_shield.py status

server:
	@echo "🌐 Starting Quantum Shield server..."
	source venv/bin/activate && ./quantum_shield.py server