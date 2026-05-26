"""Tests for GET /api/jobs/{id}/download — streams a results zip."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pd_ocr_simple_gui.app import create_app


def test_download_streams_zip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Happy path: job output dir exists → 200 with a valid zip."""
    out = tmp_path / "outputs" / "job-1"
    out.mkdir(parents=True)
    (out / "page-001.txt").write_text("hello world")
    monkeypatch.setenv("PD_OCR_SIMPLE_GUI_OUTPUT_ROOT", str(tmp_path / "outputs"))
    client = TestClient(create_app())
    resp = client.get("/api/jobs/job-1/download")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    assert "page-001.txt" in zf.namelist()


def test_download_missing_job(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """404 when the job output directory does not exist."""
    monkeypatch.setenv("PD_OCR_SIMPLE_GUI_OUTPUT_ROOT", str(tmp_path))
    client = TestClient(create_app())
    resp = client.get("/api/jobs/missing/download")
    assert resp.status_code == 404
