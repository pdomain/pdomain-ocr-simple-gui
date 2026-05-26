# tests/test_config_route.py
from fastapi.testclient import TestClient

from pd_ocr_simple_gui.app import create_app


def test_config_route_local_not_containerized(monkeypatch) -> None:
    monkeypatch.setenv("PD_OCR_SIMPLE_GUI_MODE", "local")
    monkeypatch.setattr(
        "pd_ocr_simple_gui.routes.config.detect_containerized",
        lambda: False,
    )
    client = TestClient(create_app())
    resp = client.get("/api/config")
    assert resp.status_code == 200
    assert resp.json() == {"mode": "local", "is_containerized": False}


def test_config_route_managed_containerized(monkeypatch) -> None:
    monkeypatch.setenv("PD_OCR_SIMPLE_GUI_MODE", "managed")
    monkeypatch.setattr(
        "pd_ocr_simple_gui.routes.config.detect_containerized",
        lambda: True,
    )
    client = TestClient(create_app())
    resp = client.get("/api/config")
    assert resp.status_code == 200
    assert resp.json() == {"mode": "managed", "is_containerized": True}
