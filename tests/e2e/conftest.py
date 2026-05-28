"""Playwright e2e test fixtures.

Starts the pdomain-ocr-simple-gui server on a free ephemeral port before the
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

import json
import os
import socket
import subprocess
import sys
import time
import uuid
from collections.abc import Generator
from pathlib import Path

import httpx
import pytest

# Minimal valid 1x1 greyscale PNG — used in fixtures that need a real image file
# so the OCR pipeline does not find 0 images and immediately mark the job failed.
_PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x00"
    b"\x00\x00\x00:~\x9bU"
    b"\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01\xe2!\xbc3"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)

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


def _wait_ready(base_url: str, timeout: float = 30.0) -> None:
    """Poll ``/api/config`` until the server responds 200 or timeout expires."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            resp = httpx.get(f"{base_url}/api/config", timeout=2.0)
            if resp.status_code == 200:
                return
        except httpx.TransportError:
            pass
        time.sleep(0.25)
    raise TimeoutError(f"Server at {base_url} did not become ready within {timeout}s")


# ---------------------------------------------------------------------------
# Session-scoped data roots — shared between subprocess server and fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def e2e_data_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Session-scoped temporary directory for all e2e server data."""
    root: Path = tmp_path_factory.mktemp("e2e_server_data")
    for subdir in ("projects", "outputs", "jobs_meta", "uploads"):
        (root / subdir).mkdir(parents=True, exist_ok=True)
    return root


# ---------------------------------------------------------------------------
# Session-scoped server fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def live_server_url(e2e_data_root: Path) -> Generator[str, None, None]:
    """Start the app on a free port; yield the base URL; shut down after session."""
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"

    env = {
        **os.environ,
        # Redirect all server data into the session-scoped tmpdir so tests
        # can write fixtures into the same paths without racing against the
        # real home-dir storage.
        "PD_OCR_SIMPLE_GUI_PROJECTS_ROOT": str(e2e_data_root / "projects"),
        "PD_OCR_SIMPLE_GUI_OUTPUT_ROOT": str(e2e_data_root / "outputs"),
        "PD_OCR_SIMPLE_GUI_JOBS_META_ROOT": str(e2e_data_root / "jobs_meta"),
        "PD_OCR_SIMPLE_GUI_UPLOAD_ROOT": str(e2e_data_root / "uploads"),
        # Use FakeStageDispatcher so browser e2e tests run fast without model weights.
        "PDOMAIN_OCR_FAKE_DISPATCHER": "1",
    }

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
        env=env,
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


# ---------------------------------------------------------------------------
# Seeded-job fixtures (Option B — write artifacts directly to disk)
# ---------------------------------------------------------------------------

_SEEDED_PAGE_SIDECAR = {
    "blocks": [
        {
            "lines": [
                {
                    "words": [
                        {
                            "value": "Hello",
                            "confidence": 0.95,
                            "geometry": [[0.1, 0.1], [0.3, 0.15]],
                        },
                        {
                            "value": "World",
                            "confidence": 0.93,
                            "geometry": [[0.35, 0.1], [0.55, 0.15]],
                        },
                    ]
                }
            ]
        }
    ]
}


def _write_project_json(projects_root: Path, project_id: str, *, output_dir: str) -> None:
    """Write a minimal project.json with succeeded state and one page."""
    proj_dir = projects_root / project_id
    proj_dir.mkdir(parents=True, exist_ok=True)

    spec: dict[str, object] = {
        "project_id": project_id,
        "name": f"e2e-seeded-{project_id[:8]}",
        "source_path": str(proj_dir),  # placeholder — not used for these tests
        "output_dir": output_dir,
        "engine": "doctr",
        "language": "en",
        "save_json": False,
        "combined_txt": False,
        "created_at": "2026-01-01T00:00:00+00:00",
        "last_opened_at": "2026-01-01T00:00:00+00:00",
    }
    status: dict[str, object] = {
        "project_id": project_id,
        "state": "succeeded",
        "page_count": 1,
        "pages_done": 1,
        "pages": [
            {
                "page_idx": 0,
                "page_name": "page-001",
                "state": "succeeded",
                "text_preview": "Hello World",
            }
        ],
    }
    data = {"spec": spec, "status": status}
    (proj_dir / "project.json").write_text(json.dumps(data, indent=2), encoding="utf-8")


