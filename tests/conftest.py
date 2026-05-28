"""Shared pytest fixtures for pdomain-ocr-simple-gui backend tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from pdomain_ocr_simple_gui.app import app
from pdomain_ocr_simple_gui.testing.fake_dispatcher import FakeStageDispatcher

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
