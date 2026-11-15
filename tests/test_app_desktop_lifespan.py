"""Exercise lifecycle integration through the real application lifespan."""

from __future__ import annotations

from threading import Event

import pytest
from fastapi.testclient import TestClient

from pdomain_ocr_simple_gui.app import create_app
from pdomain_ocr_simple_gui.desktop_runtime import DesktopRuntime
from pdomain_ocr_simple_gui.instance import new_instance_record
from pdomain_ocr_simple_gui.lifecycle import LifecycleController


def test_app_starts_and_stops_desktop_monitor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PDOMAIN_OCR_FAKE_DISPATCHER", "1")
    exit_requested = Event()
    record = new_instance_record("http://127.0.0.1:8004")
    controller = LifecycleController(
        record.instance_id, request_exit=exit_requested.set, initial_grace_seconds=0
    )
    app = create_app()
    app.state.desktop_runtime = DesktopRuntime(record, controller)
    with TestClient(app) as client:
        assert exit_requested.wait(timeout=2)
        assert client.get("/api/health").status_code == 503


def test_headless_bootstrap_has_no_desktop_lease(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PDOMAIN_OCR_FAKE_DISPATCHER", "1")
    with TestClient(create_app()) as client:
        response = client.post("/api/lifecycle/bootstrap")
    assert response.status_code == 200
    assert response.json() == {"managed": False}