def _write_page_sidecar(projects_root: Path, project_id: str) -> None:
    """Write the per-page JSON sidecar that /api/pages/.../words reads."""
    pages_dir = projects_root / project_id / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    # Page name matches what was written in the status pages list.
    (pages_dir / "page-001.json").write_text(json.dumps(_SEEDED_PAGE_SIDECAR, indent=2), encoding="utf-8")


def _write_output_txt(outputs_root: Path, project_id: str) -> None:
    """Write placeholder .txt and .json outputs so the download endpoint has content."""
    out_dir = outputs_root / project_id
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "page-001.txt").write_text("Hello World\n", encoding="utf-8")
    (out_dir / "page-001.json").write_text('{"text": "Hello World"}\n', encoding="utf-8")


def _write_job_meta(jobs_meta_root: Path, project_id: str, mode: str) -> None:
    """Write the output_mode sidecar that GET /api/jobs/{id} reads."""
    meta_dir = jobs_meta_root / project_id
    meta_dir.mkdir(parents=True, exist_ok=True)
    (meta_dir / "output_mode.json").write_text(json.dumps({"mode": mode}), encoding="utf-8")


@pytest.fixture(scope="session")
def seeded_job_id(e2e_data_root: Path) -> str:
    """Yield a project_id for a completed (non-managed) job pre-seeded on disk.

    The job has:
    - status = succeeded, 1 page
    - a page sidecar with 2 words (for word-overlay tests)
    - output_mode = next_to_source (no download button)
    """
    project_id = "e2etestjob-" + uuid.uuid4().hex[:12]
    projects_root = e2e_data_root / "projects"
    outputs_root = e2e_data_root / "outputs"
    jobs_meta_root = e2e_data_root / "jobs_meta"

    out_dir = str(outputs_root / project_id)
    _write_project_json(projects_root, project_id, output_dir=out_dir)
    _write_page_sidecar(projects_root, project_id)
    _write_output_txt(outputs_root, project_id)
    _write_job_meta(jobs_meta_root, project_id, mode="next_to_source")
    return project_id


def _write_project_json_2page(projects_root: Path, project_id: str, *, output_dir: str) -> None:
    """Write a minimal project.json with succeeded state and TWO pages."""
    proj_dir = projects_root / project_id
    proj_dir.mkdir(parents=True, exist_ok=True)

    spec: dict[str, object] = {
        "project_id": project_id,
        "name": f"e2e-2page-{project_id[:8]}",
        "source_path": str(proj_dir),
        "output_dir": output_dir,
        "engine": "doctr",
        "language": "en",
        "save_json": False,
        "combined_txt": False,
        "created_at": "2026-01-01T00:00:00+00:00",
        "last_opened_at": "2026-01-01T00:00:00+00:00",
    }
    status: dict[str, object] = {
        "project_id": project_id,
        "state": "succeeded",
        "page_count": 2,
        "pages_done": 2,
        "pages": [
            {
                "page_idx": 0,
                "page_name": "page-001",
                "state": "succeeded",
                "text_preview": "Hello World",
            },
            {
                "page_idx": 1,
                "page_name": "page-002",
                "state": "succeeded",
                "text_preview": "Second Page",
            },
        ],
    }
    data = {"spec": spec, "status": status}
    (proj_dir / "project.json").write_text(json.dumps(data, indent=2), encoding="utf-8")


def _write_page_sidecars_2page(projects_root: Path, project_id: str) -> None:
    """Write two per-page JSON sidecars."""
    pages_dir = projects_root / project_id / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    for name in ("page-001", "page-002"):
        (pages_dir / f"{name}.json").write_text(json.dumps(_SEEDED_PAGE_SIDECAR, indent=2), encoding="utf-8")


