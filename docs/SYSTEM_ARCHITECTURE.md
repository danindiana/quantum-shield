# System Architecture

This describes the actual code structure and data flow as it exists in
this repo — not the intended future state (that's
[`FUTURE_DIRECTIONS.md`](FUTURE_DIRECTIONS.md)) and not the security
design rationale (that's [`SECURITY_ARCHITECTURE.md`](SECURITY_ARCHITECTURE.md)).
See [diagram 01](../diagrams/01-system-architecture.svg) for the visual
version and [diagram 05](../diagrams/05-repo-module-map.svg) for the
module dependency graph.

## Layers

**External, not vendored in this repo:**
- `liboqs.so` — Open Quantum Safe's C implementation of the NIST PQC
  algorithms. Built separately (see README "Building liboqs"), installed
  to `~/.local/lib/liboqs.so` by convention.
- `openssl` + `oqs-provider` — used only via CLI shell-out
  (`test_pq_tls.py`), not linked into the Python library.

**`src/algorithms/`** — the tested, working library:
- `_liboqs.py` — one shared loader (`load_liboqs()`), tries a small list
  of known install paths, caches the loaded `ctypes.CDLL`. Everything
  else in `src/algorithms/` uses this; nothing else should reimplement
  path-searching logic (this consolidation happened 2026-09-14 — see
  `FUTURE_DIRECTIONS.md` item 1's strikethrough).
- `kem.py` — `MLKEM768`. A `ctypes.Structure` mirroring liboqs's
  `OQS_KEM` struct layout (fixed fields only), plus `argtypes`/`restype`
  declarations on the top-level `OQS_KEM_keypair`/`encaps`/`decaps` C
  functions (bound by name, not called through the struct's function
  pointers — see [diagram 04](../diagrams/04-struct-binding-approach.svg)
  for why). Buffer sizes for public/secret keys, ciphertexts, and shared
  secrets are read from the constructed struct instance at runtime.
- `signature.py` — `Signature` (generic, takes an algorithm name string)
  plus `MLDSA65`/`Falcon512` convenience subclasses. Same struct-mirroring
  approach against `OQS_SIG`.

**Consumers of `src/algorithms/`:**
- `simple_ssh_keygen.py` — uses `Signature(algorithm)` to generate real
  SSH keypairs, base64-encodes them into (a simplified) OpenSSH key
  format.
- `tests/test_kem.py`, `tests/test_signature.py` — integration tests
  against the real installed `liboqs.so`.
- `quantum_shield.py` — currently only uses `algorithms._liboqs` (for its
  `verify_liboqs()` status check); its `benchmark`/`server` subcommands
  don't call `kem.py`/`signature.py` yet (`FUTURE_DIRECTIONS.md` item 2).

**`src/kms/`** — key storage, started (rotation/revocation not yet):
- `store.py` — `KeyStore`. Takes any `(public_key, secret_key)` pair
  from `src/algorithms/` and encrypts it at rest: scrypt derives a
  256-bit AES key from a passphrase, AES-256-GCM encrypts the key
  material with the store entry's `name` bound in as AEAD associated
  data (so a ciphertext file can't be silently swapped between entries
  without decryption failing). One JSON file per key on disk, metadata
  in plaintext, key bytes encrypted. Not yet wired into
  `simple_ssh_keygen.py` — see `FUTURE_DIRECTIONS.md`. See
  [diagram 10](../diagrams/10-kms-store.svg).

**Not yet connected to anything:**
- `src/pki/`, `src/protocols/tls/` — directory skeleton only, no files.
  See `FUTURE_DIRECTIONS.md` for what each is meant to hold.

## Why the struct-mirroring approach, specifically

liboqs exposes `OQS_KEM`/`OQS_SIG` as C structs containing both metadata
(key/ciphertext/signature byte lengths — which vary per algorithm and are
only known once the struct is constructed for a specific algorithm name)
and function pointers for the actual crypto operations. Two ways to call
into this from Python via `ctypes`:

1. **Read the struct's `length_*` fields, call the module-level
   `OQS_KEM_keypair`/`OQS_SIG_sign`/etc. C functions directly by name**
   (what this repo does). Requires declaring the struct's fixed-size
   fields accurately (order and types must match the C header exactly)
   but function-call binding is simple `argtypes`/`restype`.
2. **Call through the struct's function-pointer fields directly**
   (`kem.contents.keypair(...)`). Requires declaring every function
   pointer's C signature via `ctypes.CFUNCTYPE`/`WINFUNCTYPE` in the
   struct definition itself — more ceremony, and liboqs's own C examples
   (`tests/example_kem.c`) show both call styles are equally valid at the
   C level.

Option 1 was chosen for lower ceremony and because it mirrors how the
project's original `simple_ssh_keygen.py` already called
`OQS_SIG_keypair` — consistent with existing project convention rather
than introducing a second binding style.

## Data flow for a typical operation

See [diagram 02](../diagrams/02-kem-flow.svg) (key exchange) and
[diagram 03](../diagrams/03-signature-flow.svg) (sign/verify) for the
full sequence. In short: `MLKEM768()`/`Signature(alg)` construction calls
`OQS_KEM_new`/`OQS_SIG_new` once and reads real sizes from the returned
struct; each subsequent method call (`generate_keypair`, `encapsulate`,
`sign`, etc.) allocates correctly-sized buffers via
`ctypes.create_string_buffer` and calls the corresponding `OQS_*` C
function, checking its integer return code (`0` = `OQS_SUCCESS`).

## Trust boundary

See [diagram 07](../diagrams/07-trust-boundary.svg). This repo's code is
a thin binding/glue layer; it implements no cryptographic primitives.
Everything upstream (NIST's algorithm standardization, liboqs's C
implementation) is outside this project's control and not audited by
this project. **This repo's own code has not been independently audited
either** — see the README's disclaimer.
