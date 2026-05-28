"""Tests for /api/prefs routes."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from pdomain_ocr_simple_gui.app import app


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
        from pdomain_ops.suite.types import UIPrefs

        import pdomain_ocr_simple_gui.app as app_mod

        stored = {
            "default_engine": "tesseract",
            "default_language": "fr",
            "default_output_dir": "/home/user/ocr",
            "save_json_default": True,
            "combined_txt_default": False,
            "recent_projects": [{"project_id": "x", "name": "Old Project"}],
        }
        mock = MagicMock()
        ui_prefs = UIPrefs()
        ui_prefs.apps["pdomain-ocr-simple-gui"] = stored
        mock.read.return_value = ui_prefs
        mock.write_app.return_value = None
        monkeypatch.setattr(app_mod, "_prefs_adapter", mock)
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
        from pdomain_ops.suite.types import UIPrefs

        import pdomain_ocr_simple_gui.app as app_mod

        mock = MagicMock()
        mock.read.return_value = UIPrefs()
        mock.write_app.return_value = None
        monkeypatch.setattr(app_mod, "_prefs_adapter", mock)
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
        mock.write_app.assert_called_once()
        call_args = mock.write_app.call_args
        assert call_args[0][0] == "pdomain-ocr-simple-gui"

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
        """PUT /api/prefs accepts {ui_prefs: {theme, density, font_scale}} and returns 200."""
        payload = {"ui_prefs": {"theme": "light", "density": "compact", "font_scale": 1.15}}
        resp = await client_with_mock_prefs.put("/api/prefs", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ui_prefs"]["theme"] == "light"
        assert data["ui_prefs"]["density"] == "compact"
        assert data["ui_prefs"]["font_scale"] == 1.15

    async def test_put_ui_prefs_persists_via_adapter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """PUT /api/prefs with ui_prefs calls write_app on the adapter."""
        from pdomain_ops.suite.types import UIPrefs

        import pdomain_ocr_simple_gui.app as app_mod

        mock = MagicMock()
        mock.read.return_value = UIPrefs()
        mock.write_app.return_value = None
        monkeypatch.setattr(app_mod, "_prefs_adapter", mock)
        payload = {"ui_prefs": {"theme": "dark", "density": "normal", "font_scale": 1.0}}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.put("/api/prefs", json=payload)
        assert resp.status_code == 200
        mock.write_app.assert_called_once()
        call_args = mock.write_app.call_args
        assert call_args[0][0] == "pdomain-ocr-simple-gui"
