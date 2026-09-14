<p align="center">
  <img src="diagrams/logo.svg" alt="quantum-shield" width="640">
</p>

<p align="center">
  <img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-39ffe0?style=for-the-badge&labelColor=0b0f14">
  <img alt="Python 3.10+" src="https://img.shields.io/badge/python-3.10%2B-8f5cff?style=for-the-badge&labelColor=0b0f14">
  <img alt="Wraps liboqs" src="https://img.shields.io/badge/crypto-liboqs%20(Open%20Quantum%20Safe)-ffcb47?style=for-the-badge&labelColor=0b0f14">
  <img alt="Not audited" src="https://img.shields.io/badge/status-EXPERIMENTAL%2C%20NOT%20AUDITED-ff2ec4?style=for-the-badge&labelColor=0b0f14">
</p>
<p align="center">
  <img alt="FIPS 203" src="https://img.shields.io/badge/FIPS%20203-ML--KEM-39ffe0?style=flat-square&labelColor=0b0f14">
  <img alt="FIPS 204" src="https://img.shields.io/badge/FIPS%20204-ML--DSA-39ffe0?style=flat-square&labelColor=0b0f14">
  <img alt="Tests" src="https://img.shields.io/badge/tests-58%20passing-8f5cff?style=flat-square&labelColor=0b0f14">
  <img alt="Diagrams" src="https://img.shields.io/badge/diagrams-14-8f5cff?style=flat-square&labelColor=0b0f14">
  <img alt="PRs welcome" src="https://img.shields.io/badge/PRs-welcome-39ffe0?style=flat-square&labelColor=0b0f14">
  <a href="https://github.com/danindiana/quantum-shield/commits/master"><img alt="Last commit" src="https://img.shields.io/github/last-commit/danindiana/quantum-shield?style=flat-square&labelColor=0b0f14"></a>
  <a href="https://github.com/danindiana/quantum-shield/actions/workflows/tests.yml"><img alt="Tests" src="https://github.com/danindiana/quantum-shield/actions/workflows/tests.yml/badge.svg"></a>
</p>

---

# Quantum Shield

A post-quantum cryptography project: real key encapsulation and digital
signatures via [liboqs](https://github.com/open-quantum-safe/liboqs) (Open
Quantum Safe's C implementation of the NIST-standardized algorithms), plus
working post-quantum SSH key generation and TLS certificate issuance
through `openssl` + `oqs-provider`.

> ⚠️ **This is an experimental personal project. It has not been
> independently audited. Do not use it to protect anything you actually
> care about.** It calls into liboqs (which is itself under active
> development and not FIPS-certified) — it does not implement any
> cryptographic primitives of its own. Treat everything here as a learning
> and prototyping tool, not production security infrastructure.

## What actually works today

- **`src/algorithms/kem.py`** — `MLKEM768`: real keypair generation,
  encapsulation, and decapsulation via liboqs's `OQS_KEM` C API. Sizes
  (public key, secret key, ciphertext, shared secret) are read from the
  struct liboqs returns at runtime — not hardcoded.
- **`src/algorithms/signature.py`** — `Signature` (generic, takes any
  algorithm liboqs supports) plus `MLDSA65`, `Falcon512`, and
  `SLHDSA128s` convenience subclasses: real keypair generation, signing,
  and verification via liboqs's `OQS_SIG` C API, same struct-read
  approach. SLH-DSA was believed disabled earlier this session — it
  wasn't; the identifier string was wrong (see
  `docs/RESEARCH_NOTES.md`'s correction). Its sign is ~6000x slower than
  ML-DSA-65's but far more consistent (low variance vs. ML-DSA/Falcon's
  rejection-sampling-driven variance) — a real measured contrast, not a
  guess.
- **`simple_ssh_keygen.py`** — generates real post-quantum SSH keypairs
  (ML-DSA-65 or Falcon-512) using the library above. Pass `--encrypt` to
  store the private key encrypted at rest (via `KeyStore`, passphrase
  prompted twice) instead of writing it as a plaintext file.
- **`test_pq_tls.py`** — generates real post-quantum TLS certificates by
  shelling out to `openssl` with the `oqs-provider` module loaded.
