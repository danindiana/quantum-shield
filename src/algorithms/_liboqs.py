"""Shared liboqs.so loader used by kem.py and signature.py.

liboqs itself is not vendored in this repo -- see README.md for how to
build it. This just centralizes the same search-path convention the rest
of the project (quantum_shield.py, simple_ssh_keygen.py) already uses.
"""
import ctypes
import os
from pathlib import Path


class LibOQSNotFoundError(RuntimeError):
    pass


_SEARCH_PATHS = [
    Path.home() / ".local/lib/liboqs.so",
    Path("./liboqs/build/lib/liboqs.so"),
    Path("liboqs.so"),
]

_cached_lib = None


def load_liboqs() -> ctypes.CDLL:
    """Loads and caches liboqs.so, trying each known install location."""
    global _cached_lib
    if _cached_lib is not None:
        return _cached_lib

    lib_dir = str(Path.home() / ".local/lib")
    os.environ["LD_LIBRARY_PATH"] = f"{lib_dir}:{os.environ.get('LD_LIBRARY_PATH', '')}"

    errors = []
    for path in _SEARCH_PATHS:
        try:
            _cached_lib = ctypes.CDLL(str(path))
            return _cached_lib
        except OSError as exc:
            errors.append(f"{path}: {exc}")

    raise LibOQSNotFoundError(
        "liboqs.so not found. Tried:\n  " + "\n  ".join(errors) +
        f"\nBuild it and install to {lib_dir}, or set LD_LIBRARY_PATH."
    )
