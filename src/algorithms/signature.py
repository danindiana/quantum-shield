"""Signature schemes, bound directly to liboqs's OQS_SIG C API.

Replaces the project's original signature code (formerly in
simple_ssh_keygen.py), which hardcoded per-algorithm key/signature sizes
in a chain of `if "ML-DSA-65" in algorithm: ... = 1952` branches -- its
own comment admitted this was a placeholder ("in practice you'd read the
struct fields"). It also turned out to be *wrong*: it hardcoded
ML-DSA-65's secret key as 1952/4864 bytes; liboqs actually reports
1952/4032 (verified against the installed liboqs.so). This module reads
sizes from the OQS_SIG struct at runtime instead, so it's correct for any
algorithm liboqs supports, not just the ones this file happened to
hardcode -- and can't silently drift from whatever liboqs build is
actually installed.
"""
import ctypes

from ._liboqs import load_liboqs

ALG_ML_DSA_65 = "ML-DSA-65"
ALG_FALCON_512 = "Falcon-512"


class OQS_SIG(ctypes.Structure):
    """Mirrors the fixed-size prefix of liboqs's OQS_SIG struct
    (src/sig/sig.h). Function-pointer fields are intentionally omitted --
    OQS_SIG_keypair/sign/verify are bound as top-level C functions
    instead, same approach as kem.py."""
    _fields_ = [
        ("method_name", ctypes.c_char_p),
        ("alg_version", ctypes.c_char_p),
        ("claimed_nist_level", ctypes.c_uint8),
        ("euf_cma", ctypes.c_bool),
        ("suf_cma", ctypes.c_bool),
        ("sig_with_ctx_support", ctypes.c_bool),
        ("length_public_key", ctypes.c_size_t),
        ("length_secret_key", ctypes.c_size_t),
        ("length_signature", ctypes.c_size_t),
    ]


class SignatureError(RuntimeError):
    """Raised when a liboqs OQS_SIG call fails or the algorithm is unavailable."""


class Signature:
    """A liboqs signature scheme, selected by algorithm name at
    construction time (e.g. "ML-DSA-65", "Falcon-512", any identifier
    liboqs supports -- see `OQS_SIG_algs` in liboqs for the full list).

    NOT AUDITED. This wraps liboqs (Open Quantum Safe) directly; it does
    not implement any cryptographic primitives itself. See README.md for
    the project's disclaimer before using this for anything real.
    """

    def __init__(self, algorithm: str):
        self.algorithm = algorithm
        self._lib = load_liboqs()

        self._lib.OQS_SIG_new.argtypes = [ctypes.c_char_p]
        self._lib.OQS_SIG_new.restype = ctypes.POINTER(OQS_SIG)
        self._lib.OQS_SIG_free.argtypes = [ctypes.POINTER(OQS_SIG)]
        self._lib.OQS_SIG_free.restype = None

        self._lib.OQS_SIG_keypair.argtypes = [
            ctypes.POINTER(OQS_SIG), ctypes.c_char_p, ctypes.c_char_p]
        self._lib.OQS_SIG_keypair.restype = ctypes.c_int

        self._lib.OQS_SIG_sign.argtypes = [
            ctypes.POINTER(OQS_SIG), ctypes.c_char_p, ctypes.POINTER(ctypes.c_size_t),
            ctypes.c_char_p, ctypes.c_size_t, ctypes.c_char_p]
        self._lib.OQS_SIG_sign.restype = ctypes.c_int

        self._lib.OQS_SIG_verify.argtypes = [
            ctypes.POINTER(OQS_SIG), ctypes.c_char_p, ctypes.c_size_t,
            ctypes.c_char_p, ctypes.c_size_t, ctypes.c_char_p]
        self._lib.OQS_SIG_verify.restype = ctypes.c_int

        self._sig = self._lib.OQS_SIG_new(algorithm.encode())
        if not self._sig:
            raise SignatureError(f"{algorithm} unavailable in this liboqs build")

        # Real sizes, read from the struct liboqs handed back -- not hardcoded.
        self.length_public_key = self._sig.contents.length_public_key
        self.length_secret_key = self._sig.contents.length_secret_key
        self.length_signature = self._sig.contents.length_signature

    def __del__(self):
        sig = getattr(self, "_sig", None)
        if sig:
            self._lib.OQS_SIG_free(sig)

    def generate_keypair(self) -> tuple[bytes, bytes]:
        """Returns (public_key, secret_key)."""
        public_key = ctypes.create_string_buffer(self.length_public_key)
        secret_key = ctypes.create_string_buffer(self.length_secret_key)
        rc = self._lib.OQS_SIG_keypair(self._sig, public_key, secret_key)
        if rc != 0:
            raise SignatureError(f"OQS_SIG_keypair failed with code {rc}")
        return public_key.raw, secret_key.raw

    def sign(self, secret_key: bytes, message: bytes) -> bytes:
        """Returns the signature over `message`."""
        if len(secret_key) != self.length_secret_key:
            raise SignatureError(
                f"secret key is {len(secret_key)} bytes, expected {self.length_secret_key}")
        # Buffer sized to the max (some algorithms produce variable-length
        # signatures); the actual length comes back in signature_len.
        signature = ctypes.create_string_buffer(self.length_signature)
        signature_len = ctypes.c_size_t(0)
        rc = self._lib.OQS_SIG_sign(
            self._sig, signature, ctypes.byref(signature_len),
            message, len(message), secret_key)
        if rc != 0:
            raise SignatureError(f"OQS_SIG_sign failed with code {rc}")
        return signature.raw[:signature_len.value]

    def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool:
        """Returns True if `signature` is a valid signature over `message`
        under `public_key`; False otherwise (never raises on a bad
        signature -- that's an expected, not exceptional, outcome)."""
        if len(public_key) != self.length_public_key:
            raise SignatureError(
                f"public key is {len(public_key)} bytes, expected {self.length_public_key}")
        rc = self._lib.OQS_SIG_verify(
            self._sig, message, len(message), signature, len(signature), public_key)
        return rc == 0


class MLDSA65(Signature):
    """ML-DSA-65 (FIPS 204), NIST Security Level 3."""

    def __init__(self):
        super().__init__(ALG_ML_DSA_65)


class Falcon512(Signature):
    """Falcon-512, NIST Security Level 1."""

    def __init__(self):
        super().__init__(ALG_FALCON_512)
