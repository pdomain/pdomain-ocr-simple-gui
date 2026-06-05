"""Test: /manifest.webmanifest is served by the SPA static files."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client_with_manifest(tmp_path, monkeypatch):
    """TestClient with a fake frontend build that includes manifest.webmanifest."""
    import json

    import pdomain_ocr_simple_gui.app as app_module

    frontend_dir = tmp_path / "frontend"
    (frontend_dir / "assets").mkdir(parents=True)
    (frontend_dir / "index.html").write_text(
        '<!DOCTYPE html><html><head><link rel="manifest" href="/manifest.webmanifest" /></head><body>SPA</body></html>'
    )
    manifest = {
        "name": "OCR Simple GUI",
        "short_name": "OCR Simple",
        "start_url": "/",
        "display": "standalone",
    }
    (frontend_dir / "manifest.webmanifest").write_text(json.dumps(manifest))

    monkeypatch.setattr(app_module, "_FRONTEND_DIR", frontend_dir)

    from pdomain_ocr_simple_gui.app import app

    return TestClient(app)


def test_manifest_served(client_with_manifest):
    r = client_with_manifest.get("/manifest.webmanifest")
    assert r.status_code == 200
    assert r.json()["name"]  # has a name


def test_manifest_content_type(client_with_manifest):
    r = client_with_manifest.get("/manifest.webmanifest")
    assert r.status_code == 200
    assert "json" in r.headers.get("content-type", "")


def test_manifest_has_required_fields(client_with_manifest):
    r = client_with_manifest.get("/manifest.webmanifest")
    data = r.json()
    assert data["name"]
    assert data["start_url"] == "/"
    assert data["display"] == "standalone"
