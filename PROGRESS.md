# Progress

Consolidated from the original project's status-tracking files (dropped
individually in this fork in favor of one current summary).

## Working today

- **SSH**: post-quantum SSH keypair generation (ML-DSA-65, Falcon-512) via
  `simple_ssh_keygen.py`, backed by `src/algorithms/signature.py`.
- **TLS**: post-quantum certificate generation via `openssl` +
  `oqs-provider`, verified working against OpenSSL 3.0.2 with liboqs
  v0.14.1-dev (221 signature algorithms, 35 KEMs available).
- **Library**: `src/algorithms/kem.py` (`MLKEM768`) and
  `src/algorithms/signature.py` (`Signature`, `MLDSA65`, `Falcon512`) —
  real liboqs bindings, sizes read from the C struct at runtime, 16
  passing tests round-tripping encapsulate/decapsulate and sign/verify
  against the actual installed library.
- **Docs/diagrams (2026-09-14)**: `docs/SYSTEM_ARCHITECTURE.md`,
  `docs/FUTURE_DIRECTIONS.md`, `docs/RESEARCH_NOTES.md` (includes a real
  first performance measurement, not simulated numbers),
  `docs/BEST_PRACTICES.md` (timestamped, tied to specific findings), and
  8 Graphviz diagrams in `diagrams/`.
- **`quantum_shield.py`'s `verify_liboqs()`** now delegates to the shared
  `algorithms._liboqs.load_liboqs()` loader instead of duplicating the
  path-search logic — the duplication was found while drawing the module
  map (`diagrams/05-repo-module-map.svg`).
- **`quantum_shield.py benchmark`** now runs real timings against
  `src/algorithms/kem.py`/`signature.py` and writes them to
  `benchmarks/results/<timestamp>.json`, instead of printing simulated
  output. Skips any algorithm unavailable in the current liboqs build
  (SLH-DSA) rather than faking a number.
- **`quantum_shield.py server`** is now a real ML-KEM-768 key-exchange
  demo over an actual TCP socket, testable against the new
  `examples/kem_demo_client.py` — verified both sides derive the same
  shared secret. The old version claimed SLH-DSA and "Hybrid Mode"
  support that didn't exist anywhere in the codebase; the new banner only
  states what it actually does, and explicitly flags itself as a protocol
  demo, not a security protocol (no auth, no transport encryption, no
  replay protection). See `diagrams/09-demo-server-client.svg`.
- **9th diagram** (`diagrams/09-demo-server-client.svg`) added for the
  above; `diagrams/08-test-coverage-map.svg` updated to move
  `benchmark`/`server` from "untested" to "exercised manually."
- **`run_basic_tests()`'s required-directory list** now matches
  `tests/test_setup.py`'s (both check `diagrams`, previously only one did).
- **`src/kms/store.py`** (`KeyStore`) — passphrase-encrypted at-rest key
  storage (AES-256-GCM, scrypt KDF, key name bound as AEAD associated
  data). 11 tests in `tests/test_kms.py` (27 total now), demoed in
  `examples/kms_demo.py`. `simple_ssh_keygen.py` does **not** use this
  yet — it still writes raw keys to `~/.ssh/`, see "Not yet started."
  10th diagram (`diagrams/10-kms-store.svg`) added.

## Not yet started

- **Wiring `KeyStore` into `simple_ssh_keygen.py`** (e.g. an `--encrypt`
  flag) — the store exists and is tested; the existing script hasn't
  been changed to use it yet.
- `src/kms/` **rotation and revocation** — the store has save/load/list/
  delete; no concept of superseding a key or an expiry/revocation list.
- `src/pki/` — certificate authority / trust chain handling. Empty.
- `src/protocols/tls/` — TLS integration beyond manual `openssl` CLI
  certificate generation (i.e., an actual PQ-TLS server/client, not just
  cert issuance, and not the unauthenticated demo in `quantum_shield.py
  server`).
- SLH-DSA (hash-based signatures, FIPS 205) — configured as the primary
  `hash_signature` scheme in `configs/quantum_shield_config.yaml`. Checked
  this session: `Signature("SLH-DSA-128s")` raises `SignatureError` —
  it's disabled at compile time in the liboqs build on this machine, even
  though `src/algorithms/signature.py`'s `Signature` class is written
  generically enough to support any algorithm liboqs has compiled in.
  Would need a liboqs rebuild with SLH-DSA enabled to use.

## Known limitation carried over from the original project

liboqs and `oqs-provider` are **not vendored** in this repo (their
combined source is ~400MB and both are readily available upstream) — see
the README's "Building liboqs" section. Anyone cloning this repo needs to
build them separately before the tests or CLI tools will work.
