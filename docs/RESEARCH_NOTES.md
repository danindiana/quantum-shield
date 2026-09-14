# Research Notes

Dated entries, newest first. Each entry records what was actually checked
or measured on this machine, with the date — not restated general PQC
background (that's in `NIST_COMPLIANCE.md`).

---

## 2026-09-14 — Setting up CI found a real, silent liboqs/oqs-provider version and linkage trap

Writing `.github/workflows/tests.yml` (build liboqs + oqs-provider from
pinned tags, run the test suite) surfaced two real problems, both found
by actually building, not by reading build files:

1. **Version incompatibility.** liboqs `0.16.0` (its newest tag at the
   time of checking) + oqs-provider `0.11.0` (its newest tag) fails to
   compile: `OQS_SIG_alg_sphincs_shake_128f_simple` undeclared —
   oqs-provider 0.11.0 expects an older SPHINCS+ symbol name liboqs
   0.16.0 removed. Checked oqs-provider's own CI
   (`.github/workflows/linux.yml`) and found it pins liboqs `0.15.0`,
   not `0.16.0` — switched to that exact pairing, which builds and
   passes the full test suite (48/48) cleanly. Two "latest" tags from
   two related projects are not automatically compatible with each
   other; the maintaining project's own CI pin is the real source of
   truth.

2. **Silent wrong-linkage.** Even with the right version pair,
   `cmake -Dliboqs_DIR=$HOME/.local ...` built oqs-provider with no
   errors — but the resulting `oqsprovider.so` had linked against a
   *different* liboqs already present on the test machine (leftover
   from earlier work this session), not the one just built. Caught only
   by `ldd`-checking the actual `.so` and comparing its SONAME
   (`liboqs.so.8`, the old one) against what the fresh build actually
   produced (`liboqs.so.9`). Root cause: `liboqs_DIR` needs to be set as
   an **environment variable**, not a `-D` CMake cache flag — confirmed
   by finding oqs-provider's own `scripts/fullbuild.sh`, which sets it
   via `export`, and reproducing both the broken (`-D`) and working
   (`export`) forms side by side. See
   `docs/BEST_PRACTICES.md`'s new entry on this.

Verified the corrected build three times end-to-end, atomically (single
shell script, not split across multiple invocations after the first
attempt's cross-invocation environment confusion added noise) — real
cert generation via `openssl genpkey`/`req`, `ldd` confirming correct
linkage, and the full 48-test pytest suite passing against the fresh
build. Also updated the README's "Building liboqs" section with the
exact same corrected commands, verified literally copy-paste-runnable.

---

## 2026-09-14 — The Makefile had been completely non-functional since it was written

Checked something nobody had touched all session: the `Makefile`. Ran
`make test` in a clean environment (`env -i`, no inherited shell state)
to see what a fresh clone actually experiences. Result:
`sh: 1: source: not found`, exit 127 — every target using
`source venv/bin/activate && ...` (that's `setup`, `test`, `install`,
`benchmark`, `status`, `server` — everything except `help` and `clean`)
fails immediately, because `make` invokes recipes with `/bin/sh`, and
`source` is a bash builtin, not a POSIX `sh` one.

Separately, `make test` — even if it had run — only called
`quantum_shield.py test` (the CLI's own ~10-line self-check), never
`pytest`. The actual 48-test suite this session built had no `make`
entry point calling it at all.

Fixed both: every target now calls `venv/bin/python3`/`venv/bin/pytest`
directly (works under any `/bin/sh`), `test` runs the real pytest suite,
and a new `venv` target bootstraps a fresh virtualenv from
`requirements.txt`. Verified end-to-end by actually creating a brand new
venv via `make venv` (not reusing any existing one) and running every
target through it — `test` (48 passed), `docs`, `status`, `benchmark`,
`pki-demo`, `security`, `test-cli`, `clean`.

Also found while fixing `docs`: it referenced `QUICK_REFERENCE.md` and
`PROJECT_STATUS.md`, both dropped in this repo's very first commit (the
initial fork consolidation) — an eleven-commit-old dead reference nobody
had checked either. Grepped the whole repo for every other file dropped
in that consolidation; the Makefile was the only place any of them still
appeared.

---

## 2026-09-14 — Verified a real PQ X.509 certificate end-to-end, without reimplementing DER

Investigated whether `src/pki/` could offer more than documentation
before building anything: checked whether `cryptography` (already a
dependency) natively supports ML-DSA for X.509 -- it doesn't
(`cryptography.hazmat.primitives.asymmetric.ml_dsa` doesn't exist in
46.0.2). Rolling a full X.509 *encoder* with correct ASN.1 DER for a PQ
signature algorithm was ruled out as too large and too risky for this
pass -- getting DER encoding subtly wrong is a real, easy-to-hit failure
mode, and `openssl`+`oqs-provider` already does it correctly.

What turned out to be both safe and genuinely useful: `cryptography`'s
X.509 *parser* handles a certificate's structure correctly even for a
signature algorithm it can't verify (`cert.public_key()` raises "Unknown
key type," but `cert.tbs_certificate_bytes`, `cert.signature`, and
`cert.signature_algorithm_oid` all work). Confirmed this directly against
a real ML-DSA-65 cert generated on this host via `openssl genpkey
-algorithm mldsa65` + `openssl req -x509` (with `oqs-provider`, already
built here) — parsing succeeded, `cert.signature_algorithm_oid` returned
`2.16.840.1.101.3.4.3.18`.

The remaining piece — getting the raw public key bytes out of
`SubjectPublicKeyInfo` — needed some DER parsing, but only a *generic*
TLV walker (tag/length/content), not certificate-specific encoding logic.
Prototyped it interactively against the real cert before writing the
module: walked `tbs_certificate_bytes`'s fixed RFC 5280 field order to
reach the `SubjectPublicKeyInfo` SEQUENCE, then its `BIT STRING`, and
confirmed the content (minus the leading "unused bits" byte) is exactly
the raw ML-DSA-65 public key — verified by feeding it into
`Signature("ML-DSA-65").verify(raw_pk, cert.tbs_certificate_bytes,
cert.signature)`, which returned `True` against a real, honestly-generated
certificate. Repeated the same check for a real Falcon-512 cert
(different OID: `1.3.9999.3.11`, an OQS-private experimental arc, not a
NIST-assigned one).

Also found and fixed a portability gap while writing this: the code
initially used `cert.not_valid_before_utc` (added in `cryptography`
42.0), which doesn't exist on the system's much older `cryptography`
3.4.8 (distinct from this project's own venv) — a real version mismatch
that would only have shown up when someone ran a script outside the
venv. Fixed to prefer the newer accessor when present, fall back to the
older naive one otherwise.

---

## 2026-09-14 — Added key rotation and revocation to KeyStore

Extended `src/kms/store.py` with `rotate_key()`, `revoke_key()`, and
`list_history()`. Design choice worth recording: rotation **never
decrypts the key being rotated away** — it only needs the old record's
plaintext metadata (algorithm, key type, generation number) to archive
it, not its secret key material. This means rotating to a new keypair
under a *lost* old passphrase is still possible (you can't recover the
old key, but you can still supersede it with a new one) — a deliberate
property, not an oversight, verified by `test_rotate_archives_old_generation_and_activates_new`
using two different passphrases for the two generations.

Revocation is intentionally **not** deletion: `revoke_key()` marks the
active generation's status in place and `load_keypair()` refuses it by
default, but the encrypted material is still there and recoverable with
`allow_revoked=True` — this matters because a revoked *signing* key's
public half may still be legitimately needed to verify signatures made
before revocation. Confirmed this distinction actually works end-to-end
in `examples/kms_rotation_demo.py`, not just asserted in a docstring.

8 new tests (19 total in `tests/test_kms.py`, 35 overall).

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

## 2026-09-14 — Closed the "no statistical variance" caveat above, and found a real signal in doing it

`_time_op()` in `quantum_shield.py` now times each of the 200 iterations
individually (instead of one wall-clock span divided by 200) and reports
mean/stddev/min/max/p95 per operation, addressing the caveat two entries
up directly. Re-running surfaced something a single average had hidden:

| Operation | mean (ms) | stddev (ms) | min | max | p95 |
|---|---|---|---|---|---|
| ML-DSA-65 sign | 0.0518 | **0.0335** | 0.0228 | 0.265 | 0.1034 |
| Falcon-512 keypair | 4.3149 | **1.3361** | 3.1272 | 10.4866 | 7.3442 |

Every other operation measured (KEM keypair/encaps/decaps, both
algorithms' verify, ML-DSA-65 keypair) has a stddev under ~3% of its
mean — tight and boring, as expected for constant-time-ish operations.
These two stand out: ML-DSA-65's sign stddev is **65% of its own mean**,
and Falcon-512's keypair max (10.49ms) is **2.4x** its min (3.13ms).

This is consistent with both algorithms' known internals rather than a
binding artifact: ML-DSA (Dilithium) signing and Falcon's NTRU trapdoor
key generation both use **rejection sampling** — an internal retry loop
that runs a variable number of times per call depending on random
sampling outcomes, by design (not a bug, and not something
`src/algorithms/` controls or could "fix" — it's inherent to how these
specific lattice constructions achieve their security proofs). Stated as
a hypothesis consistent with the data, not independently confirmed
against liboqs's own internals this session — the honest caveat now is
"this pattern matches the known algorithm design," not "no variance data
exists at all."

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