- **`quantum_shield.py benchmark`** — real timings (not simulated) for
  keypair/encaps/decaps/sign/verify, reported as mean/stddev/min/max/p95
  per operation (not a single aggregate average), written to
  `benchmarks/results/<timestamp>.json`. Surfaced a real signal doing
  this: ML-DSA-65 sign and Falcon-512 keypair both show high variance,
  consistent with their rejection-sampling internals — see
  `docs/RESEARCH_NOTES.md`.
- **`quantum_shield.py server` + `examples/kem_demo_client.py`** — a real
  ML-KEM-768 key exchange over an actual TCP socket: the server generates
  a keypair, sends the public key, the client encapsulates and sends back
  a ciphertext, the server decapsulates — both sides print the identical
  shared secret. **This is a protocol demo, not a security protocol**: no
  authentication of the server's public key, no transport encryption, no
  replay protection. See [diagram 09](diagrams/09-demo-server-client.svg).
- **`src/kms/store.py`** — `KeyStore`: passphrase-encrypted at-rest
  storage for any keypair from the library above (AES-256-GCM, scrypt
  KDF, key name bound as AEAD associated data), wired into
  `simple_ssh_keygen.py --encrypt` (see above). Includes **key rotation**
  (`rotate_key()` archives the old generation, activates a new one under
  a possibly-different passphrase) and **revocation**
  (`revoke_key()` + `load_keypair(..., allow_revoked=True)`). See
  [diagram 10](diagrams/10-kms-store.svg),
  [diagram 11](diagrams/11-kms-rotation-revocation.svg),
  `examples/kms_demo.py`, and `examples/kms_rotation_demo.py`.
- **`src/pki/certs.py`** — verifies a real PQ-signed X.509 certificate's
  signature: parses structure via `cryptography`'s X.509 parser,
  extracts the raw public key from `SubjectPublicKeyInfo` via a small
  generic DER TLV walker, then checks the signature via
  `src/algorithms/signature.py`. **Never builds or encodes a
  certificate** — that stays delegated to `openssl`+`oqs-provider`
  (`test_pq_tls.py`); this only reads DER that openssl already produced
  correctly. `verify_chain()` checks a real leaf cert against a
  separate issuer cert (not just self-signed) — verified against a real
  2-level chain (`openssl x509 -req -CA`) plus a real negative control
  (an unrelated CA correctly fails). Verified against real ML-DSA-65 and
  Falcon-512 certs generated fresh in the test suite. See
  [diagram 12](diagrams/12-pki-cert-verify.svg),
  [diagram 14](diagrams/14-pki-chain-verify.svg), and
  `examples/pki_verify_demo.py`.
- **`src/protocols/tls/demo.py`** — a real TLS 1.3 handshake using
  ML-KEM-768 for key exchange, via `openssl s_server`/`s_client` +
  `oqs-provider`. Authenticated with a **classical** ECDSA certificate,
  not a PQ-signed one — checked this session that authenticating a live
  TLS connection with a PQ-signed certificate needs **OpenSSL 3.2+**
  (this project has 3.0.2, both locally and in CI); generating such a
  certificate works fine on 3.0 (that's what `test_pq_tls.py`/
  `src/pki/certs.py` already do), loading one into `s_server` for a
  live handshake does not. Proof the PQ group was used is by
  construction (both sides offer exactly one, identical group) and
  verified with a real negative control — mismatched groups fail the
  handshake outright. See [diagram 13](diagrams/13-tls-pq-handshake.svg)
  and `examples/tls_demo.py`.
- **58 passing tests** (`tests/test_kem.py`, `tests/test_signature.py`,
  `tests/test_setup.py`, `tests/test_kms.py`, `tests/test_pki_certs.py`,
  `tests/test_tls_demo.py`) run against the actual installed
  `liboqs.so`, real `cryptography` primitives, and real
  `openssl`+`oqs-provider` certs and TLS handshakes — round-trip
  encapsulate/decapsulate, sign/verify, encrypt/decrypt, certificate
  verification, a real TLS 1.3 handshake, and negative cases (tampered
  message, wrong key, wrong passphrase, wrong signer, mismatched TLS
  group) — not mocks.

### A bug this refactor found and fixed

