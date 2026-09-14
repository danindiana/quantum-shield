# Quantum Shield Makefile
#
# Every target below invokes venv/bin/<tool> directly rather than
# `source venv/bin/activate && ...` -- that pattern silently failed on
# any target, always, because `make` runs recipes with /bin/sh (dash on
# Debian/Ubuntu), and `source` is a bash builtin `sh` doesn't have
# ("sh: 1: source: not found", exit 127). Confirmed this session by
# actually running `make test` in a clean environment. Every target had
# been broken since this Makefile was first written.

.PHONY: help venv install test test-cli clean benchmark docs security status server pki-demo

VENV := venv
PY := $(VENV)/bin/python3
PYTEST := $(VENV)/bin/pytest
LIBOQS_LIB := $(HOME)/.local/lib
export LD_LIBRARY_PATH := $(LIBOQS_LIB):$(LD_LIBRARY_PATH)
export OPENSSL_MODULES := $(LIBOQS_LIB)/ossl-modules

help:
	@echo "Quantum Shield - Post-Quantum Cryptography Implementation"
	@echo ""
	@echo "Available commands:"
	@echo "  venv       - Create venv/ and install requirements.txt into it"
	@echo "  test       - Run the full pytest suite (48 tests, needs liboqs built)"
	@echo "  test-cli   - Run quantum_shield.py's own basic self-check (not pytest)"
	@echo "  install    - Install requirements.txt into the existing venv"
	@echo "  clean      - Clean build artifacts"
	@echo "  benchmark  - Run quantum_shield.py's real timing benchmarks"
	@echo "  pki-demo   - Run the PKI certificate verification demo"
	@echo "  docs       - List the actual documentation files in this repo"
	@echo "  security   - Run bandit + safety security scans"
	@echo "  status     - Show project status"
	@echo "  server     - Start the ML-KEM-768 demo listener (see README)"
	@echo ""
	@echo "First-time setup: make venv && make test"

venv:
	@echo "Creating $(VENV)/ and installing requirements.txt..."
	python3 -m venv $(VENV)
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r requirements.txt

install:
	@echo "Installing requirements.txt into $(VENV)/..."
	$(PY) -m pip install -r requirements.txt

test:
	@echo "Running the pytest suite (LD_LIBRARY_PATH=$(LD_LIBRARY_PATH))..."
	$(PYTEST) tests/ -v

test-cli:
	@echo "Running quantum_shield.py's own basic self-check..."
	$(PY) quantum_shield.py test

clean:
	@echo "Cleaning build artifacts..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -rf build/ dist/ *.egg-info/ .pytest_cache/ benchmarks/results/

benchmark:
	@echo "Running real timing benchmarks..."
	$(PY) quantum_shield.py benchmark

pki-demo:
	@echo "Running the PKI certificate verification demo..."
	$(PY) examples/pki_verify_demo.py

docs:
	@echo "Quantum Shield Documentation"
	@echo "  - System Architecture:    docs/SYSTEM_ARCHITECTURE.md"
	@echo "  - Future Directions:      docs/FUTURE_DIRECTIONS.md"
	@echo "  - Research Notes:         docs/RESEARCH_NOTES.md"
	@echo "  - Best Practices Log:     docs/BEST_PRACTICES.md"
	@echo "  - Implementation Plan:    docs/IMPLEMENTATION_PLAN.md"
	@echo "  - NIST Compliance:        docs/NIST_COMPLIANCE.md"
	@echo "  - Security Architecture:  docs/SECURITY_ARCHITECTURE.md"
	@echo "  - Deployment Guide:       docs/DEPLOYMENT.md"
	@echo "  - SSH PQ Guide:           docs/SSH_POST_QUANTUM_GUIDE.md"
	@echo "  - TLS/HTTPS PQ Research:  docs/tls/TLS_PQ_RESEARCH.md"
	@echo "  - Progress log:           PROGRESS.md"
	@echo "  - Diagrams (12):          diagrams/"

security:
	@echo "Running security scans..."
	$(PY) -m bandit -r src/ || true
	$(PY) -m safety check || true

status:
	@echo "Quantum Shield Status"
	$(PY) quantum_shield.py status

server:
	@echo "Starting the ML-KEM-768 demo listener..."
	$(PY) quantum_shield.py server
