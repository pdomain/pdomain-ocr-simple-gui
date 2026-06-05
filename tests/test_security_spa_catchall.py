"""Security tests: SPA catch-all must not serve files outside the frontend dir.

Path traversal via percent-encoded slashes (%2f / %2F) could allow a
crafted request to escape the frontend root and serve arbitrary files.
These tests assert that such requests never return outside-tree file contents —
they must fall through to index.html (200 text/html) or 404.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client_with_frontend(tmp_path, monkeypatch):
    """TestClient with a fake frontend build containing index.html only."""
    import pdomain_ocr_simple_gui.app as app_module

    frontend_dir = tmp_path / "frontend"
    (frontend_dir / "assets").mkdir(parents=True)
    (frontend_dir / "index.html").write_text("<!DOCTYPE html><html><body>SPA</body></html>")

    monkeypatch.setattr(app_module, "_FRONTEND_DIR", frontend_dir)

    from pdomain_ocr_simple_gui.app import app

    # raise_server_exceptions=False so 503/404 paths don't throw in tests
    return TestClient(app, raise_server_exceptions=False)


def _is_safe_response(resp) -> bool:
    """Return True if the response is a safe SPA fall-through (HTML or 404/503)."""
    if resp.status_code == 200:
        ct = resp.headers.get("content-type", "")
        return "text/html" in ct
    return resp.status_code in (404, 503)


def _leaks_outside_file(resp) -> bool:
    """Return True if the response appears to serve an outside-tree file."""
    if resp.status_code != 200:
        return False
    ct = resp.headers.get("content-type", "")
    # If it returned 200 with non-HTML content the catch-all leaked a real file
    return "text/html" not in ct


def test_percent_encoded_traversal_single_depth(client_with_frontend, tmp_path):
    """GET /..%2fetc%2fpasswd must not return file contents outside frontend dir."""
    # The test validates the response is safe (HTML or error), NOT file contents.
    resp = client_with_frontend.get("/..%2fetc%2fpasswd")
    assert _is_safe_response(resp), (
        f"Expected safe response (HTML or 4xx) for traversal attempt, "
        f"got {resp.status_code} content-type={resp.headers.get('content-type', '')!r}"
    )
    # Extra guard: body must not contain /etc/passwd contents
    assert "root:" not in resp.text, "Response body looks like /etc/passwd contents"


def test_percent_encoded_traversal_double_depth(client_with_frontend, tmp_path):
    """GET /..%2f..%2fetc%2fpasswd must not return file contents outside frontend dir."""
    resp = client_with_frontend.get("/..%2f..%2fetc%2fpasswd")
    assert _is_safe_response(resp), (
        f"Expected safe response for deep traversal attempt, "
        f"got {resp.status_code} content-type={resp.headers.get('content-type', '')!r}"
    )
    assert "root:" not in resp.text


def test_percent_encoded_traversal_to_outside_tmp(client_with_frontend, tmp_path):
    """Traversal to a known file outside the frontend dir must fall through to SPA."""
    # Write a sentinel file one level above the frontend dir
    sentinel = tmp_path / "secret.txt"
    sentinel.write_text("SHOULD_NOT_APPEAR")

    # Build a path that escapes frontend/ by one level then reads secret.txt
    resp = client_with_frontend.get("/..%2fsecret.txt")
    assert _is_safe_response(resp), (
        f"Expected safe response for sentinel file traversal, "
        f"got {resp.status_code} content-type={resp.headers.get('content-type', '')!r}"
    )
    assert "SHOULD_NOT_APPEAR" not in resp.text, (
        "Response body contains sentinel value — catch-all served an outside-tree file"
    )


def test_api_routes_still_not_shadowed(client_with_frontend):
    """/api/* routes are not swallowed by the catch-all after the fix."""
    resp = client_with_frontend.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_manifest_still_served_after_fix(tmp_path, monkeypatch):
    """manifest.webmanifest inside the frontend dir is still served correctly."""
    import json

    import pdomain_ocr_simple_gui.app as app_module

    frontend_dir = tmp_path / "frontend"
    (frontend_dir / "assets").mkdir(parents=True)
    (frontend_dir / "index.html").write_text(
        '<!DOCTYPE html><html><head><link rel="manifest" href="/manifest.webmanifest"/></head><body>SPA</body></html>'
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

    client = TestClient(app)
    resp = client.get("/manifest.webmanifest")
    assert resp.status_code == 200
    assert "json" in resp.headers.get("content-type", "")