The project's original SSH keygen code hardcoded key sizes per algorithm
instead of reading them from liboqs — its own comment admitted this was a
placeholder. One of those hardcoded values was simply **wrong**: ML-DSA-65's
secret key was hardcoded as 4864 bytes; liboqs actually reports 4032.
Every SSH key generated by the old code was silently zero-padded to the
wrong length. The new `src/algorithms/signature.py` reads the real size
from the `OQS_SIG` struct instead, so this class of bug can't recur for
any algorithm liboqs supports — verified by comparing the new code's
reported sizes against the actual FIPS 203/204 spec sizes in
`tests/test_kem.py` / `tests/test_signature.py`.

### A second bug, found doing routine maintenance

The `Makefile`'s `test`/`setup`/`benchmark`/`status`/`server`/`install`
targets all used `source venv/bin/activate && <command>`. `make` runs
recipes with `/bin/sh` by default (dash on Debian/Ubuntu), which has no
`source` builtin — every one of those targets failed immediately with
`sh: 1: source: not found`, confirmed by actually running `make test` in
a clean environment. They'd been broken since this Makefile was first
written; nothing had ever run them. Fixed by invoking `venv/bin/python3`
directly instead of relying on shell activation, and by actually wiring
`make test` to run the pytest suite (48 tests) — it previously only ran
`quantum_shield.py`'s own basic self-check, never pytest at all. Verified
by creating a fresh venv from scratch via the new `make venv` target and
running every target through it.

## Quick start

The `Makefile` wraps most of this (`make venv && make test`); the manual
steps below are equivalent and useful if you want to see what each step
actually does:

```bash
git clone https://github.com/danindiana/quantum-shield.git
cd quantum-shield

# liboqs is NOT vendored in this repo (see "Building liboqs" below) --
# build it first, then:
export LD_LIBRARY_PATH="$HOME/.local/lib:$LD_LIBRARY_PATH"

python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Run the full test suite against your liboqs build (or: make test)
python3 -m pytest tests/ -v

# Generate post-quantum SSH keys
python3 simple_ssh_keygen.py

# Generate post-quantum TLS certificates (needs oqs-provider too)
export OPENSSL_MODULES="$HOME/.local/lib/ossl-modules"
python3 test_pq_tls.py
```

### Building liboqs

This repo intentionally does not vendor liboqs's ~400MB source tree —
clone and build it yourself. Pin a release tag rather than `main`/HEAD —
`.github/workflows/tests.yml` pins `0.15.0`, matching the exact version
oqs-provider's own CI builds against (its `main` branch had already
drifted incompatible with a newer liboqs release when this was checked):

```bash
git clone --depth 1 --branch 0.15.0 https://github.com/open-quantum-safe/liboqs.git
cmake -S liboqs -B liboqs/build -DCMAKE_INSTALL_PREFIX=$HOME/.local -DBUILD_SHARED_LIBS=ON
cmake --build liboqs/build --parallel
cmake --install liboqs/build
```

