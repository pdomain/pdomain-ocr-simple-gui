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
import tempfile
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
# Safety guards
# ---------------------------------------------------------------------------


def _assert_suite_data_dir_is_tmp(suite_data_dir: str) -> None:
    """Raise AssertionError when *suite_data_dir* is not a safe tmp path.

    Called from ``_boot_server`` before each server launch to prevent the
    prefs-reset autouse fixture from overwriting real user data when a
    developer forgets to set the isolation env var.
    """
    tmp = tempfile.gettempdir()
    assert suite_data_dir and suite_data_dir.startswith(("/tmp", tmp)), (
        "PD_SUITE_DATA_DIR must be set to a tmp path before running e2e tests "
        f"(current value: {suite_data_dir!r}). This prevents prefs-reset from overwriting real "
        "user data."
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _assert_under_tmp(path: Path, tmp_root: Path) -> None:
    """Raise RuntimeError when *path* does not resolve under *tmp_root*.

    Called from e2e seeding fixtures before writing any artifact to disk so
    that a misconfigured data-root cannot accidentally write into a real user
    directory.  Both the exact root and any descendant are accepted.
    """
    resolved = Path(path).resolve()
    root_resolved = tmp_root.resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise RuntimeError(f"e2e fixture refusing to write outside tmpdir: {resolved}")


def _guard_seeded_roots(
    projects_root: Path,
    outputs_root: Path,
    jobs_meta_root: Path,
    tmp_root: Path,
) -> None:
    """Assert all three seeded-artifact roots are under *tmp_root*.

    DRY guard used by every seeding fixture to prevent writing outside
    the session-scoped tmpdir when data roots are misconfigured.
    """
    _assert_under_tmp(projects_root, tmp_root)
    _assert_under_tmp(outputs_root, tmp_root)
    _assert_under_tmp(jobs_meta_root, tmp_root)


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


def _boot_server(env_overrides: dict[str, str], *, ready_timeout: float = 30.0) -> Generator[str, None, None]:
    """Boot the app as a uvicorn subprocess and yield its base URL.

    Shared boot logic for every live-server fixture. ``env_overrides`` is layered
    on top of the current ``os.environ`` so callers select the dispatcher / GPU
    backend / data roots they need. The server is polled on ``/api/config`` for
    readiness and terminated on teardown.
    """
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"

    env = {**os.environ, **env_overrides}
    _assert_suite_data_dir_is_tmp(env.get("PD_SUITE_DATA_DIR", ""))

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
        _wait_ready(base_url, timeout=ready_timeout)
        yield base_url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


# ---------------------------------------------------------------------------
# Session-scoped data roots — shared between subprocess server and fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def e2e_data_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Session-scoped temporary directory for all e2e server data."""
    root: Path = tmp_path_factory.mktemp("e2e_server_data")
    for subdir in ("projects", "outputs", "jobs_meta", "uploads", "suite_data", "suite_data_real"):
        subpath = root / subdir
        subpath.mkdir(parents=True, exist_ok=True)
        _assert_under_tmp(subpath, root)
    return root


# ---------------------------------------------------------------------------
# Session-scoped server fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def live_server_url(e2e_data_root: Path) -> Generator[str, None, None]:
    """Start the app on a free port; yield the base URL; shut down after session."""
    env = {
        # Redirect all server data into the session-scoped tmpdir so tests
        # can write fixtures into the same paths without racing against the
        # real home-dir storage.
        "PD_OCR_SIMPLE_GUI_PROJECTS_ROOT": str(e2e_data_root / "projects"),
        "PD_OCR_SIMPLE_GUI_OUTPUT_ROOT": str(e2e_data_root / "outputs"),
        "PD_OCR_SIMPLE_GUI_JOBS_META_ROOT": str(e2e_data_root / "jobs_meta"),
        "PD_OCR_SIMPLE_GUI_UPLOAD_ROOT": str(e2e_data_root / "uploads"),
        # Redirect pdomain-ops suite data (including ui-prefs.json) into the
        # session-scoped tmpdir so prefs mutations in one test never bleed into
        # another test or the real user prefs file on disk.
        # PD_SUITE_DATA_DIR is per-xdist-worker because tmp_path_factory is
        # worker-scoped; combined with reset_prefs (function-scoped autouse)
        # this gives full per-test prefs isolation.
        "PD_SUITE_DATA_DIR": str(e2e_data_root / "suite_data"),
        # Use FakeStageDispatcher so browser e2e tests run fast without model weights.
        "PDOMAIN_OCR_FAKE_DISPATCHER": "1",
    }
    yield from _boot_server(env)


# ---------------------------------------------------------------------------
# Function-scoped prefs reset — autouse for every e2e test
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_prefs(live_server_url: str) -> None:
    """Reset app prefs to defaults before each e2e test.

    Prefs (default_engine, recent_projects, etc.) are persisted to a JSON
    file on the server subprocess's filesystem.  Under pytest-xdist each
    worker runs multiple tests against the same session-scoped live server;
    any test that mutates prefs via PUT /api/prefs would otherwise pollute
    subsequent tests assigned to the same worker.

    This fixture PUTs the FULL AppPrefs defaults immediately before each
    test so every test starts from a known clean state.  It is autouse so
    no individual test needs to opt in.

    NOTE: it must send an explicit full-defaults body, NOT an empty ``{}``.
    PUT /api/prefs read-modify-merges a partial body (the clobber-proof
    fix), so an empty payload is a no-op that would leak prefs across tests
    on the same xdist worker.  Sending every field at its default value is
    what actually resets the stored prefs.
    """
    from pdomain_ocr_simple_gui.models import AppPrefs

    httpx.put(
        f"{live_server_url}/api/prefs",
        json=AppPrefs().model_dump(mode="json"),
        timeout=5.0,
    )


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
    _assert_under_tmp(projects_root, e2e_data_root)
    _assert_under_tmp(outputs_root, e2e_data_root)
    _assert_under_tmp(jobs_meta_root, e2e_data_root)

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
    _guard_seeded_roots(projects_root, outputs_root, jobs_meta_root, e2e_data_root)

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
    env = {
        "PD_OCR_SIMPLE_GUI_PROJECTS_ROOT": str(e2e_data_root / "projects"),
        "PD_OCR_SIMPLE_GUI_OUTPUT_ROOT": str(e2e_data_root / "outputs"),
        "PD_OCR_SIMPLE_GUI_JOBS_META_ROOT": str(e2e_data_root / "jobs_meta"),
        "PD_OCR_SIMPLE_GUI_UPLOAD_ROOT": str(e2e_data_root / "uploads"),
        "PD_SUITE_DATA_DIR": str(e2e_data_root / "suite_data"),
        "PDOMAIN_OCR_FAKE_DISPATCHER": "1",
        # Force CPU so gpu_available=False → gpu-help-toggle is rendered.
        "PDOMAIN_GPU_BACKEND": "cpu",
    }
    yield from _boot_server(env)


@pytest.fixture(scope="session")
def live_server_url_containerized(e2e_data_root: Path) -> Generator[str, None, None]:
    """Start the app on a free port with PD_OCR_SIMPLE_GUI_IS_CONTAINERIZED=1.

    Used for source-hide tests: in local+containerized mode, both an "Upload"
    picker and an "Existing folder or zip" path picker are rendered.  Choosing
    one hides the other (B-HOME-001 / B-HOME-003); clearing restores both
    (B-HOME-004).
    """
    env = {
        "PD_OCR_SIMPLE_GUI_PROJECTS_ROOT": str(e2e_data_root / "projects"),
        "PD_OCR_SIMPLE_GUI_OUTPUT_ROOT": str(e2e_data_root / "outputs"),
        "PD_OCR_SIMPLE_GUI_JOBS_META_ROOT": str(e2e_data_root / "jobs_meta"),
        "PD_OCR_SIMPLE_GUI_UPLOAD_ROOT": str(e2e_data_root / "uploads"),
        "PD_SUITE_DATA_DIR": str(e2e_data_root / "suite_data"),
        "PDOMAIN_OCR_FAKE_DISPATCHER": "1",
        # Force local+containerized so both pickers render.
        "PD_OCR_SIMPLE_GUI_IS_CONTAINERIZED": "1",
    }
    yield from _boot_server(env)


@pytest.fixture(scope="session")
def live_server_url_real_ocr(e2e_data_root: Path) -> Generator[str, None, None]:
    """Live server running the REAL OCR engine on the GPU. Opt-in (real_ocr).

    Mirrors ``live_server_url`` but intentionally OMITS
    ``PDOMAIN_OCR_FAKE_DISPATCHER`` (so the real LocalStageDispatcher + DocTR
    runner execute) and sets ``PDOMAIN_GPU_BACKEND=local``. Data roots are
    isolated from the fake-dispatcher fixtures so the real engine never collides
    with the seeded artifacts. Used only by Tier-B ``real_ocr`` tests; never in
    default CI.
    """
    env = {
        "PD_OCR_SIMPLE_GUI_PROJECTS_ROOT": str(e2e_data_root / "rp"),
        "PD_OCR_SIMPLE_GUI_OUTPUT_ROOT": str(e2e_data_root / "ro"),
        "PD_OCR_SIMPLE_GUI_JOBS_META_ROOT": str(e2e_data_root / "rj"),
        "PD_OCR_SIMPLE_GUI_UPLOAD_ROOT": str(e2e_data_root / "ru"),
        "PD_SUITE_DATA_DIR": str(e2e_data_root / "suite_data_real"),
        "PDOMAIN_GPU_BACKEND": "local",
        # NOTE: PDOMAIN_OCR_FAKE_DISPATCHER intentionally NOT set.
    }
    # Real OCR cold-start (model load) is slower than the fake dispatcher, so
    # give the server a longer readiness window before the first request.
    yield from _boot_server(env, ready_timeout=60.0)


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
    _guard_seeded_roots(projects_root, outputs_root, jobs_meta_root, e2e_data_root)

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


def _write_failed_project_json(projects_root: Path, project_id: str, *, output_dir: str) -> None:
    """Write a minimal project.json for a FAILED job (zero pages + error text)."""
    proj_dir = projects_root / project_id
    proj_dir.mkdir(parents=True, exist_ok=True)

    spec: dict[str, object] = {
        "project_id": project_id,
        "name": f"e2e-failed-{project_id[:8]}",
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
        "state": "failed",
        "page_count": 0,
        "pages_done": 0,
        "pages": [],
        "error": (
            "No supported image files found in source; supported types are PNG, JPEG, TIFF, JPEG 2000, WebP."
        ),
    }
    data = {"spec": spec, "status": status}
    (proj_dir / "project.json").write_text(json.dumps(data, indent=2), encoding="utf-8")


@pytest.fixture(scope="session")
def seeded_failed_job_id(e2e_data_root: Path) -> str:
    """Yield a project_id for a FAILED job pre-seeded on disk.

    The job has:
    - status = failed, 0 pages, error = "No supported image files found…"
    - output_mode = next_to_source

    Used for B-RESULTS-004 (a failed job must surface its error text AND offer
    a rerun affordance, not render a bare red pip). The fixture has NO source
    image, so a rerun re-fails (which is fine — the test asserts the error +
    rerun control render, not a successful rerun).
    """
    project_id = "e2efailed-" + uuid.uuid4().hex[:12]
    projects_root = e2e_data_root / "projects"
    outputs_root = e2e_data_root / "outputs"
    jobs_meta_root = e2e_data_root / "jobs_meta"
    _guard_seeded_roots(projects_root, outputs_root, jobs_meta_root, e2e_data_root)

    out_dir = str(outputs_root / project_id)
    _write_failed_project_json(projects_root, project_id, output_dir=out_dir)
    _write_job_meta(jobs_meta_root, project_id, mode="next_to_source")
    return project_id


@pytest.fixture(scope="session")
def seeded_flow_rerun_job_id(e2e_data_root: Path) -> str:
    """Yield a project_id for a succeeded job with a real source image.

    Dedicated fixture for F-RERUN-01 flow test, isolated from
    seeded_rerun_job_id so that the flow test's save+rerun writes do not
    contaminate the per-unit rerun tests (both sets run in parallel under
    xdist and share session-scoped fixtures by project_id; sharing the same
    fixture caused flakiness when both tests write to page-001.json).
    """
    project_id = "e2eflowrerun-" + uuid.uuid4().hex[:12]
    projects_root = e2e_data_root / "projects"
    outputs_root = e2e_data_root / "outputs"
    jobs_meta_root = e2e_data_root / "jobs_meta"
    _guard_seeded_roots(projects_root, outputs_root, jobs_meta_root, e2e_data_root)

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
def seeded_page_rerun_job_id(e2e_data_root: Path) -> str:
    """Yield a project_id for a succeeded job with a real source image.

    Dedicated fixture for test_rerun_doctr_toasts_and_preserves_saved_edit
    (B-PAGEVIEW-013), isolated from seeded_rerun_job_id (used by the full-job
    rerun test in test_click_paths_downloads.py).  When those two tests share
    the same project, the full-job rerun can overwrite the sidecar before the
    per-page rerun test finishes reading it, causing intermittent failures
    under xdist parallel execution.
    """
    project_id = "e2epgrerun-" + uuid.uuid4().hex[:12]
    projects_root = e2e_data_root / "projects"
    outputs_root = e2e_data_root / "outputs"
    jobs_meta_root = e2e_data_root / "jobs_meta"
    _guard_seeded_roots(projects_root, outputs_root, jobs_meta_root, e2e_data_root)

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
    _guard_seeded_roots(projects_root, outputs_root, jobs_meta_root, e2e_data_root)

    out_dir = str(outputs_root / project_id)
    _write_project_json(projects_root, project_id, output_dir=out_dir)
    _write_page_sidecar(projects_root, project_id)
    _write_output_txt(outputs_root, project_id)
    _write_job_meta(jobs_meta_root, project_id, mode="managed")
    return project_id
