# tests/test_uploads.py
import io
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from pd_ocr_simple_gui.app import create_app


def _client(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PD_OCR_SIMPLE_GUI_UPLOAD_ROOT", str(tmp_path))
    return TestClient(create_app())


def test_single_image_upload(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    resp = client.post(
        "/api/uploads",
        files={"files": ("scan.png", b"\x89PNG\r\n", "image/png")},
    )
    assert resp.status_code == 200
    body = resp.json()
    upload_id = body["upload_id"]
    landed = tmp_path / upload_id / "scan.png"
    assert landed.read_bytes() == b"\x89PNG\r\n"


def test_zip_upload_extracts(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("a.png", b"\x89PNG")
    resp = client.post(
        "/api/uploads",
        files={"files": ("scans.zip", buf.getvalue(), "application/zip")},
    )
    upload_id = resp.json()["upload_id"]
    assert (tmp_path / upload_id / "a.png").exists()


def test_size_cap(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PD_OCR_SIMPLE_GUI_UPLOAD_MAX_BYTES", "16")
    client = _client(tmp_path, monkeypatch)
    resp = client.post(
        "/api/uploads",
        files={"files": ("big.png", b"A" * 1024, "image/png")},
    )
    assert resp.status_code == 413
