# Progress

Consolidated from the original project's status-tracking files (dropped
individually in this fork in favor of one current summary).

## Working today

- **CI (2026-09-14)**: `.github/workflows/tests.yml` builds liboqs
  `0.15.0` + oqs-provider `0.11.0` from pinned tags (verified compatible
  pairing — a newer "latest" pairing of both actually fails to compile)
  and runs the full 48-test suite on every push/PR. Verified with a real
  run on GitHub Actions (`gh run watch`), not just YAML that looks
  right: all steps green, 48 passed, in ~4 minutes. Caught and fixed a
  genuinely subtle bug along the way — `liboqs_DIR` must be an
  environment variable, not a `-D` CMake flag, or oqs-provider silently
  links against a different liboqs with zero build errors. README's
  "Building liboqs" section updated with the same corrected, verified
  commands.
- **`Makefile`, fixed (2026-09-14)**: every target except `help`/`clean`
  was silently broken since it was written (`source venv/bin/activate`
  doesn't work under `/bin/sh`, which is what `make` actually uses), and
  `make test` never called `pytest` at all. Fixed all targets to invoke
  `venv/bin/python3` directly, wired `test` to the real 48-test suite,
  added a `venv` bootstrap target, fixed `docs`' dead references to two
  files dropped in this fork's first commit. Verified end-to-end against
  a freshly created venv, not a pre-existing one.
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
  `examples/kms_demo.py`. 10th diagram (`diagrams/10-kms-store.svg`).
- **`simple_ssh_keygen.py --encrypt`** — now wired into `KeyStore`: with
  the flag, the private key is stored encrypted (passphrase prompted
  twice via `getpass`) instead of written as a plaintext file; without
  it, behavior is unchanged from before. Verified both modes end-to-end,
  including a full non-interactive subprocess run with a redirected
  `HOME`.
- **`src/kms/` rotation and revocation** — `rotate_key()` archives the
  current active generation (status "rotated") and activates a new one
  under a possibly-different passphrase; `revoke_key()` marks the active
  generation revoked in place, and `load_keypair()` then refuses it
  unless `allow_revoked=True`. `list_history()` returns every
  generation's status, oldest first. 8 new tests (19 in
  `tests/test_kms.py`, 35 total). Demoed in
  `examples/kms_rotation_demo.py`. 11th diagram
  (`diagrams/11-kms-rotation-revocation.svg`).
- **`src/pki/certs.py`** — verifies a PQ-signed X.509 certificate's
  signature without ever building or encoding one: structure parsing via
  `cryptography`'s X.509 parser, raw public key extraction via a small
  generic DER TLV walker, signature check via
  `src/algorithms/signature.py`. Verified against real ML-DSA-65 and
  Falcon-512 certs generated fresh in the test run (not fixtures). 13
  tests in `tests/test_pki_certs.py` (48 total). Demoed in
  `examples/pki_verify_demo.py`. 12th diagram
  (`diagrams/12-pki-cert-verify.svg`). While updating diagrams 01, 06,
  07, and 08 for this, found all four had `src/pki/` or test-count
  references stale from prior commits — fixed all four (see
  `docs/BEST_PRACTICES.md`'s "diagrams rot" entry, which is now doing
  double duty).

## Not yet started

- `src/pki/` **chain verification, key usage/extensions, revocation
  (CRL/OCSP)** — current code verifies one certificate's signature, not
  a trust chain or anything else a real validator needs.
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
