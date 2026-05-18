"""Tests for /api/prefs routes."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from pd_ocr_simple_gui.app import app


def _make_mock_adapter(app_data: dict[str, Any] | None = None) -> MagicMock:
    """Build a mock PrefsAdapter that returns app_data for pd-ocr-simple-gui."""
    from pd_ocr_ops.suite.types import UIPrefs

    mock = MagicMock()
    ui_prefs = UIPrefs()
    if app_data:
        ui_prefs.apps["pd-ocr-simple-gui"] = app_data
    mock.read.return_value = ui_prefs
    mock.write_app.return_value = None
    return mock


@pytest.fixture
async def client_with_mock_prefs(monkeypatch: pytest.MonkeyPatch) -> AsyncClient:
    """Async HTTP client with a mocked prefs adapter."""
    import pd_ocr_simple_gui.app as app_mod

    mock_adapter = _make_mock_adapter()
    monkeypatch.setattr(app_mod, "_prefs_adapter", mock_adapter)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac  # type: ignore[misc]


@pytest.fixture
async def client_no_prefs(monkeypatch: pytest.MonkeyPatch) -> AsyncClient:
    """Async HTTP client with prefs adapter set to None."""
    import pd_ocr_simple_gui.app as app_mod

    monkeypatch.setattr(app_mod, "_prefs_adapter", None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac  # type: ignore[misc]


class TestGetPrefs:
    async def test_returns_default_prefs(self, client_with_mock_prefs: AsyncClient) -> None:
        resp = await client_with_mock_prefs.get("/api/prefs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["default_engine"] == "doctr"
        assert data["default_language"] == "en"
        assert data["save_json_default"] is False
        assert data["combined_txt_default"] is True
        assert data["recent_projects"] == []

    async def test_returns_stored_prefs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import pd_ocr_simple_gui.app as app_mod

        stored = {
            "default_engine": "tesseract",
            "default_language": "fr",
            "default_output_dir": "/home/user/ocr",
            "save_json_default": True,
            "combined_txt_default": False,
            "recent_projects": [{"project_id": "x", "name": "Old Project"}],
        }
        mock_adapter = _make_mock_adapter(stored)
        monkeypatch.setattr(app_mod, "_prefs_adapter", mock_adapter)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/api/prefs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["default_engine"] == "tesseract"
        assert data["default_language"] == "fr"
        assert data["recent_projects"] == [{"project_id": "x", "name": "Old Project"}]

    async def test_returns_defaults_when_no_adapter(self, client_no_prefs: AsyncClient) -> None:
        resp = await client_no_prefs.get("/api/prefs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["default_engine"] == "doctr"


class TestPutPrefs:
    async def test_saves_prefs(self, client_with_mock_prefs: AsyncClient) -> None:
        payload = {
            "default_engine": "tesseract",
            "default_language": "de",
            "default_output_dir": "/tmp/out",
            "save_json_default": True,
            "combined_txt_default": False,
            "recent_projects": [],
        }
        resp = await client_with_mock_prefs.put("/api/prefs", json=payload)
        assert resp.status_code == 200

    async def test_write_app_called_with_app_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import pd_ocr_simple_gui.app as app_mod

        mock_adapter = _make_mock_adapter()
        monkeypatch.setattr(app_mod, "_prefs_adapter", mock_adapter)
        payload = {
            "default_engine": "doctr",
            "default_language": "en",
            "default_output_dir": "",
            "save_json_default": False,
            "combined_txt_default": True,
            "recent_projects": [],
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            await ac.put("/api/prefs", json=payload)
        mock_adapter.write_app.assert_called_once()
        call_args = mock_adapter.write_app.call_args
        assert call_args[0][0] == "pd-ocr-simple-gui"

    async def test_put_no_adapter_returns_200(self, client_no_prefs: AsyncClient) -> None:
        """PUT /api/prefs with no adapter should still return 200 (best-effort)."""
        payload = {
            "default_engine": "doctr",
            "default_language": "en",
            "default_output_dir": "",
            "save_json_default": False,
            "combined_txt_default": True,
            "recent_projects": [],
        }
        resp = await client_no_prefs.put("/api/prefs", json=payload)
        assert resp.status_code == 200

    async def test_put_ui_prefs_subset(self, client_with_mock_prefs: AsyncClient) -> None:
        """PUT /api/prefs accepts {ui_prefs: {theme, density, fontScale}} and returns 200."""
        payload = {"ui_prefs": {"theme": "light", "density": "compact", "fontScale": 1.15}}
        resp = await client_with_mock_prefs.put("/api/prefs", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ui_prefs"]["theme"] == "light"
        assert data["ui_prefs"]["density"] == "compact"
        assert data["ui_prefs"]["fontScale"] == 1.15

    async def test_put_ui_prefs_persists_via_adapter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """PUT /api/prefs with ui_prefs calls write_app on the adapter."""
        import pd_ocr_simple_gui.app as app_mod

        mock_adapter = _make_mock_adapter()
        monkeypatch.setattr(app_mod, "_prefs_adapter", mock_adapter)
        payload = {"ui_prefs": {"theme": "dark", "density": "normal", "fontScale": 1.0}}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.put("/api/prefs", json=payload)
        assert resp.status_code == 200
        mock_adapter.write_app.assert_called_once()
        call_args = mock_adapter.write_app.call_args
        assert call_args[0][0] == "pd-ocr-simple-gui"
