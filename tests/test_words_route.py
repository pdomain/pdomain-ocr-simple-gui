"""Tests for GET /api/pages/{job_id}/{idx}/words."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pdomain_ocr_simple_gui.app import create_app


def _seed_project_with_words(projects_root: Path) -> str:
    """Write a minimal project + sidecar with word data; returns the project_id."""
    from datetime import UTC, datetime

    from pdomain_ocr_simple_gui.models import PageResult, ProjectSpec, ProjectStatus
    from pdomain_ocr_simple_gui.storage import write_page_sidecar, write_project

    project_id = "words-test-001"
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
