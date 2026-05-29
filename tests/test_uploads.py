# tests/test_uploads.py
import io
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from pdomain_ocr_simple_gui.app import create_app


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


# B-HOME-004 (Regression): clearing a chosen upload must delete its staging
# dir. DELETE /api/uploads/{upload_id} removes <UPLOAD_ROOT>/<upload_id>/ so
# orphan staging dirs do not accumulate on disk.
def test_delete_upload_removes_staging_dir(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    resp = client.post(
        "/api/uploads",
        files={"files": ("scan.png", b"\x89PNG\r\n", "image/png")},
    )
    upload_id = resp.json()["upload_id"]
    staging = tmp_path / upload_id
    assert staging.is_dir(), "staging dir should exist after upload"

    del_resp = client.delete(f"/api/uploads/{upload_id}")
    assert del_resp.status_code == 200
    assert not staging.exists(), "staging dir must be gone after DELETE"


def test_delete_upload_missing_is_204(tmp_path: Path, monkeypatch) -> None:
    """DELETE of an upload_id that was never staged returns 204 (idempotent)."""
    client = _client(tmp_path, monkeypatch)
    resp = client.delete("/api/uploads/deadbeefcafe")
    assert resp.status_code == 204


def test_delete_upload_rejects_unsafe_id(tmp_path: Path, monkeypatch) -> None:
    """An upload_id with disallowed chars (dots) is rejected 400, deletes nothing."""
    client = _client(tmp_path, monkeypatch)
    # A sibling dir we must never touch.
    victim = tmp_path / "keepme"
    victim.mkdir()
    resp = client.delete("/api/uploads/..foo..")
    assert resp.status_code == 400
    assert victim.exists(), "validation must reject before any filesystem op"
