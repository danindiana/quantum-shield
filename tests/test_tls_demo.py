"""Tests for src/protocols/tls/demo.py, against a REAL openssl
s_server/s_client handshake -- not a mocked subprocess. Skips cleanly if
oqs-provider isn't built (same convention as tests/test_pki_certs.py)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.protocols.tls.demo import run_handshake, oqsprovider_available, TLSDemoError

pytestmark = pytest.mark.skipif(
    not oqsprovider_available(),
    reason="oqs-provider not built on this machine (not vendored -- see README)",
)


def test_handshake_succeeds_with_matching_pq_group():
    result = run_handshake(server_group="mlkem768")
    assert result["connected"] is True
    assert result["returncode"] == 0
    assert result["protocol"] == "TLSv1.3"
    assert result["cipher"] not in ("", "(NONE)")


def test_handshake_fails_with_mismatched_groups():
    """The discriminating negative case: if the client and server don't
    share a group, the handshake must fail outright -- proving a
    successful handshake in the positive test above is real evidence
    the requested group was used, not a check that would pass either
    way."""
    result = run_handshake(server_group="mlkem768", client_group="mlkem1024")
    assert result["connected"] is False
    assert result["returncode"] != 0
    assert result["cipher"] == "(NONE)"
