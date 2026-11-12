"""Tests for how the e2e conftest boots each live server.

Under ``pytest -n auto`` every xdist worker boots its own server. When the
port was chosen by binding a probe socket and closing it, two workers could
get the same port: the second uvicorn failed to bind, but its readiness poll
got a 200 from the first worker's server. That worker then ran against
another worker's data ("Page not found" for its own seeded job) and saw
``Connection refused`` once the owning worker shut its server down.
"""

from __future__ import annotations

import subprocess
import sys
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from tests.e2e import conftest as e2e_conftest


class _DecoyHandler(BaseHTTPRequestHandler):
    """Answers 200 to every GET, like a healthy server owned by someone else."""

    def do_GET(self) -> None:
        body = b"{}"
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        _ = self.wfile.write(body)


@pytest.fixture
def decoy_port() -> Iterator[int]:
    """Run an HTTP server on a free port for the length of one test."""
    server = HTTPServer(("127.0.0.1", 0), _DecoyHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()


def _server_env(root: Path) -> dict[str, str]:
    for sub in ("projects", "outputs", "jobs_meta", "uploads", "suite_data"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    return {
        "PD_OCR_SIMPLE_GUI_PROJECTS_ROOT": str(root / "projects"),
        "PD_OCR_SIMPLE_GUI_OUTPUT_ROOT": str(root / "outputs"),
        "PD_OCR_SIMPLE_GUI_JOBS_META_ROOT": str(root / "jobs_meta"),
        "PD_OCR_SIMPLE_GUI_UPLOAD_ROOT": str(root / "uploads"),
        "PD_SUITE_DATA_DIR": str(root / "suite_data"),
        "PDOMAIN_OCR_FAKE_DISPATCHER": "1",
    }


def test_boot_server_never_yields_a_port_another_server_holds(
    decoy_port: int, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A port already served by another process must not be handed to tests.

    The old ``_free_port`` is forced to return the decoy's port, which is what
    a cross-worker collision looks like. ``raising=False`` keeps the test valid
    once the conftest no longer picks ports itself.
    """
    monkeypatch.setattr(e2e_conftest, "_free_port", lambda: decoy_port, raising=False)
    monkeypatch.setattr(e2e_conftest, "_assert_frontend_built", lambda: None)

    gen = e2e_conftest._boot_server(_server_env(tmp_path))
    try:
        base_url = next(gen)
    except (TimeoutError, RuntimeError):
        return  # refusing to start is also correct; using the decoy is not
    try:
        assert base_url != f"http://127.0.0.1:{decoy_port}", "booted server answered on the decoy's port"
    finally:
        gen.close()


def test_wait_for_bound_port_fails_fast_when_server_exits(tmp_path: Path) -> None:
    """A server that exits before reporting its port is an error, not a wait."""
    log_path = tmp_path / "server.log"
    _ = log_path.write_text("ERROR: [Errno 98] address already in use\n", encoding="utf-8")
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    _ = proc.wait(timeout=10)

    with pytest.raises(RuntimeError, match="exited"):
        _ = e2e_conftest._wait_for_bound_port(log_path, proc, timeout=10.0)


def test_wait_for_bound_port_reads_uvicorn_startup_line(tmp_path: Path) -> None:
    """The port comes from uvicorn's own "running on" log line."""
    log_path = tmp_path / "server.log"
    _ = log_path.write_text(
        "INFO:     Uvicorn running on http://127.0.0.1:41234 (Press CTRL+C to quit)\n",
        encoding="utf-8",
    )
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        assert e2e_conftest._wait_for_bound_port(log_path, proc, timeout=5.0) == 41234
    finally:
        proc.kill()
        _ = proc.wait(timeout=10)
