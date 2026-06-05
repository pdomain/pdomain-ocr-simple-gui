"""Regression tests: /api/suite/device and /api/suite/update are mounted
and not shadowed by the SPA catch-all.

Routes arrive via the existing mount_routes() call in app.py.
Test pattern mirrors test_routes_root.py (monkeypatch + TestClient).
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """TestClient wired to the singleton app instance."""
    from pdomain_ocr_simple_gui.app import app

    return TestClient(app, raise_server_exceptions=False)


def test_device_route_mounted(client):
    resp = client.get("/api/suite/device")
    assert resp.status_code == 200


def test_update_route_mounted(client):
    resp = client.get("/api/suite/update")
    assert resp.status_code == 200


def test_routes_not_shadowed_by_spa_catchall(client):
    resp = client.get("/api/suite/device")
    assert resp.headers["content-type"].startswith("application/json")
