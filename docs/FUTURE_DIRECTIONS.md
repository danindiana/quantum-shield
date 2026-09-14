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
2. ~~**Wire `quantum_shield.py`'s `benchmark` and `server` subcommands
   into the real library.**~~ **Done.** `benchmark` now runs real timings
   via `src/algorithms/kem.py`/`signature.py` and writes them to
   `benchmarks/results/<timestamp>.json`; `server` is now a real (clearly
   labeled, non-production) ML-KEM-768 key-exchange demo listener over a
   real TCP socket, testable against the new
   `examples/kem_demo_client.py` — both sides derive the same shared
   secret, verified this session. The old `server` output also claimed
   SLH-DSA-128s and "Hybrid Mode" support that don't exist anywhere in
   this codebase; the new version only advertises what it actually does.
3. ~~**Actual benchmark numbers.**~~ **Done**, see item 2 above and
   `docs/RESEARCH_NOTES.md`.
4. **The demo listener handles one connection at a time and blocks on
   `accept()`.** Fine for a demo, but worth a note: it doesn't fork or
   thread, so a second `kem_demo_client.py` run while one is already
   connected just queues until the first disconnects. Not a bug, just a
   scope boundary worth stating rather than discovering by surprise.
5. ~~**`run_basic_tests()`'s directory check was out of sync with
   `tests/test_setup.py`'s `test_project_structure`.**~~ **Done.** Both
   now check the same list (`src`, `tests`, `docs`, `scripts`, `configs`,
   `benchmarks`, `examples`, `diagrams`) — the same category of issue as
   the `verify_liboqs()` duplication in item 1: two places asserting the
   same fact, able to silently disagree.

## Medium-term (real scope, some started)

4. ~~**`src/kms/`** — key storage.~~ **Started.** `src/kms/store.py`
   (`KeyStore`) now provides passphrase-encrypted at-rest storage
   (AES-256-GCM, scrypt-derived key, key name bound as AEAD associated
   data) for any keypair produced by `src/algorithms/`. 11 tests in
   `tests/test_kms.py`, demoed in `examples/kms_demo.py`. See
   [diagram 10](../diagrams/10-kms-store.svg).

   ~~**`simple_ssh_keygen.py` still writes raw, unencrypted key bytes to
   `~/.ssh/`.**~~ **Done.** Added a `--encrypt` flag: with it, the
   private key is stored via `KeyStore` (passphrase prompted twice via
   `getpass`, no echo) instead of written as a plaintext file; the
   public key still gets written as a plain file as before (it isn't
   secret). Default behavior (no flag) is unchanged, so this is additive,
   not a breaking change. Verified: plaintext mode still produces
   identical output to before; encrypt mode round-trips correctly
   through `KeyStore.load_keypair()`.

   ~~**Key rotation.**~~ **Done.** `rotate_key()` archives the current
   active generation (status `"rotated"`) and activates a new one, under
   a passphrase that need not match the old generation's. `list_history()`
   returns every generation's status, oldest first. 8 new tests, demoed
   in `examples/kms_rotation_demo.py`. See
   [diagram 11](../diagrams/11-kms-rotation-revocation.svg).

   ~~**Revocation.**~~ **Done.** `revoke_key()` marks the active
   generation revoked in place; `load_keypair()` then refuses it unless
   `allow_revoked=True` is passed explicitly (kept available on purpose —
   e.g. to still verify old signatures against a revoked signing key's
   public half).

   **Not done yet, and this remains a real gap:**
   - **No hardware-backed storage** (HSM/TPM) — this is a plain file on
     disk, encrypted, but a file nonetheless.
   - **No multi-user access control** — anything with filesystem access
     to the keystore directory and the right passphrase can read a key;
     there's no separate authorization layer.
   - **No automatic/scheduled rotation** — `rotate_key()` is a manual
     operation a caller invokes; nothing tracks key age or expiry to
     prompt it.
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
