#!/usr/bin/env python3
"""
Client for quantum_shield.py's `server` demo command.

Connects to the demo listener, receives its ML-KEM-768 public key,
encapsulates a shared secret against it, sends the ciphertext back, and
prints the shared secret it derived. Run the server first:

    python3 quantum_shield.py server --port 8443

then in another terminal:

    python3 examples/kem_demo_client.py --port 8443

Both sides should print the same shared secret (hex) if it worked. This
is a protocol demo, not a security protocol: it has no authentication of
the server's public key, no transport encryption, and no replay
protection. See docs/FUTURE_DIRECTIONS.md item 6 for what a real
PQ-TLS integration would need beyond this.
"""
import argparse
import socket
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.algorithms.kem import MLKEM768


def recv_frame(sock: socket.socket) -> bytes:
    (length,) = struct.unpack(">I", _recv_exact(sock, 4))
    return _recv_exact(sock, length)


def send_frame(sock: socket.socket, payload: bytes) -> None:
    sock.sendall(struct.pack(">I", len(payload)) + payload)


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    chunks = []
    remaining = n
    while remaining > 0:
        chunk = sock.recv(remaining)
        if not chunk:
            raise ConnectionError("connection closed before receiving expected data")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8443)
    args = parser.parse_args()

    kem = MLKEM768()

    print(f"🔌 Connecting to {args.host}:{args.port}...")
    with socket.create_connection((args.host, args.port)) as sock:
        public_key = recv_frame(sock)
        print(f"📥 Received server public key ({len(public_key)} bytes)")

        ciphertext, shared_secret = kem.encapsulate(public_key)
        send_frame(sock, ciphertext)
        print(f"📤 Sent ciphertext ({len(ciphertext)} bytes)")

        print(f"🔑 Derived shared secret: {shared_secret.hex()}")


if __name__ == "__main__":
    main()
