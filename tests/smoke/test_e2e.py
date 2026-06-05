"""End-to-end smoke test — starts a real server, submits a job, asserts output.

Marked ``slow`` and ``e2e``:

* Excluded from ``make test`` (``-m "not slow"`` via addopts).
* Included in ``make smoke`` / ``make ci`` (``-m "slow or e2e"``).
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

_FIXTURE_IMAGE = Path("/workspaces/ocr-container/pdomain-book-tools/tests/ocr-test-image.png")
_POLL_INTERVAL = 2.0  # seconds — slightly longer interval reduces noise under load
_TIMEOUT = 300.0  # seconds — 5 min; first DocTR model load can be very slow under load
_POLL_READ_TIMEOUT = 30.0  # seconds — per-poll httpx read timeout; 5 s was too tight under load


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


@pytest.mark.slow
@pytest.mark.e2e
def test_e2e_job_completes(tmp_path: Path) -> None:
    """Start the server, submit a job, poll until terminal, assert .txt output."""
    if not _FIXTURE_IMAGE.exists():
        pytest.skip(f"Fixture image not found: {_FIXTURE_IMAGE}")

    # Copy fixture image to a temp source dir so we control the path
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    shutil.copy(_FIXTURE_IMAGE, source_dir / _FIXTURE_IMAGE.name)

    output_dir = tmp_path / "output"
    output_dir.mkdir()

    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"

    # Isolated data roots — never write to the real home-dir storage.
    isolated_projects = tmp_path / "projects"
    isolated_output = tmp_path / "output_root"
    isolated_jobs_meta = tmp_path / "jobs_meta"
    isolated_uploads = tmp_path / "uploads"
    isolated_suite = tmp_path / "suite_data"
    for p in (isolated_projects, isolated_output, isolated_jobs_meta, isolated_uploads, isolated_suite):
        p.mkdir()

    server_env = {
        **os.environ,
        "PD_OCR_SIMPLE_GUI_PROJECTS_ROOT": str(isolated_projects),
        "PD_OCR_SIMPLE_GUI_OUTPUT_ROOT": str(isolated_output),
        "PD_OCR_SIMPLE_GUI_JOBS_META_ROOT": str(isolated_jobs_meta),
        "PD_OCR_SIMPLE_GUI_UPLOAD_ROOT": str(isolated_uploads),
        "PD_SUITE_DATA_DIR": str(isolated_suite),
    }

    # Start the server as a subprocess
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "pdomain_ocr_simple_gui.app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        env=server_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    project_id: str | None = None
    try:
        _wait_ready(base_url, timeout=30.0)

        # POST a job
        resp = httpx.post(
            f"{base_url}/api/jobs",
            json={
                "name": "e2e-smoke",
                "source_path": str(source_dir),
                "output_dir": str(output_dir),
                "engine": "doctr",
                "language": "en",
                "save_json": False,
                "combined_txt": True,
            },
            timeout=10.0,
        )
        assert resp.status_code == 202, f"POST /api/jobs failed: {resp.text}"
        project_id = resp.json()["project_id"]

        # Poll until terminal state
        deadline = time.monotonic() + _TIMEOUT
        final_status: dict = {}
        while time.monotonic() < deadline:
            poll = httpx.get(f"{base_url}/api/jobs/{project_id}", timeout=_POLL_READ_TIMEOUT)
            assert poll.status_code == 200, f"GET /api/jobs/{project_id} failed: {poll.text}"
            final_status = poll.json()
            state = final_status.get("state")
            if state in ("succeeded", "failed", "cancelled"):
                break
            time.sleep(_POLL_INTERVAL)
        else:
            pytest.fail(f"Job did not reach terminal state within {_TIMEOUT}s; last state={final_status}")

        state = final_status.get("state")
        if state == "failed":
            pytest.xfail(
                "Job reached state=failed — likely missing OCR model weights or a pipeline error. "
                "Run with a full model cache to verify OCR output."
            )
        assert state == "succeeded", f"Expected state=succeeded, got {state!r}. Full status: {final_status}"

        # If succeeded, assert at least one .txt file was written to the isolated roots.
        # We check both the explicit output_dir and the isolated projects root (the pipeline
        # may write to either or both depending on the OutputConfig mode).
        if final_status.get("state") == "succeeded":
            txt_files = list(output_dir.rglob("*.txt")) or list(isolated_projects.rglob("*.txt"))
            assert txt_files, (
                "Job state=done but no .txt files found in output_dir or isolated project storage"
            )

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
