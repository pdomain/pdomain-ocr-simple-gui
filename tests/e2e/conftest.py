"""Playwright e2e test fixtures.

Starts the pd-ocr-simple-gui server on a free ephemeral port before the
session and tears it down afterwards.  Tests access the URL via the
``live_server_url`` fixture.

All tests in ``tests/e2e/`` are marked ``e2e`` and ``slow`` so they are
excluded from ``make test`` (which passes ``-m "not slow"``) and included
in ``make e2e-browser``.

Usage::

    make e2e-browser          # runs only tests/e2e/ with playwright
    PLAYWRIGHT_BROWSERS_PATH=/cache/shared-ai/ms-playwright make e2e-browser
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from collections.abc import Generator

import httpx
import pytest

# ---------------------------------------------------------------------------
# Browser path — prefer the shared cache used by this workspace
# ---------------------------------------------------------------------------
_SHARED_BROWSERS = "/cache/shared-ai/ms-playwright"
if os.path.isdir(_SHARED_BROWSERS) and "PLAYWRIGHT_BROWSERS_PATH" not in os.environ:
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = _SHARED_BROWSERS

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _free_port() -> int:
    """Return an ephemeral free TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]  # type: ignore[return-value]


def _wait_ready(base_url: str, timeout: float = 20.0) -> None:
    """Poll ``/api/health`` until the server responds or timeout expires."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            resp = httpx.get(f"{base_url}/api/health", timeout=2.0)
            if resp.status_code == 200:
                return
        except httpx.TransportError:
            pass
        time.sleep(0.25)
    raise TimeoutError(f"Server at {base_url} did not become ready within {timeout}s")


# ---------------------------------------------------------------------------
# Session-scoped server fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def live_server_url() -> Generator[str, None, None]:
    """Start the app on a free port; yield the base URL; shut down after session."""
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "pd_ocr_simple_gui.app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        _wait_ready(base_url, timeout=30.0)
        yield base_url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
