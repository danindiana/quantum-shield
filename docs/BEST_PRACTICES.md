# Best Practices Log

Append-only. Each entry is dated and states a practice **and the
concrete incident or check that justified it** — not generic advice
copied from a style guide. Newest first.

---

### 2026-09-14 — Separate "parse structure" from "verify content" when deciding what's safe to build yourself

**What happened:** `src/pki/certs.py` needed to work with X.509
certificates signed by an algorithm (`ML-DSA`, `Falcon`) that
`cryptography`'s own `cert.public_key()`/verification methods don't
support. The tempting shortcut would have been to write a from-scratch
certificate parser (or worse, encoder) to work around that gap.

**Practice:** a binary format's *structure* (how many bytes a field is,
where the next field starts) and its *semantic content* (what a specific
algorithm's key or signature bytes mean, whether a signature is
cryptographically valid) are different problems with different risk
profiles. A generic, algorithm-agnostic structural parser is safe to
write yourself if the format's structure is simple and well-specified
(DER's tag-length-value framing is exactly this). Verifying content is
where a project's own already-tested crypto code should do the work.
Never reach for "write a full encoder/parser for a format we don't fully
need" when "walk the structure generically, delegate the semantics" is
available.

**How to apply here:** `extract_raw_public_key()` only walks DER TLV
framing and RFC 5280's fixed field *order* — it never interprets what's
inside `issuer`/`validity`/`subject`, because it doesn't need to.
`verify_certificate_signature()` does 100% of the actual cryptographic
work through `src/algorithms/signature.py`, never re-implementing a
signature check. Building or signing a certificate stays entirely out of
scope, delegated to `openssl`+`oqs-provider` — that's the side of this
boundary this project has no business doing itself.

---

### 2026-09-14 — Revocation and deletion are different operations; don't conflate them

**What happened:** designing `revoke_key()` for `src/kms/store.py`, the
first instinct was to make revocation delete or overwrite the key
material. Realized this would be wrong: a revoked *signing* key's public
half is often still needed to verify signatures made before the
revocation, and the encrypted secret material itself is harmless at
rest (it's still passphrase-protected) — the actual security property
revocation needs to provide is "don't let anyone use this for anything
new," not "destroy the evidence it ever existed."

**Practice:** when adding a revocation concept to anything, separate
three distinct questions before writing code: (1) can this still be
*read* for historical/verification purposes? (2) can this still be
*used* for new operations? (3) should the underlying material eventually
be *destroyed*? These often have different answers, and conflating them
into a single "revoked = gone" operation forecloses legitimate future
needs.

**How to apply here:** `KeyStore.revoke_key()` answers (2) — no new use
without an explicit `allow_revoked=True` override — while leaving (1)
available and (3) as a separate, not-yet-implemented operation (plain
`delete_key()` already exists for that, unchanged by revocation).

---

### 2026-09-14 — Diagrams rot exactly like duplicated code; check them when the thing they describe changes

**What happened:** `diagrams/01-system-architecture.dot` and
`diagrams/05-repo-module-map.dot` were drawn once, then never revisited
across two subsequent commits that changed the exact things they
described — one still showed `quantum_shield.py`'s `benchmark`/`server`
as simulated after they were made real, and `05` still showed
`verify_liboqs()` as an unfixed duplicate loader *after* that duplication
had already been fixed and celebrated in `PROGRESS.md`. Both diagrams
were quietly wrong for a full commit cycle before this entry caught it
while wiring in `src/kms/`.

**Practice:** a diagram is a claim about the code, same as a docstring or
a README line — it needs the same "does this still match reality" check
before considering a change done, not just when it's first drawn. It's
easy to add a *new* diagram for a new feature and forget that *existing*
diagrams depicting the same subsystem now need a look too.

**How to apply here:** whenever a change touches a module that already
has a diagram referencing it, grep the diagram sources
(`grep -rl <module name> diagrams/*.dot`) before considering the change
done, the same way this session already greps for stale doc references.

---

### 2026-09-14 — Bind identifying context into an AEAD ciphertext as associated data

**What happened:** designing `src/kms/store.py`'s file format, the key's
`name` (its filename-derived identity) was passed to
`AESGCM.encrypt(...)`/`decrypt(...)` as `associated_data`, not just used
to pick which file to read.

**Practice:** when a ciphertext's *meaning* depends on context outside
the ciphertext itself (here: which key this is supposed to be), bind
that context into the AEAD call as associated data, not just as
surrounding metadata a caller is trusted to check. Without this, an
attacker with write access to the keystore directory could rename or
swap two encrypted files, and `load_keypair("key-a", ...)` would happily
decrypt what was actually `key-b`'s ciphertext (its passphrase-derived
key differs per-file via the per-file random salt, so cross-decryption
would usually fail on its own here — but relying on that coincidence
instead of explicitly authenticating the binding is fragile design, not
a deliberate guarantee).

**How to apply here:** any future addition to `src/kms/` that encrypts
data tied to an identifier (a rotation generation number, an owner user
ID, an algorithm name) should bind that identifier as AEAD associated
data the same way, rather than trusting the caller to have looked up the
right file.

---

### 2026-09-14 — A CLI's status output is a security claim; don't let it drift from the code

**What happened:** `quantum_shield.py server`'s banner claimed
"SLH-DSA-128s (Long-term Signatures)" and "Hybrid Mode: Classical +
Post-Quantum" as supported, alongside a "🛡️ All connections secured with
post-quantum cryptography" line — while the command itself only slept in
a loop and never opened a socket. Every claim in that banner was false:
SLH-DSA is disabled in the installed liboqs build (confirmed
independently in `docs/RESEARCH_NOTES.md`), hybrid mode has no
implementation anywhere in the codebase, and no connection of any kind
was ever secured because none was ever accepted.

**Practice:** a CLI's printed status/banner text is read by users as a
factual claim about what the running code does, not as flavor text or
aspirational marketing. Every algorithm or feature named in output like
this should be checked against what the code actually calls, not copied
from the config file's intentions or a project's roadmap.

**How to apply here:** the rebuilt `server` command's banner names
exactly what it does (ML-KEM-768 demo listener) and states its
limitations in the same breath ("no authentication, no transport
encryption, no replay protection") rather than listing capabilities that
sound impressive but aren't real.

---

### 2026-09-14 — Never hardcode a C library's struct sizes; read them at runtime

**What happened:** the original `simple_ssh_keygen.py` hardcoded
ML-DSA-65's secret key length as 4864 bytes. liboqs's `OQS_SIG` struct
actually reports 4032 for that field. Every SSH key the old code
generated was silently zero-padded to the wrong length — no crash, no
error, no obviously wrong output; a working-looking but structurally
incorrect key.

**Practice:** when binding to a C library via `ctypes` (or any FFI),
read size/length fields from the library's own struct or introspection
API at runtime instead of hardcoding them, even when the values are
"well known" or "documented." Reserve hardcoded constants for values a
spec genuinely fixes forever (e.g. ML-KEM-768's 32-byte shared secret is
part of FIPS 203 and won't change); anything that's a property of a
*specific build or algorithm variant* should come from that build.

**How to apply here:** `src/algorithms/kem.py` and `signature.py` both
read `length_public_key`/`length_secret_key`/etc. from the constructed
`OQS_KEM`/`OQS_SIG` struct instance, never from a hardcoded table. Tests
in `tests/test_kem.py`/`test_signature.py` assert those runtime-read
values equal the spec's known sizes — that's checking the binding is
correct, not re-introducing the same hardcoding this practice exists to
avoid.

---

### 2026-09-14 — Test against the real dependency, not a mock, when the dependency is the point

**What happened:** `tests/test_kem.py`/`test_signature.py` run against
the actual `liboqs.so` installed on the machine, not a mocked `ctypes`
call.

**Practice:** for a project whose entire value is "correctly bind to this
external library," mocking that library in tests would only prove the
Python-side plumbing runs, not that it works. A passing mocked test and a
broken real binding are indistinguishable without an integration test
against the real thing.

**How to apply here:** if a CI environment for this repo is ever set up
(none exists yet), it needs to build liboqs first — a unit-test-only CI
that skips the real library would not catch the class of bug this log's
first entry describes.

---

### 2026-09-14 — Don't assume a config file's algorithm choices are actually available

**What happened:** `configs/quantum_shield_config.yaml` names
`SLH-DSA-128s` as the primary hash-based signature scheme. Checking it
directly (`Signature("SLH-DSA-128s")`) found it's disabled at compile
time in the currently installed liboqs build — a config/reality mismatch
that would only surface as a runtime error the first time that code path
actually ran.

**Practice:** when a config file names an external dependency's
capability (an algorithm, a feature flag, a plugin), verify that
capability is actually present in the installed dependency as part of
setup/startup validation — don't assume the config author verified it,
and don't wait for a runtime failure to discover the mismatch.

**How to apply here:** noted in `docs/RESEARCH_NOTES.md`'s 2026-09-14
algorithm availability audit; not yet automated as a startup check (see
`FUTURE_DIRECTIONS.md`).

---

### 2026-09-14 — State disclaimers as a fact about the code, not boilerplate

**What happened:** this project wraps NIST-standardized, liboqs-implemented
cryptography — real algorithms, not toy ones. It would be easy for a
README to read as more production-ready than it is, given that ML-KEM
and ML-DSA sound authoritative on their own.

**Practice:** for security-adjacent code, state explicitly and near the
top of the README what has and hasn't been verified (tests passing
against real liboqs — yes; independent security audit of this
repo's own code — no) rather than a generic "for educational purposes"
disclaimer that doesn't distinguish what's actually been checked.

**How to apply here:** the README's disclaimer names the specific gap
(no independent audit of this repo, liboqs itself not FIPS-certified) —
see also [diagram 07](../diagrams/07-trust-boundary.svg) for what
"trusted" actually covers here.
