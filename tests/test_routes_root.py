"""Contract tests: GET / and SPA paths serve the frontend index.html."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app_with_frontend(tmp_path, monkeypatch):
    # Create minimal fake frontend build
    frontend_dir = tmp_path / "frontend"
    (frontend_dir / "assets").mkdir(parents=True)
    (frontend_dir / "index.html").write_text("<!DOCTYPE html><html><body>SPA</body></html>")

    # Patch the _FRONTEND_DIR in app module
    import pd_ocr_simple_gui.app as app_module

    monkeypatch.setattr(app_module, "_FRONTEND_DIR", frontend_dir)

    from pd_ocr_simple_gui.app import app

    return TestClient(app)


def test_root_returns_html(app_with_frontend):
    resp = app_with_frontend.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "<!DOCTYPE html>" in resp.text


def test_spa_react_router_paths_return_html(app_with_frontend):
    for path in ["/jobs", "/jobs/some-id", "/jobs/some-id/pages/0"]:
        resp = app_with_frontend.get(path)
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]


def test_api_routes_not_shadowed_by_spa_fallback(app_with_frontend):
    # API routes must still work — not swallowed by catch-all
    resp = app_with_frontend.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_root_503_when_frontend_not_built(tmp_path, monkeypatch):
    # When frontend/index.html doesn't exist → 503, not 404
    import pd_ocr_simple_gui.app as app_module

    monkeypatch.setattr(app_module, "_FRONTEND_DIR", tmp_path / "nonexistent")
    from pd_ocr_simple_gui.app import app

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/")
    assert resp.status_code == 503
