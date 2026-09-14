# Future Directions

Concrete, honest next steps — not aspirational feature lists. Each item
below is something checked and found missing/broken this session, not a
guess about what would be nice to have. See
[diagram 06](../diagrams/06-roadmap.svg) for the staged view.

## Near-term (small, well-scoped)

1. ~~**Consolidate `quantum_shield.py`'s `verify_liboqs()` with
   `src/algorithms/_liboqs.py`.**~~ **Done.** Found while drawing
   [diagram 05](../diagrams/05-repo-module-map.svg): they independently
   implemented the same "search a few paths, try `ctypes.CDLL`" logic —
   exactly the kind of drift that produced the original hardcoded-key-size
   bug. `verify_liboqs()` now delegates to `algorithms._liboqs.load_liboqs()`.
2. **Wire `quantum_shield.py`'s `benchmark` and `server` subcommands into
   the real library.** Right now they print simulated/placeholder output
   (`"⏱️ Simulating ML-KEM key generation..."`) instead of calling
   `src/algorithms/kem.py` / `signature.py`. This is a small change with
   a disproportionately misleading current behavior — a user running
   `./quantum_shield.py benchmark` today gets fake numbers that look real.
3. **Actual benchmark numbers.** `docs/tls/TLS_PQ_RESEARCH.md` and the
   config reference NIST security levels and algorithm names but no file
   in this repo has ever measured real keygen/encaps/decaps/sign/verify
   timings on this hardware. `src/algorithms/kem.py` and `signature.py`
   are stable enough now to time honestly. See
   `docs/RESEARCH_NOTES.md` for the first such measurement.

## Medium-term (real scope, not started)

4. **`src/kms/`** — key storage, rotation, and revocation. Currently an
   empty directory. `simple_ssh_keygen.py` writes raw keys straight to
   `~/.ssh/` with no lifecycle management at all.
5. **`src/pki/`** — certificate authority / trust chain handling beyond
   the single self-signed cert `test_pq_tls.py` generates via the
   `openssl` CLI.
6. **`src/protocols/tls/`** — an actual PQ-TLS server/client using the
   library, not just manual certificate issuance via shell-out to
   `openssl`.
7. **SLH-DSA support.** Configured as the primary `hash_signature` scheme
   in `configs/quantum_shield_config.yaml`, but checked this session:
   `Signature("SLH-DSA-128s")` raises — it's disabled at compile time in
   the liboqs build currently installed. `src/algorithms/signature.py`'s
   `Signature` class is already written generically enough to support it
   once liboqs is rebuilt with it enabled; no code change needed there,
   just a liboqs rebuild.

## Longer-term / needs more thought before starting

8. **Hybrid mode** (classical + PQ, e.g. X25519 + ML-KEM-768) — configured
   as `enabled: true` in `configs/quantum_shield_config.yaml` but nothing
   in the codebase implements it. This is architecturally bigger than it
   sounds: it means combining two independent key-exchange outputs
   correctly (concatenation isn't automatically safe — depends on the
   specific combiner construction used), which is exactly the kind of
   decision that benefits from following an established combiner spec
   (e.g. the IETF hybrid-TLS draft referenced in
   `docs/tls/TLS_PQ_RESEARCH.md`) rather than improvising one.
9. **A real security review.** Everything in this repo remains explicitly
   **not audited** (see the README). liboqs itself is under active
   development and not FIPS-certified as a module. Before any of the
   above gets used for anything beyond learning/prototyping, an actual
   independent review — not a solo AI-assisted session — is a
   prerequisite, not a nice-to-have.

## Explicitly not planned

- Implementing cryptographic primitives from scratch. This project wraps
  liboqs; it does not and should not reimplement ML-KEM/ML-DSA math
  itself. Rolling your own crypto primitives is a well-known way to
  introduce subtle, catastrophic bugs that don't show up in functional
  tests — the entire value of using liboqs is standing on a
  community-reviewed reference implementation instead.
