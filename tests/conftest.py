"""Shared pytest fixtures for pdomain-ocr-simple-gui backend tests."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from pdomain_ocr_simple_gui.app import app
from pdomain_ocr_simple_gui.testing.fake_dispatcher import FakeStageDispatcher

# ---------------------------------------------------------------------------
# Session-wide isolation guard
#
# Ensures that NO test in ANY module can accidentally write to the real
# home-dir storage roots.  If a test or the smoke-test subprocess forgets to
# set its own roots, these session-scoped defaults kick in and redirect ALL
# data roots (projects / output / jobs-meta / uploads / suite data) to a
# per-session tmpdir.  Then a hard guard FAILS the whole session if any
# resolved data root still points outside the pytest tmp tree.
#
# Critically, the defaulting step does NOT override a value already set in the
# environment — so the e2e conftest (which passes its own session-scoped tmp
# roots into the server subprocess) and the smoke test (which does the same)
# both keep their explicit roots.  Any root that IS set in this process's
# os.environ must still resolve under tmp or the guard aborts the session.
# ---------------------------------------------------------------------------

# Every env var the app / suite reads to locate on-disk data.
_DATA_ROOT_VARS: dict[str, str] = {
    "PD_OCR_SIMPLE_GUI_PROJECTS_ROOT": "projects",
    "PD_OCR_SIMPLE_GUI_OUTPUT_ROOT": "outputs",
    "PD_OCR_SIMPLE_GUI_JOBS_META_ROOT": "jobs_meta",
    "PD_OCR_SIMPLE_GUI_UPLOAD_ROOT": "uploads",
    "PD_SUITE_DATA_DIR": "suite_data",
}


def _is_under_tmp_tree(path: Path, *tmp_roots: Path) -> bool:
    """Return True if *path* lives under the OS tmp dir or any pytest tmp root."""
    import tempfile

    resolved = path.resolve()
    candidates = [Path(tempfile.gettempdir()).resolve(), *(r.resolve() for r in tmp_roots)]
    for base in candidates:
        if resolved == base or base in resolved.parents:
            return True
    # Fall back to a path-segment check (covers tmp dirs the platform reports
    # differently than tempfile.gettempdir(), e.g. /tmp vs /private/tmp).
    return resolved.parts[:2] == ("/", "tmp") or "pytest" in str(resolved)


def _assert_roots_under_tmp(env: dict[str, str], *tmp_roots: Path) -> None:
    """Fail-closed guard: raise if any data root in *env* escapes the tmp tree.

    Inspects every var named in ``_DATA_ROOT_VARS``.  A var that is unset or
    empty is ignored (the defaulting step in the fixture handles unset vars).
    Any var whose value resolves OUTSIDE the pytest tmp tree — i.e. at the real
    home-dir storage — makes this raise ``RuntimeError`` so the session fails
    fast and no test can write to real on-disk data.

    Factored out of ``_isolate_storage_roots`` so the raise path is directly
    testable; the fixture calls this helper, so its behavior is unchanged.
    """
    leaked: list[str] = []
    for var in _DATA_ROOT_VARS:
        raw = env.get(var, "")
        if not raw:
            continue
        if not _is_under_tmp_tree(Path(raw), *tmp_roots):
            leaked.append(f"{var}={raw!r}")
    if leaked:
        raise RuntimeError(
            "Storage-isolation guard: data root(s) resolve OUTSIDE the pytest tmp "
            "tree — tests would write to real home-dir storage. Offending vars: " + "; ".join(leaked)
        )


@pytest.fixture(autouse=True, scope="session")
def _isolate_storage_roots(tmp_path_factory: pytest.TempPathFactory) -> None:
    """Default all data roots to a session tmp dir, then HARD-GUARD against leaks.

    Step 1 (default): any data-root env var that is unset is pointed at a
    per-session tmpdir.  Already-set vars are left untouched so explicit
    per-session overrides (e2e conftest, smoke test) win.

    Step 2 (guard): every resolved data root is verified to live under the
    pytest tmp tree.  If any root points outside tmp — i.e. at the real
    home-dir storage — the fixture raises and the whole session fails fast.
    No test, anywhere, may resolve a data root to the real home dir.
    """
    session_root: Path = tmp_path_factory.mktemp("session_storage_isolation")
    base_temp: Path = tmp_path_factory.getbasetemp()

    for var, subdir in _DATA_ROOT_VARS.items():
        if var not in os.environ:
            p = session_root / subdir
            p.mkdir(parents=True, exist_ok=True)
            os.environ[var] = str(p)

    _assert_roots_under_tmp(dict(os.environ), session_root, base_temp)


# ---------------------------------------------------------------------------
# Storage root
# ---------------------------------------------------------------------------


@pytest.fixture
def projects_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect storage root to tmp_path via the env var _projects_root() reads."""
    root = tmp_path / "projects"
    root.mkdir()
    monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(root))
    return root


# ---------------------------------------------------------------------------
# Bare async HTTP client
# ---------------------------------------------------------------------------


@pytest.fixture
async def async_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AsyncClient:
    """Async HTTP client wired to the FastAPI app with tmp storage root."""
    root = tmp_path / "projects"
    root.mkdir()
    monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(root))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Client with a real source directory containing one image
# ---------------------------------------------------------------------------


