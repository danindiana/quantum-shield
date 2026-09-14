# Research Notes

Dated entries, newest first. Each entry records what was actually checked
or measured on this machine, with the date — not restated general PQC
background (that's in `NIST_COMPLIANCE.md`).

---

## 2026-09-14 — Wired KeyStore into simple_ssh_keygen.py, and found two stale diagrams doing it

Added a `--encrypt` flag to `simple_ssh_keygen.py`: with it, the private
key goes through `KeyStore.save_keypair()` (passphrase prompted twice via
`getpass`) instead of being written as a plaintext file; without it,
behavior is byte-for-byte unchanged from before. Verified both paths:
plaintext mode still produces the same output as before, encrypt mode
round-trips correctly, and a full non-interactive run via `subprocess`
with a redirected `HOME` exercises the whole CLI flow end-to-end.

While updating `diagrams/01-system-architecture.dot` and
`diagrams/05-repo-module-map.dot` to add the new `KeyStore` edge, found
both diagrams had already drifted from reality *before* this change —
`01` still showed `benchmark`/`server` as simulated (fixed two commits
ago) and `05` still showed `verify_liboqs()` as an unfixed duplicate
loader (fixed even earlier). Neither diagram had been touched since
those code changes landed. Rewrote both to match current reality; see
`docs/BEST_PRACTICES.md`'s new entry on why this happened.

---

## 2026-09-14 — Key storage was entirely absent; added and tested a minimal version

Before this entry, `simple_ssh_keygen.py` was the only code path in this
repo that persisted key material at all, and it writes raw bytes to
`~/.ssh/` with no encryption — `src/kms/` was an empty directory with no
plan more specific than "key management" in the original project's
status files.

Added `src/kms/store.py` (`KeyStore`): AES-256-GCM encryption of key
material at rest, key derived from a passphrase via scrypt with
N=2^14, r=8, p=1 — RFC 7914's recommended parameters for interactive
logins, chosen as a reasonable default rather than tuned or benchmarked
against this hardware; a real deployment should re-evaluate these
against current guidance, not assume they're right forever. The store's
`name` is bound in as AEAD associated data specifically to prevent
silently swapping one encrypted key file for another without detection.

**Deliberately out of scope for this addition:** key rotation, revocation,
multi-user access control, hardware-backed storage. This is "don't write
plaintext keys to disk," not a full KMS. See `docs/FUTURE_DIRECTIONS.md`.

---

## 2026-09-14 — First real over-the-wire key exchange

Verified `quantum_shield.py server` and the new
`examples/kem_demo_client.py` actually perform a working ML-KEM-768
handshake over a real TCP socket (loopback, port 18443 for the test):
server generates a keypair and sends the public key; client encapsulates
against it and sends back the ciphertext; server decapsulates. Both
processes printed the identical 32-byte shared secret
(`af62ad66611d234e51fd13ebc827afa75ace7f52fa01e581feac9fb9fe506b6e` in
this run — the value itself is meaningless, it's freshly random every
run; what matters is that it matched on both sides).

**Explicitly not claimed:** this is not TLS, has no authentication of the
server's public key (a machine-in-the-middle could substitute their own
key and the client would never know), no transport encryption of
anything after the handshake, and no replay protection. It demonstrates
the KEM primitive working correctly over a real network boundary, which
is a meaningfully different (and stronger) claim than "the Python
function returns the right bytes in-process" — but it is not a security
protocol. See `docs/FUTURE_DIRECTIONS.md` item 6 for what real PQ-TLS
integration would still need on top of this.

---

## 2026-09-14 — First real performance measurement

No file in this repo had ever measured actual algorithm timings before
this entry — `docs/tls/TLS_PQ_RESEARCH.md` and
`configs/quantum_shield_config.yaml` reference NIST security levels and
algorithm names, but nothing had run them and timed it.

**Method:** `src/algorithms/kem.py` / `signature.py`, 200 iterations per
operation after a 5-iteration warmup, `time.perf_counter()`, single-run
(not averaged across multiple sessions — see caveats below).

**Hardware:** AMD Ryzen 9 7950X3D (16-core), single-threaded Python
process, no concurrent load control.

| Operation | Time (ms/op) |
|---|---|
| ML-KEM-768 keypair | 0.0105 |
| ML-KEM-768 encapsulate | 0.0085 |
| ML-KEM-768 decapsulate | 0.0165 |
| ML-DSA-65 keypair | 0.0384 |
| ML-DSA-65 sign | 0.0861 |
| ML-DSA-65 verify | 0.0199 |
| Falcon-512 keypair | 4.6977 |
| Falcon-512 sign | 0.1413 |
| Falcon-512 verify | 0.0251 |

**Observations:**
- Falcon-512 keypair generation is ~450x slower than ML-DSA-65's — this
  matches Falcon's known characteristic (NTRU lattice trapdoor sampling
  is expensive) rather than being a binding-layer artifact; worth
  confirming against upstream liboqs benchmarks before relying on this
  number for anything decision-relevant.
- All figures are liboqs's native C implementation timing plus Python/
  ctypes call overhead; the overhead itself hasn't been isolated (e.g. by
  comparing against liboqs's own C benchmark harness) — treat these as
  "cost of calling this from Python," not "cost of the algorithm in
  isolation."
- Single run, no statistical variance reported (stddev, percentiles).
  **Caveat, stated plainly:** this is a first measurement, not a
  benchmark suite. Re-run before trusting these for any real comparison
  or optimization decision — see `docs/FUTURE_DIRECTIONS.md` item 3 for
  making this a proper repeatable benchmark instead of an ad hoc note.

---

## 2026-09-14 — Algorithm availability audit

Checked which algorithms are actually enabled in the currently installed
liboqs build (v0.14.1-dev), rather than assuming everything in
`configs/quantum_shield_config.yaml` is available:

- `ML-KEM-768` (primary KEM): **available**, verified working via
  `src/algorithms/kem.py`.
- `ML-DSA-65` (primary signature): **available**, verified working.
- `Falcon-512`: **available**, verified working (used by
  `simple_ssh_keygen.py`).
- `SLH-DSA-128s` (primary hash-based signature): **NOT available** —
  `Signature("SLH-DSA-128s")` raises `SignatureError`, confirming it's
  disabled at compile time in this build despite being configured as
  primary in `quantum_shield_config.yaml`. This is a config/build mismatch
  worth flagging rather than assuming the config is accurate.

**Takeaway:** the config file describes an intended algorithm set, not a
verified-available one. Anyone deploying this should run a quick
`Signature(alg)` construction check for every algorithm their config
names before relying on it — the failure mode otherwise is a runtime
`SignatureError` at first use, not a startup-time warning.
