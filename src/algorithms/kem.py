"""ML-KEM-768 key encapsulation, bound directly to liboqs's OQS_KEM C API.

Reads real key/ciphertext/shared-secret sizes from the OQS_KEM struct
liboqs hands back at runtime, instead of hardcoding per-algorithm sizes
(the pitfall the project's earlier signature code fell into -- see
signature.py's docstring and the README).

Binds the top-level OQS_KEM_keypair/encaps/decaps C functions by name
rather than calling through the struct's function-pointer fields -- same
low-ceremony pattern the rest of this project already uses, and it avoids
needing WINFUNCTYPE/CFUNCTYPE plumbing for five different function
pointer signatures.
"""
import ctypes

from ._liboqs import load_liboqs

ALG_ML_KEM_768 = "ML-KEM-768"


class OQS_KEM(ctypes.Structure):
    """Mirrors the fixed-size prefix of liboqs's OQS_KEM struct
    (src/kem/kem.h). Function-pointer fields are intentionally omitted --
    not called through this struct, see module docstring."""
    _fields_ = [
        ("method_name", ctypes.c_char_p),
        ("alg_version", ctypes.c_char_p),
        ("claimed_nist_level", ctypes.c_uint8),
        ("ind_cca", ctypes.c_bool),
        ("length_public_key", ctypes.c_size_t),
        ("length_secret_key", ctypes.c_size_t),
        ("length_ciphertext", ctypes.c_size_t),
        ("length_shared_secret", ctypes.c_size_t),
        ("length_keypair_seed", ctypes.c_size_t),
        ("length_encaps_seed", ctypes.c_size_t),
    ]


class KEMError(RuntimeError):
    """Raised when a liboqs OQS_KEM call fails or the algorithm is unavailable."""


class MLKEM768:
    """ML-KEM-768 (FIPS 203), NIST Security Level 3.

    NOT AUDITED. This wraps liboqs (Open Quantum Safe) directly; it does
    not implement any cryptographic primitives itself. See README.md for
    the project's disclaimer before using this for anything real.
    """

    def __init__(self):
        self._lib = load_liboqs()

        self._lib.OQS_KEM_new.argtypes = [ctypes.c_char_p]
        self._lib.OQS_KEM_new.restype = ctypes.POINTER(OQS_KEM)
        self._lib.OQS_KEM_free.argtypes = [ctypes.POINTER(OQS_KEM)]
        self._lib.OQS_KEM_free.restype = None

        self._lib.OQS_KEM_keypair.argtypes = [
            ctypes.POINTER(OQS_KEM), ctypes.c_char_p, ctypes.c_char_p]
        self._lib.OQS_KEM_keypair.restype = ctypes.c_int

        self._lib.OQS_KEM_encaps.argtypes = [
            ctypes.POINTER(OQS_KEM), ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p]
        self._lib.OQS_KEM_encaps.restype = ctypes.c_int

        self._lib.OQS_KEM_decaps.argtypes = [
            ctypes.POINTER(OQS_KEM), ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p]
        self._lib.OQS_KEM_decaps.restype = ctypes.c_int

        self._kem = self._lib.OQS_KEM_new(ALG_ML_KEM_768.encode())
        if not self._kem:
            raise KEMError(f"{ALG_ML_KEM_768} unavailable in this liboqs build")

        # Real sizes, read from the struct liboqs handed back -- not hardcoded.
        self.length_public_key = self._kem.contents.length_public_key
        self.length_secret_key = self._kem.contents.length_secret_key
        self.length_ciphertext = self._kem.contents.length_ciphertext
        self.length_shared_secret = self._kem.contents.length_shared_secret

    def __del__(self):
        kem = getattr(self, "_kem", None)
        if kem:
            self._lib.OQS_KEM_free(kem)

    def generate_keypair(self) -> tuple[bytes, bytes]:
        """Returns (public_key, secret_key)."""
        public_key = ctypes.create_string_buffer(self.length_public_key)
        secret_key = ctypes.create_string_buffer(self.length_secret_key)
        rc = self._lib.OQS_KEM_keypair(self._kem, public_key, secret_key)
        if rc != 0:
            raise KEMError(f"OQS_KEM_keypair failed with code {rc}")
        return public_key.raw, secret_key.raw

    def encapsulate(self, public_key: bytes) -> tuple[bytes, bytes]:
        """Returns (ciphertext, shared_secret)."""
        if len(public_key) != self.length_public_key:
            raise KEMError(
                f"public key is {len(public_key)} bytes, expected {self.length_public_key}")
        ciphertext = ctypes.create_string_buffer(self.length_ciphertext)
        shared_secret = ctypes.create_string_buffer(self.length_shared_secret)
        rc = self._lib.OQS_KEM_encaps(self._kem, ciphertext, shared_secret, public_key)
        if rc != 0:
            raise KEMError(f"OQS_KEM_encaps failed with code {rc}")
        return ciphertext.raw, shared_secret.raw

    def decapsulate(self, secret_key: bytes, ciphertext: bytes) -> bytes:
        """Returns the shared secret."""
        if len(secret_key) != self.length_secret_key:
            raise KEMError(
                f"secret key is {len(secret_key)} bytes, expected {self.length_secret_key}")
        if len(ciphertext) != self.length_ciphertext:
            raise KEMError(
                f"ciphertext is {len(ciphertext)} bytes, expected {self.length_ciphertext}")
        shared_secret = ctypes.create_string_buffer(self.length_shared_secret)
        rc = self._lib.OQS_KEM_decaps(self._kem, shared_secret, ciphertext, secret_key)
        if rc != 0:
            raise KEMError(f"OQS_KEM_decaps failed with code {rc}")
        return shared_secret.raw
