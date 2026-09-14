"""Orchestrates a real TLS 1.3 handshake using a post-quantum KEM group
(ML-KEM-768 by default) for key exchange, via `openssl s_server` /
`s_client` + `oqs-provider`. This module implements no TLS protocol
logic and no cryptography itself -- it starts/stops real `openssl`
subprocesses and inspects their exit codes and diagnostic output to
confirm the PQ group was actually negotiated, the same "delegate the
protocol, orchestrate and verify" boundary as `test_pq_tls.py` and
`src/pki/certs.py`.

**A real limitation, discovered this session, that shapes this
module's design:** authenticating a live TLS connection with a
post-quantum-*signed certificate* requires OpenSSL 3.2+ (stated
explicitly in oqs-provider's own USAGE.md: "using QSC CA's and server
certificates is not supported in versions prior to OpenSSL 3.2").
Generating such a certificate works fine on OpenSSL 3.0 (that's exactly
what `test_pq_tls.py` and `src/pki/certs.py` already do) -- but actually
loading one into `s_server` for a live handshake does not, confirmed by
reproducing the exact failure ("unknown certificate type") against this
project's OpenSSL 3.0.2 (both locally and in CI). So this demo
authenticates the server with a classical ECDSA certificate (OpenSSL's
own, no oqs-provider involved) and uses oqs-provider only for the KEM
group. This is not a workaround for a missing feature -- it's the
realistic near-term deployment shape (hybrid: classical authentication
today, post-quantum key exchange today) -- see
docs/FUTURE_DIRECTIONS.md for what full PQ-authenticated TLS would need.

**Why "handshake succeeded" is sufficient proof the PQ group was used,
without parsing a "negotiated group" field:** both server and client are
configured with `-groups <group>` naming the SAME single group. There is
no other group either side could have silently fallen back to.
Confirmed this is a real, discriminating test (not a trivial always-true
check) by reproducing the negative case: pointing the client at a
*different* group than the server offers fails the handshake outright
(nonzero exit code, "Cipher is (NONE)", an explicit
"sslv3 alert handshake failure") -- see tests/test_tls_demo.py.

NOT AUDITED -- see the project README's disclaimer.
"""
import contextlib
import os
import socket
import subprocess
import tempfile
import time
from pathlib import Path


class TLSDemoError(RuntimeError):
    """Raised for setup failures (oqs-provider missing, server failed to
    start) -- NOT for a failed handshake, which run_handshake() reports
    in its returned dict instead, since that's a real possible outcome
    worth returning rather than raising."""


def oqsprovider_available() -> bool:
    return (Path.home() / ".local/lib/ossl-modules/oqsprovider.so").exists()


def _openssl_env() -> dict:
    env = dict(os.environ)
    home = Path.home()
    env["OPENSSL_MODULES"] = str(home / ".local/lib/ossl-modules")
    env["LD_LIBRARY_PATH"] = f"{home / '.local/lib'}:{env.get('LD_LIBRARY_PATH', '')}"
    return env


def _free_port() -> int:
    """Binds to an OS-assigned free port, then releases it -- avoids
    hardcoding a port that might already be in use, especially if
    multiple CI jobs ran concurrently."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def generate_classical_cert(directory: Path) -> tuple:
    """Generates a self-signed EC (P-256) cert + key via plain openssl --
    no oqs-provider involved, since this authenticates the connection,
    not the key exchange. Returns (key_path, cert_path)."""
    key_path = directory / "classical.key"
    cert_path = directory / "classical.crt"
    subprocess.run(
        ["openssl", "req", "-x509", "-new", "-newkey", "ec",
         "-pkeyopt", "ec_paramgen_curve:P-256",
         "-keyout", str(key_path), "-out", str(cert_path),
         "-days", "1", "-nodes", "-subj", "/CN=localhost"],
        check=True, capture_output=True, text=True,
    )
    return key_path, cert_path


def run_handshake(server_group: str = "mlkem768", client_group: str = None,
                   timeout: float = 10.0) -> dict:
    """Starts a real openssl s_server authenticated with a classical EC
    cert, offering only `server_group` (a KEM name oqs-provider
    registers) for key exchange, connects to it with s_client offering
    `client_group` (defaults to the same as server_group), and returns:

        {"connected": bool, "cipher": str, "protocol": str,
         "returncode": int, "raw_output": str}

    Pass a deliberately different client_group to get a reliable
    negative case (see module docstring) -- useful for tests proving
    this check actually discriminates. Raises TLSDemoError if
    oqs-provider isn't available or the server fails to start; a failed
    handshake itself is reported in the dict, not raised.
    """
    if not oqsprovider_available():
        raise TLSDemoError(
            "oqs-provider not built (see README 'Building liboqs') -- "
            "needed for TLS group registration, not just certificates")

    client_group = client_group or server_group
    env = _openssl_env()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        key_path, cert_path = generate_classical_cert(tmpdir)
        port = _free_port()

        server = subprocess.Popen(
            ["openssl", "s_server", "-cert", str(cert_path), "-key", str(key_path),
             "-provider", "default", "-provider", "oqsprovider",
             "-groups", server_group, "-accept", str(port), "-quiet"],
            env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        try:
            time.sleep(1.0)  # let s_server bind and start listening
            if server.poll() is not None:
                raise TLSDemoError(
                    f"s_server exited immediately (code {server.returncode}): "
                    f"{server.stdout.read()}")

            client = subprocess.run(
                ["openssl", "s_client", "-connect", f"127.0.0.1:{port}",
                 "-groups", client_group, "-provider", "default", "-provider", "oqsprovider",
                 "-CAfile", str(cert_path)],
                stdin=subprocess.DEVNULL, env=env, capture_output=True, text=True,
                timeout=timeout,
            )
        finally:
            server.terminate()
            with contextlib.suppress(subprocess.TimeoutExpired):
                server.wait(timeout=5)

        output = client.stdout + client.stderr
        cipher = ""
        protocol = ""
        for line in output.splitlines():
            if line.startswith("New,") and "Cipher is" in line:
                # e.g. "New, TLSv1.3, Cipher is TLS_AES_256_GCM_SHA384"
                parts = line.split(",")
                protocol = parts[1].strip() if len(parts) > 1 else ""
                cipher = line.split("Cipher is", 1)[1].strip()

        connected = client.returncode == 0 and cipher not in ("", "(NONE)")

        return {
            "connected": connected,
            "cipher": cipher,
            "protocol": protocol,
            "returncode": client.returncode,
            "raw_output": output,
        }
