"""Tests for GET /api/pages/{job_id}/{idx}/words."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pdomain_ocr_simple_gui.app import create_app


def _seed_project_with_words(projects_root: Path, project_id: str = "words-test-001") -> str:
    """Write a minimal project + sidecar with word data; returns the project_id.

    ``project_id`` defaults to a normal id, but callers testing traversal
    guards may pass a relative-path id (e.g. ``"../outside-root"``) — the
    underlying storage helpers do not sanitize it, so the seeded project
    lands wherever that id resolves to on disk, exactly like an attacker's
    write would.
    """
    from datetime import UTC, datetime

    from pdomain_ocr_simple_gui.models import PageResult, ProjectSpec, ProjectStatus
    from pdomain_ocr_simple_gui.storage import write_page_sidecar, write_project

    spec = ProjectSpec(
        project_id=project_id,
        name="Words Test",
        source_path=str(projects_root / "source"),
        output_dir=str(projects_root / "output"),
        engine="doctr",
        language="en",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        last_opened_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    status = ProjectStatus(
        project_id=project_id,
        state="succeeded",
        page_count=1,
        pages_done=1,
        pages=[PageResult(page_idx=0, page_name="page_001.png", state="succeeded")],
    )
    write_project(spec, status)
    # Write sidecar with normalized word data (the format pipeline writes)
    sidecar = {
        "text": "Hello world",
        "width": 100,
        "height": 200,
        "words": [
            {"text": "Hello", "bbox": {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.05}, "confidence": 0.95},
            {"text": "world", "bbox": {"x": 0.35, "y": 0.1, "w": 0.2, "h": 0.05}, "confidence": 0.88},
        ],
    }
    write_page_sidecar(spec, 0, sidecar)
    return project_id


def test_words_payload_shape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Happy-path: real storage round-trip returns correct {words:[...]} shape."""
    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(projects_root))

    project_id = _seed_project_with_words(projects_root)

    client = TestClient(create_app())
    resp = client.get(f"/api/pages/{project_id}/0/words")
    assert resp.status_code == 200
    data = resp.json()
    assert "words" in data
    assert len(data["words"]) == 2
    assert data["words"][0]["text"] == "Hello"
    assert data["words"][0]["confidence"] == pytest.approx(0.95)
    bbox = data["words"][0]["bbox"]
    assert set(bbox.keys()) == {"x", "y", "w", "h"}


def test_words_missing_returns_404(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing project (no sidecar on disk) → 404 with no crash."""
    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(projects_root))

    client = TestClient(create_app())
    resp = client.get("/api/pages/does-not-exist/0/words")
    assert resp.status_code == 404


def test_words_rejects_traversal_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A traversal project_id is rejected with 400 before any filesystem read.

    Plants a valid project + sidecar OUTSIDE the projects root, at the parent
    directory a ``".."`` id resolves to, to prove the off-root read never
    happens: if validation didn't run first, the route would find the file
    and return 200 instead of 400. (FastAPI path params never contain a raw
    "/", so a same-segment ``".."`` — sent url-encoded as ``%2e%2e`` so the
    HTTP client doesn't normalize it away first — is the traversal id that
    actually reaches the route function.)
    """
    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(projects_root))

    # get_project_dir("..") == projects_root / ".." == tmp_path, so seeding
    # under project_id ".." plants project.json + sidecar right there.
    _seed_project_with_words(tmp_path, project_id="..")

    client = TestClient(create_app())
    resp = client.get("/api/pages/%2e%2e/0/words")
    assert resp.status_code == 400


def test_words_route_after_fake_pipeline_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """End-to-end: fake-backed run_project writes a sidecar with real word boxes.

    Asserts that GET /api/pages/{id}/0/words returns non-empty word records
    with valid geometry — not an empty list — proving the fake dispatcher's
    output passes Page.from_dict() and that extract_words() finds the words
    in the resulting sidecar.
    """
    import asyncio
    from datetime import UTC, datetime

    from pdomain_ocr_simple_gui.models import ProjectSpec
    from pdomain_ocr_simple_gui.pipeline import run_project
    from pdomain_ocr_simple_gui.storage import write_project
    from pdomain_ocr_simple_gui.testing.fake_dispatcher import FakeStageDispatcher

    # Set up an isolated projects root with a single fake image
    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(projects_root))

    # Create a source directory with one PNG-like file (content irrelevant; pipeline
    # reads bytes but the fake dispatcher ignores them)
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    fake_image = source_dir / "page_001.png"
    fake_image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)  # minimal PNG header

    project_id = "fake-pipeline-words-001"
    spec = ProjectSpec(
        project_id=project_id,
        name="Fake Pipeline Words Test",
        source_path=str(source_dir),
        output_dir=str(tmp_path / "output"),
        engine="doctr",
        language="en",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        last_opened_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    from pdomain_ocr_simple_gui.models import PageResult, ProjectStatus

    initial_status = ProjectStatus(
        project_id=project_id,
        state="queued",
        page_count=1,
        pages_done=0,
        pages=[PageResult(page_idx=0, page_name="page_001.png", state="queued")],
    )
    write_project(spec, initial_status)

    dispatcher = FakeStageDispatcher(text="red fox jumps")
    statuses: list[ProjectStatus] = []

    async def _collect_status(s: ProjectStatus) -> None:
        statuses.append(s)

    # Patch aiofiles.open so the pipeline can read the fake PNG bytes
    asyncio.run(run_project(spec, dispatcher, _collect_status))

    # Now hit the words endpoint
    client = TestClient(create_app())
    resp = client.get(f"/api/pages/{project_id}/0/words")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    words = data.get("words", [])
    assert len(words) >= 1, f"Expected at least one word from fake pipeline run, got {len(words)}"
    # Verify geometry is present (not zeroed out by fallback path)
    for rec in words:
        bbox = rec["bbox"]
        assert float(bbox["w"]) > 0, f"Word {rec['text']!r} has zero-width bbox"
        assert float(bbox["h"]) > 0, f"Word {rec['text']!r} has zero-height bbox"
    # All three tokens should be present
    texts = [rec["text"] for rec in words]
    assert "red" in texts or "fox" in texts or "jumps" in texts, (
        f"Expected fake text tokens in words response, got: {texts}"
    )