@pytest.fixture
async def client_with_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[AsyncClient, str]:
    """Client with a tmp storage root AND a real source directory with one image."""
    root = tmp_path / "projects"
    root.mkdir()
    monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(root))

    src = tmp_path / "source"
    src.mkdir()
    (src / "page0.png").touch()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac, str(src)  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Project with a real (tiny) image on disk
# ---------------------------------------------------------------------------


@pytest.fixture
def project_with_image(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[str, Path]:
    """Create a project with one page and a real (tiny) image file."""
    from datetime import UTC, datetime
    from io import BytesIO

    from PIL import Image

    from pdomain_ocr_simple_gui.models import PageResult, ProjectSpec, ProjectStatus
    from pdomain_ocr_simple_gui.storage import write_page_sidecar, write_project

    root = tmp_path / "projects"
    root.mkdir(exist_ok=True)
    monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(root))

    buf = BytesIO()
    Image.new("RGB", (4, 4), color="white").save(buf, format="PNG")
    png_bytes = buf.getvalue()
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    img_path = source_dir / "page_001.png"
    img_path.write_bytes(png_bytes)

    project_id = "pages-test-001"
    spec = ProjectSpec(
        project_id=project_id,
        name="Pages Test",
        source_path=str(source_dir),
        output_dir=str(tmp_path / "output"),
        engine="doctr",
        language="en",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        last_opened_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    status = ProjectStatus(
        project_id=project_id,
        state="succeeded",
        page_count=1,
        pages_done=1,
        pages=[PageResult(page_idx=0, page_name="page_001.png", state="succeeded", text_preview="Hello")],
    )
    write_project(spec, status)
    write_page_sidecar(spec, 0, {"page_idx": 0, "text": "Hello world", "edited_text": None})
    return project_id, img_path


# ---------------------------------------------------------------------------
# Security: client with an isolated project store + sentinel above root
# ---------------------------------------------------------------------------


@pytest.fixture
async def secured_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[AsyncClient, Path, Path]:
    """Client with an isolated tmp project store + a sentinel above the root.

    Layout:
        tmp_path/
            sentinel.txt          <- must NEVER be deleted by the API
            projects/             <- _PROJECTS_ROOT (monkeypatched)
                legit-project/    <- pre-seeded so GET/DELETE can reach storage
                    project.json
    """
    root = tmp_path / "projects"
    root.mkdir()
    monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(root))

    sentinel = tmp_path / "sentinel.txt"
    sentinel.write_text("do not delete")

    legit_id = "legit-project-abc123"
    legit_dir = root / legit_id
    legit_dir.mkdir()
    project_data = {
        "spec": {
            "project_id": legit_id,
            "name": "Legit",
            "source_path": "/tmp/src",
            "output_dir": "/tmp/out",
            "engine": "doctr",
            "language": "en",
            "save_json": False,
            "combined_txt": True,
            "created_at": "2026-01-01T00:00:00+00:00",
            "last_opened_at": "2026-01-01T00:00:00+00:00",
        },
        "status": {
            "project_id": legit_id,
            "state": "succeeded",
            "page_count": 0,
            "pages_done": 0,
            "pages": [],
        },
    }
    (legit_dir / "project.json").write_text(json.dumps(project_data))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac, root, sentinel  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Prefs fixtures
# ---------------------------------------------------------------------------


def _make_mock_adapter(app_data: dict[str, Any] | None = None) -> MagicMock:
    """Build a mock PrefsAdapter that returns app_data for pdomain-ocr-simple-gui."""
    from pdomain_ops.suite.types import UIPrefs

    mock = MagicMock()
    ui_prefs = UIPrefs()
    if app_data:
        ui_prefs.apps["pdomain-ocr-simple-gui"] = app_data
    mock.read.return_value = ui_prefs
    mock.write_app.return_value = None
    return mock


@pytest.fixture
async def client_with_mock_prefs(monkeypatch: pytest.MonkeyPatch) -> AsyncClient:
    """Async HTTP client with a mocked prefs adapter."""
    import pdomain_ocr_simple_gui.app as app_mod

    mock_adapter = _make_mock_adapter()
    monkeypatch.setattr(app_mod, "_prefs_adapter", mock_adapter)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac  # type: ignore[misc]


@pytest.fixture
async def client_no_prefs(monkeypatch: pytest.MonkeyPatch) -> AsyncClient:
    """Async HTTP client with prefs adapter set to None."""
    import pdomain_ocr_simple_gui.app as app_mod

    monkeypatch.setattr(app_mod, "_prefs_adapter", None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Fake OCR dispatcher seam
# ---------------------------------------------------------------------------


@pytest.fixture
def use_fake_dispatcher(monkeypatch: pytest.MonkeyPatch) -> FakeStageDispatcher:
    """Replace the module-level OCR dispatcher with a deterministic fake.

    Patches ``pdomain_ocr_simple_gui.app._dispatcher`` so that any call to
    ``get_dispatcher()`` — including from ``_pipeline_run_job`` — returns the
    fake instead of a real ``LocalStageDispatcher``.  No model weights are
    loaded; the pipeline completes synchronously and deterministically.

    Returns the ``FakeStageDispatcher`` instance so tests can inspect or
    reconfigure it (e.g. change ``._text`` before the POST).

    Example::

        async def test_my_job(tmp_path, monkeypatch, use_fake_dispatcher):
            ...  # POST /api/jobs → pipeline uses fake OCR
    """
    import pdomain_ocr_simple_gui.app as app_mod

    fake = FakeStageDispatcher()
    monkeypatch.setattr(app_mod, "_dispatcher", fake)
    return fake