@pytest.fixture(scope="session")
def seeded_2page_job_id(e2e_data_root: Path) -> str:
    """Yield a project_id for a completed job with TWO pages.

    Used for prev/next navigation tests that require a multi-page job.
    """
    project_id = "e2etest2pg-" + uuid.uuid4().hex[:12]
    projects_root = e2e_data_root / "projects"
    outputs_root = e2e_data_root / "outputs"
    jobs_meta_root = e2e_data_root / "jobs_meta"

    out_dir = str(outputs_root / project_id)
    _write_project_json_2page(projects_root, project_id, output_dir=out_dir)
    _write_page_sidecars_2page(projects_root, project_id)
    _write_output_txt(outputs_root, project_id)
    _write_job_meta(jobs_meta_root, project_id, mode="next_to_source")
    return project_id


@pytest.fixture(scope="session")
def live_server_url_cpu(e2e_data_root: Path) -> Generator[str, None, None]:
    """Start the app on a free port with PDOMAIN_GPU_BACKEND=cpu forced.

    Used for gpu-help-toggle tests: when gpu_available=False the toggle is
    rendered; when gpu_available=True it is absent from the DOM.
    """
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"

    env = {
        **os.environ,
        "PD_OCR_SIMPLE_GUI_PROJECTS_ROOT": str(e2e_data_root / "projects"),
        "PD_OCR_SIMPLE_GUI_OUTPUT_ROOT": str(e2e_data_root / "outputs"),
        "PD_OCR_SIMPLE_GUI_JOBS_META_ROOT": str(e2e_data_root / "jobs_meta"),
        "PD_OCR_SIMPLE_GUI_UPLOAD_ROOT": str(e2e_data_root / "uploads"),
        "PDOMAIN_OCR_FAKE_DISPATCHER": "1",
        # Force CPU so gpu_available=False → gpu-help-toggle is rendered.
        "PDOMAIN_GPU_BACKEND": "cpu",
    }

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
        env=env,
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


@pytest.fixture(scope="session")
def seeded_rerun_job_id(e2e_data_root: Path) -> str:
    """Yield a project_id for a succeeded job that has a real source image.

    Used for rerun tests (rerun-all, rerun-doctr, rerun-tesseract) that POST
    to the rerun endpoint.  Having a real PNG in source_path ensures the fake
    dispatcher can process the job and return it to succeeded state after the
    rerun, rather than immediately marking it failed due to 0 images.
    """
    project_id = "e2ererun-" + uuid.uuid4().hex[:12]
    projects_root = e2e_data_root / "projects"
    outputs_root = e2e_data_root / "outputs"
    jobs_meta_root = e2e_data_root / "jobs_meta"

    # Write the source image into the project dir so collect_images finds it.
    proj_dir = projects_root / project_id
    proj_dir.mkdir(parents=True, exist_ok=True)
    (proj_dir / "page-001.png").write_bytes(_PNG_1X1)

    out_dir = str(outputs_root / project_id)
    _write_project_json(projects_root, project_id, output_dir=out_dir)
    _write_page_sidecar(projects_root, project_id)
    _write_output_txt(outputs_root, project_id)
    _write_job_meta(jobs_meta_root, project_id, mode="next_to_source")
    return project_id


@pytest.fixture(scope="session")
def seeded_managed_job_id(e2e_data_root: Path) -> str:
    """Yield a project_id for a completed managed-mode job pre-seeded on disk.

    The job has:
    - status = succeeded, 1 page
    - output_mode = managed  → ResultsPage shows the download button
    - output artifacts in outputs_root/<id>/ so /api/jobs/{id}/download works
    """
    project_id = "e2etestmgd-" + uuid.uuid4().hex[:12]
    projects_root = e2e_data_root / "projects"
    outputs_root = e2e_data_root / "outputs"
    jobs_meta_root = e2e_data_root / "jobs_meta"

    out_dir = str(outputs_root / project_id)
    _write_project_json(projects_root, project_id, output_dir=out_dir)
    _write_page_sidecar(projects_root, project_id)
    _write_output_txt(outputs_root, project_id)
    _write_job_meta(jobs_meta_root, project_id, mode="managed")
    return project_id
