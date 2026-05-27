"""Tests for GET /api/jobs/{id}/download — streams a results zip."""

from __future__ import annotations

import io
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pdomain_ocr_simple_gui.app import create_app
from pdomain_ocr_simple_gui.models import ProjectSpec, ProjectStatus
from pdomain_ocr_simple_gui.storage import write_project


def _make_job(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    job_id: str = "job-1",
    *,
    txt_files: list[str] | None = None,
    json_files: list[str] | None = None,
    image_files: list[str] | None = None,
) -> Path:
    """Materialize a job: write project.json (storage) + populate output_dir.

    Returns the output_dir path.
    """
    projects_root = tmp_path / "projects"
    output_dir = tmp_path / "outputs" / job_id
    output_dir.mkdir(parents=True)
    monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(projects_root))
    monkeypatch.setenv("PD_OCR_SIMPLE_GUI_OUTPUT_ROOT", str(tmp_path / "outputs"))

    now = datetime.now(UTC)
    spec = ProjectSpec(
        project_id=job_id,
        name="test",
        source_path=str(tmp_path / "src"),
        output_dir=str(output_dir),
        engine="doctr",
        language="en",
        save_json=True,
        combined_txt=True,
        created_at=now,
        last_opened_at=now,
    )
    status = ProjectStatus(
        project_id=job_id,
        state="succeeded",
        page_count=0,
        pages_done=0,
        pages=[],
    )
    write_project(spec, status)

    for name in txt_files or []:
        (output_dir / name).write_text("text content")
    for name in json_files or []:
        (output_dir / name).write_text(json.dumps({"k": "v"}))
    for name in image_files or []:
        (output_dir / name).write_bytes(b"\x89PNG fake")

    return output_dir


def test_download_streams_zip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Happy path: job output dir exists → 200 with a valid zip containing all files."""
    _make_job(
        tmp_path,
        monkeypatch,
        txt_files=["page-001.txt", "combined.txt"],
        json_files=["page-001.json"],
    )
    client = TestClient(create_app())
    resp = client.get("/api/jobs/job-1/download")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    names = set(zf.namelist())
    assert "page-001.txt" in names
    assert "combined.txt" in names
    assert "page-001.json" in names


def test_download_missing_job(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """404 when the job (or its output directory) does not exist."""
    monkeypatch.setenv("PD_OCR_SIMPLE_GUI_PROJECTS_ROOT", str(tmp_path / "projects"))
    monkeypatch.setenv("PD_OCR_SIMPLE_GUI_OUTPUT_ROOT", str(tmp_path / "outputs"))
    client = TestClient(create_app())
    resp = client.get("/api/jobs/missing/download")
    assert resp.status_code == 404


def test_download_include_text_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """?include=text returns only .txt files (plus images, if any)."""
    _make_job(
        tmp_path,
        monkeypatch,
        txt_files=["page-001.txt", "combined.txt"],
        json_files=["page-001.json"],
        image_files=["page-001.png"],
    )
    client = TestClient(create_app())
    resp = client.get("/api/jobs/job-1/download?include=text")
    assert resp.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    names = set(zf.namelist())
    assert "page-001.txt" in names
    assert "combined.txt" in names
    assert "page-001.json" not in names
    # images preserved (current zip already includes them)
    assert "page-001.png" in names


def test_download_include_json_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """?include=json returns only .json files (plus images)."""
    _make_job(
        tmp_path,
        monkeypatch,
        txt_files=["page-001.txt"],
        json_files=["page-001.json"],
        image_files=["page-001.png"],
    )
    client = TestClient(create_app())
    resp = client.get("/api/jobs/job-1/download?include=json")
    assert resp.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    names = set(zf.namelist())
    assert "page-001.json" in names
    assert "page-001.txt" not in names
    assert "page-001.png" in names


def test_download_include_both_explicit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """?include=text,json (and text+json) returns both."""
    _make_job(
        tmp_path,
        monkeypatch,
        txt_files=["page-001.txt"],
        json_files=["page-001.json"],
    )
    client = TestClient(create_app())
    for value in ("text,json", "text+json", "json,text"):
        resp = client.get(f"/api/jobs/job-1/download?include={value}")
        assert resp.status_code == 200, f"include={value} got {resp.status_code}"
        zf = zipfile.ZipFile(io.BytesIO(resp.content))
        names = set(zf.namelist())
        assert "page-001.txt" in names
        assert "page-001.json" in names


def test_download_default_is_both(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No ?include returns text + json (default)."""
    _make_job(
        tmp_path,
        monkeypatch,
        txt_files=["page-001.txt"],
        json_files=["page-001.json"],
    )
    client = TestClient(create_app())
    resp = client.get("/api/jobs/job-1/download")
    assert resp.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    names = set(zf.namelist())
    assert "page-001.txt" in names
    assert "page-001.json" in names


def test_download_invalid_include_value(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """?include=garbage returns 400 with a clear message."""
    _make_job(
        tmp_path,
        monkeypatch,
        txt_files=["page-001.txt"],
    )
    client = TestClient(create_app())
    resp = client.get("/api/jobs/job-1/download?include=garbage")
    assert resp.status_code == 400
    body = resp.json()
    assert "include" in str(body).lower()