For PQ TLS certificates, also build
[`oqs-provider`](https://github.com/open-quantum-safe/oqs-provider)
(pin `0.11.0` — the version actually verified against liboqs `0.15.0`
this session) against the same liboqs install. Two flags matter here,
both found by actually running the build and install, not by reading
the build files and assuming they'd work:

- **`liboqs_DIR` must be an environment variable (`export`), not a
  `-D` CMake flag.** CMake's `find_package(liboqs)` treats a `-D`-set
  cache variable as the *exact* directory containing
  `liboqsConfig.cmake` (one level deeper than the install prefix) and
  silently discards it if it's not exactly that — with no error —
  falling back to any *other* liboqs already on the system's default
  search paths instead. Only as an environment variable does
  oqs-provider's CMakeLists treat it as a prefix to search under. A
  build with the wrong one produces no error and no warning; the only
  way to catch it is `ldd`-checking the built `oqsprovider.so` against
  the liboqs you actually meant to use.
- **`OPENSSL_MODULES_PATH` must be passed explicitly** — without it,
  oqs-provider's `CMakeLists.txt` installs `oqsprovider.so` into the
  *system* OpenSSL modules directory regardless of
  `CMAKE_INSTALL_PREFIX`, which fails with a permission error unless you
  run the install step as root.

```bash
git clone --depth 1 --branch 0.11.0 https://github.com/open-quantum-safe/oqs-provider.git
export liboqs_DIR=$HOME/.local
cmake -S oqs-provider -B oqs-provider/build \
    -DOPENSSL_ROOT_DIR=/usr \
    -DCMAKE_INSTALL_PREFIX=$HOME/.local \
    -DOPENSSL_MODULES_PATH=$HOME/.local/lib/ossl-modules
cmake --build oqs-provider/build --parallel
cmake --install oqs-provider/build

# Confirm it actually linked against the liboqs you just built --
# should show liboqs.so.N resolving under $HOME/.local/lib, not
# /usr/lib or any other path:
LD_LIBRARY_PATH=$HOME/.local/lib ldd $HOME/.local/lib/ossl-modules/oqsprovider.so | grep liboqs
```

Then set `OPENSSL_MODULES=$HOME/.local/lib/ossl-modules` (as in the
Quick Start above) so `openssl` can find it.

## Using the library directly

```python
from src.algorithms.kem import MLKEM768
from src.algorithms.signature import MLDSA65

# Key exchange
kem = MLKEM768()
pk, sk = kem.generate_keypair()
ciphertext, shared_secret_a = kem.encapsulate(pk)
shared_secret_b = kem.decapsulate(sk, ciphertext)
assert shared_secret_a == shared_secret_b

# Signatures
sig = MLDSA65()
pk, sk = sig.generate_keypair()
signature = sig.sign(sk, b"a message")
assert sig.verify(pk, b"a message", signature)
```

```python
from src.kms.store import KeyStore

# Store any keypair from the library above, encrypted at rest
store = KeyStore()  # defaults to ~/.quantum-shield/keystore/
store.save_keypair("my-signing-key", "ML-DSA-65", "signature", pk, sk, "a strong passphrase")
loaded = store.load_keypair("my-signing-key", "a strong passphrase")
assert loaded["secret_key"] == sk
```

```python
from src.pki.certs import load_certificate, is_self_signed_and_valid

# Verify a real PQ X.509 cert (built by openssl+oqs-provider, see
# test_pq_tls.py), using only this project's own liboqs binding
cert = load_certificate(open("server.crt", "rb").read())
assert is_self_signed_and_valid(cert)  # signature + validity dates checked
```

```python
from src.protocols.tls.demo import run_handshake

# A real TLS 1.3 handshake with an ML-KEM-768 group (classical cert for
# auth -- see the module docstring for why, and README "Building liboqs")
result = run_handshake(server_group="mlkem768")
assert result["connected"]
print(result["protocol"], result["cipher"])  # TLSv1.3 TLS_AES_256_GCM_SHA384
```

## Troubleshooting

**`cryptography.exceptions.InternalError: Unknown OpenSSL error ... DSO support routines::could not load the shared library`**
when running an example or test with `OPENSSL_MODULES` set: this
happens with some system-packaged, older `cryptography` builds (seen
with a system Python's `cryptography 3.4.8`, distinct from this
project's own venv) when `OPENSSL_MODULES` points at oqs-provider's
directory — reproduced this session even with **zero** `openssl`
subprocess calls involved, just the env var being set in the same
process that later touches `cryptography`. Not something a real user
should ever hit: **use the project's own venv** (`make venv`, or the
Quick Start above) — verified working there with `cryptography` 46.x
and 50.x. Root cause not fully isolated (old `cryptography` version,
not this repo's code); flagged here rather than silently worked around.

## What's still planned

Carried over honestly from the project's own status tracking rather than
overstated: SSH deployment (`scripts/ssh/`) and TLS certificate generation
work today; `src/kms/` now has a real, tested key store with rotation and
revocation, wired into `simple_ssh_keygen.py --encrypt` (see above), but
still no hardware-backed storage or multi-user access control; `src/pki/`
now verifies certificate signatures and one leaf→issuer chain link (see
above) but doesn't build certificates, walk multi-step chains, or check
revocation; `src/protocols/tls/`
now has a real PQ-KEM TLS 1.3 handshake demo (see above), but full
PQ-*authenticated* TLS needs OpenSSL 3.2+ (this project has 3.0.2) — a
bigger environment change than anything else here, not just more code.
See [`PROGRESS.md`](PROGRESS.md) and
[`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md).

## Diagrams

14 Graphviz diagrams (dark background / neon palette), source `.dot`
alongside rendered `.svg`/`.png` in [`diagrams/`](diagrams/):

| # | Diagram | What it shows |
|---|---|---|
| 01 | [System architecture](diagrams/01-system-architecture.svg) | Full module map, external deps, what's wired vs. not |
| 02 | [KEM flow](diagrams/02-kem-flow.svg) | ML-KEM-768 key exchange sequence, real byte sizes |
| 03 | [Signature flow](diagrams/03-signature-flow.svg) | Sign/verify sequence for ML-DSA-65 / Falcon-512 |
| 04 | [Struct binding approach](diagrams/04-struct-binding-approach.svg) | Before/after: the hardcoded-size bug vs. the struct-read fix |
| 05 | [Repo module map](diagrams/05-repo-module-map.svg) | What imports what, including the duplicated-loader finding |
| 06 | [Roadmap](diagrams/06-roadmap.svg) | Staged next steps, from `FUTURE_DIRECTIONS.md` |
| 07 | [Trust boundary](diagrams/07-trust-boundary.svg) | What's upstream/vetted vs. this repo's own (not audited) code |
| 08 | [Test coverage map](diagrams/08-test-coverage-map.svg) | What's covered by pytest vs. exercised manually vs. untested |
| 09 | [Demo server/client](diagrams/09-demo-server-client.svg) | The real over-the-wire ML-KEM-768 handshake, and its explicit non-goals |
| 10 | [KMS store](diagrams/10-kms-store.svg) | Passphrase-encrypted key storage: scrypt + AES-256-GCM save/load |
| 11 | [KMS rotation/revocation](diagrams/11-kms-rotation-revocation.svg) | Multi-generation rotation and revocation, with `allow_revoked=True` |
| 12 | [PKI cert verification](diagrams/12-pki-cert-verify.svg) | Verifying a real PQ X.509 cert's signature without reimplementing DER |
| 13 | [PQ TLS handshake](diagrams/13-tls-pq-handshake.svg) | A real TLS 1.3 handshake with an ML-KEM-768 group, and the OpenSSL 3.2+ limit found doing it |
| 14 | [PKI chain verification](diagrams/14-pki-chain-verify.svg) | A real leaf-signed-by-CA link, and a negative control with an unrelated CA |

## Documentation

- [System Architecture](docs/SYSTEM_ARCHITECTURE.md) — actual code structure and data flow
- [Future Directions](docs/FUTURE_DIRECTIONS.md) — concrete next steps, checked not guessed
- [Research Notes](docs/RESEARCH_NOTES.md) — dated findings, including real timing measurements
- [Best Practices Log](docs/BEST_PRACTICES.md) — timestamped, tied to specific incidents (not generic advice)
- [Implementation Plan](docs/IMPLEMENTATION_PLAN.md)
- [NIST Standards Compliance](docs/NIST_COMPLIANCE.md)
- [Security Architecture](docs/SECURITY_ARCHITECTURE.md) — security design rationale
- [Deployment Guide](docs/DEPLOYMENT.md)
- [SSH Post-Quantum Guide](docs/SSH_POST_QUANTUM_GUIDE.md) / [Quick Deploy](SSH_QUICK_DEPLOY.md)
- [TLS/HTTPS PQ Research](docs/tls/TLS_PQ_RESEARCH.md)
- [Progress log](PROGRESS.md)

## Directory structure

```
quantum-shield/
├── src/
│   ├── algorithms/     # kem.py, signature.py -- the real, tested library
│   ├── kms/            # store.py -- encrypted key storage, wired into --encrypt
│   ├── pki/            # certs.py -- verifies PQ X.509 certs, never encodes one
│   ├── protocols/tls/  # demo.py -- real TLS 1.3 handshake, PQ KEM group only
│   └── utils/           # empty, planned
├── tests/               # pytest, runs against a real liboqs build
├── diagrams/            # 14 Graphviz diagrams, dark/neon, .dot + rendered
├── docs/                # architecture, future directions, research, best practices
├── scripts/             # SSH deployment automation
├── configs/              # SSH / algorithm configuration
├── benchmarks/           # timing results land here (gitignored)
├── examples/             # kem_demo_client.py, kms_demo.py, kms_rotation_demo.py,
│                         # pki_verify_demo.py, tls_demo.py
├── simple_ssh_keygen.py, test_pq_tls.py, test_liboqs.py
└── quantum_shield.py     # CLI entry point (setup/test/status/benchmark/server)
```

## License

MIT — see [LICENSE](LICENSE).
