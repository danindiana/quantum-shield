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
  real liboqs bindings, sizes read from the C struct at runtime, 11
  passing tests round-tripping encapsulate/decapsulate and sign/verify
  against the actual installed library.

## Not yet started

- `src/kms/` — key management (storage, rotation, revocation). Empty.
- `src/pki/` — certificate authority / trust chain handling. Empty.
- `src/protocols/tls/` — TLS integration beyond manual `openssl` CLI
  certificate generation (i.e., an actual PQ-TLS server/client, not just
  cert issuance). Empty.
- SLH-DSA (hash-based signatures, FIPS 205) — configured as the primary
  `hash_signature` scheme in `configs/quantum_shield_config.yaml`. Checked
  this session: `Signature("SLH-DSA-128s")` raises `SignatureError` —
  it's disabled at compile time in the liboqs build on this machine, even
  though `src/algorithms/signature.py`'s `Signature` class is written
  generically enough to support any algorithm liboqs has compiled in.
  Would need a liboqs rebuild with SLH-DSA enabled to use.
- `quantum_shield.py`'s `benchmark` and `server` CLI subcommands print
  simulated/placeholder output; they don't call the real library yet.

## Known limitation carried over from the original project

liboqs and `oqs-provider` are **not vendored** in this repo (their
combined source is ~400MB and both are readily available upstream) — see
the README's "Building liboqs" section. Anyone cloning this repo needs to
build them separately before the tests or CLI tools will work.
