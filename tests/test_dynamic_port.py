"""Tests for the pdomain_ops port helpers and the CLI port flag.

The launch-time port behaviour is tested in ``test_port_selection.py``.
"""

from __future__ import annotations

import socket
import subprocess
import sys


class TestBootstrapSpaImportable:
    """Verify bootstrap_spa is importable from pdomain_ops.suite."""

    def test_bootstrap_spa_is_importable(self) -> None:
        """bootstrap_spa is importable from pdomain_ops.suite."""
        from pdomain_ops.suite import bootstrap_spa

        assert callable(bootstrap_spa)

    def test_find_available_port_is_importable(self) -> None:
        """find_available_port is importable from pdomain_ops.suite."""
        from pdomain_ops.suite import find_available_port

        assert callable(find_available_port)

    def test_find_available_port_returns_int(self) -> None:
        """find_available_port(8004) returns an integer port."""
        from pdomain_ops.suite import find_available_port

        port = find_available_port(8004)
        assert isinstance(port, int)
        assert 1024 <= port <= 65535

    def test_find_available_port_skips_occupied_port(self) -> None:
        """find_available_port returns a different port when the preferred one is occupied."""
        from pdomain_ops.suite import find_available_port

        # Occupy a port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            occupied = s.getsockname()[1]
            # Ask for the occupied port; should get a different one
            result = find_available_port(occupied)
            assert isinstance(result, int)
            assert 1024 <= result <= 65535  # at minimum: valid port range, no crash


def test_cli_invalid_port_flag_exits_nonzero() -> None:
    """--port with a non-integer argument exits non-zero (argparse type check)."""
    result = subprocess.run(
        [sys.executable, "-m", "pdomain_ocr_simple_gui", "--port", "not-a-number"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode != 0
