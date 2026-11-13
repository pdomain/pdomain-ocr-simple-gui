"""The smoke server must bind the port the kernel assigns.

Probing a free port and then binding it leaves a gap. Another process can
take that port. The smoke readiness poll then treats the other process as
its own server.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from tests.smoke import test_e2e as smoke_e2e


class _DecoyHandler(BaseHTTPRequestHandler):
    """Answers 200 to every GET, like a server owned by someone else."""

    def do_GET(self) -> None:
        body = b"{}"
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        _ = self.wfile.write(body)


@pytest.fixture
def decoy_port() -> Iterator[int]:
    """Run an HTTP server on a kernel-chosen port for one test."""
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


def test_smoke_start_does_not_adopt_a_port_another_process_holds(
    decoy_port: int, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The URL yielded by the smoke start must not be a port someone else holds.

    Forcing the old probe to return the decoy's port is the collision. The
    start must still yield a different URL.
    """
    monkeypatch.setattr(smoke_e2e, "_free_port", lambda: decoy_port, raising=False)
    server = smoke_e2e.start_smoke_server(_server_env(tmp_path), tmp_path)
    base_url = next(server)
    try:
        assert base_url != f"http://127.0.0.1:{decoy_port}"
    finally:
        server.close()
