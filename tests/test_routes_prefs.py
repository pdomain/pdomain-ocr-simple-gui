"""Tests for /api/prefs routes."""

from __future__ import annotations

from pathlib import Path
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

    async def test_returns_default_prefs_when_adapter_has_no_app_data(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """GET /api/prefs returns full defaults when the adapter holds no app data.

        Bad state: the adapter is present but the app's namespace inside UIPrefs
        is empty (e.g. first launch after prefs file created by a different app).
        Expected: 200 with all-default field values — not an error, not partial data.
        """
        from pdomain_ops.suite.types import UIPrefs

        import pdomain_ocr_simple_gui.app as app_mod

        mock = MagicMock()
        # UIPrefs with no entry for this app — simulates a fresh/foreign prefs file
        mock.read.return_value = UIPrefs()
        mock.write_app.return_value = None
        monkeypatch.setattr(app_mod, "_prefs_adapter", mock)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/api/prefs")

        assert resp.status_code == 200
        data = resp.json()
        # All fields must be the AppPrefs defaults
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

    async def test_returns_defaults_for_partial_stored_prefs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """GET /api/prefs fills in defaults for missing fields in partial stored prefs.

        Bad state: the adapter returns a prefs dict that only has some fields
        (e.g. a prior version wrote fewer keys). Missing fields must receive
        their defaults — not raise a ValidationError or return null.
        """
        from pdomain_ops.suite.types import UIPrefs

        import pdomain_ocr_simple_gui.app as app_mod

        # Only one field set — all others must fall back to AppPrefs defaults
        partial = {"default_engine": "tesseract"}
        mock = MagicMock()
        ui_prefs = UIPrefs()
        ui_prefs.apps["pdomain-ocr-simple-gui"] = partial
        mock.read.return_value = ui_prefs
        mock.write_app.return_value = None
        monkeypatch.setattr(app_mod, "_prefs_adapter", mock)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/api/prefs")

        assert resp.status_code == 200
        data = resp.json()
        # Stored override honoured
        assert data["default_engine"] == "tesseract"
        # Unset fields default correctly
        assert data["default_language"] == "en"
        assert data["save_json_default"] is False
        assert data["combined_txt_default"] is True
        assert data["recent_projects"] == []

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

    async def test_put_invalid_prefs_returns_422(self, client_with_mock_prefs: AsyncClient) -> None:
        """PUT /api/prefs with an invalid engine value returns 422 Unprocessable Entity.

        Bad state: the client sends a prefs payload with a field that fails
        Pydantic validation (wrong type). The route must reject it with 422,
        not silently store garbage or return 200.
        """
        invalid_payload = {
            "default_engine": 12345,  # must be a str, not an int
            "default_language": "en",
            "save_json_default": False,
            "combined_txt_default": True,
            "recent_projects": "not-a-list",  # must be a list
        }
        resp = await client_with_mock_prefs.put("/api/prefs", json=invalid_payload)
        assert resp.status_code == 422

    async def test_write_app_called_with_app_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """PUT /api/prefs persists the submitted values via the adapter.

        Observable: the response body reflects the PUT payload, confirming the
        route round-tripped the values rather than discarding or replacing them.
        """
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
            resp = await ac.put("/api/prefs", json=payload)

        # Observable: response body echoes the submitted values
        assert resp.status_code == 200
        data = resp.json()
        assert data["default_engine"] == "doctr"
        assert data["default_language"] == "en"
        assert data["save_json_default"] is False

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

    async def test_put_ui_prefs_with_unknown_fields_returns_200(
        self, client_with_mock_prefs: AsyncClient
    ) -> None:
        """PUT /api/prefs with extra unknown fields in ui_prefs returns 200.

        Bad state: client sends extra fields not in the CommonUIPrefs schema.
        Pydantic's default is to ignore unknown fields (extra='ignore'), so
        the route should accept the payload and return the known fields only.
        """
        payload = {
            "ui_prefs": {
                "theme": "dark",
                "density": "normal",
                "font_scale": 1.0,
                "unknown_future_field": "should-be-ignored",
            }
        }
        resp = await client_with_mock_prefs.put("/api/prefs", json=payload)
        # Must accept the payload (not 422)
        assert resp.status_code == 200
        data = resp.json()
        # Known fields present
        assert data["ui_prefs"]["theme"] == "dark"

    async def test_put_ui_prefs_persists_via_adapter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """PUT /api/prefs with ui_prefs echoes the submitted ui_prefs values in response.

        Observable: the response body includes the ui_prefs fields that were
        submitted, confirming the route accepted and round-tripped the payload
        rather than discarding the ui_prefs key.
        """
        from pdomain_ops.suite.types import UIPrefs

        import pdomain_ocr_simple_gui.app as app_mod

        mock = MagicMock()
        mock.read.return_value = UIPrefs()
        mock.write_app.return_value = None
        monkeypatch.setattr(app_mod, "_prefs_adapter", mock)
        payload = {"ui_prefs": {"theme": "dark", "density": "normal", "font_scale": 1.0}}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.put("/api/prefs", json=payload)

        # Observable: response echoes the ui_prefs values
        assert resp.status_code == 200
        data = resp.json()
        assert data["ui_prefs"]["theme"] == "dark"
        assert data["ui_prefs"]["density"] == "normal"
        assert data["ui_prefs"]["font_scale"] == 1.0


def _stateful_adapter() -> MagicMock:
    """A mock PrefsAdapter whose read() reflects prior write_app() calls.

    The shipped MagicMock fixture returns a fixed empty UIPrefs from read(),
    so it can't observe clobbering across a PUT->GET sequence. This stateful
    variant stores what write_app() persists and serves it back from read(),
    matching LocalFilePrefs' real read-after-write behaviour.
    """
    from pdomain_ops.suite.types import UIPrefs

    store: dict[str, dict[str, object]] = {}
    mock = MagicMock()

    def _read() -> UIPrefs:
        ui = UIPrefs()
        for app_id, payload in store.items():
            ui.apps[app_id] = dict(payload)
        return ui

    def _write_app(app_id: str, payload: dict[str, object]) -> None:
        store[app_id] = dict(payload)

    mock.read.side_effect = _read
    mock.write_app.side_effect = _write_app
    return mock


class TestPutPrefsMergeNoClobber:
    """PUT /api/prefs must read-modify-write merge so a partial body never
    wipes previously-saved sibling fields (active data-loss regression)."""

    async def test_partial_app_field_preserves_siblings(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """PUT with only default_engine keeps default_language/recent_projects/etc."""
        import pdomain_ocr_simple_gui.app as app_mod

        adapter = _stateful_adapter()
        monkeypatch.setattr(app_mod, "_prefs_adapter", adapter)

        jobs_dir = str(tmp_path / "seed-jobs")
        seed = {
            "default_engine": "tesseract",
            "default_language": "fr",
            "default_output_dir": "/seed/out",
            "save_json_default": True,
            "combined_txt_default": False,
            "recent_projects": [{"project_id": "p1", "name": "Seed"}],
            "ui_prefs": {"theme": "light", "density": "compact", "font_scale": 1.2},
            "jobs_location": jobs_dir,
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            seed_resp = await ac.put("/api/prefs", json=seed)
            assert seed_resp.status_code == 200

            # Change ONLY default_engine.
            resp = await ac.put("/api/prefs", json={"default_engine": "doctr"})
            assert resp.status_code == 200

            after = (await ac.get("/api/prefs")).json()

        assert after["default_engine"] == "doctr"  # changed field applied
        # Every sibling must survive.
        assert after["default_language"] == "fr"
        assert after["default_output_dir"] == "/seed/out"
        assert after["save_json_default"] is True
        assert after["combined_txt_default"] is False
        assert after["recent_projects"] == [{"project_id": "p1", "name": "Seed"}]
        assert after["ui_prefs"]["theme"] == "light"
        assert after["jobs_location"] == jobs_dir

    async def test_partial_ui_prefs_preserves_app_fields(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """PUT with only ui_prefs (theme/density/fontScale) keeps all app fields."""
        import pdomain_ocr_simple_gui.app as app_mod

        adapter = _stateful_adapter()
        monkeypatch.setattr(app_mod, "_prefs_adapter", adapter)

        jobs_dir = str(tmp_path / "seed-jobs")
        seed = {
            "default_engine": "tesseract",
            "default_language": "de",
            "recent_projects": [{"project_id": "p9", "name": "Keep"}],
            "jobs_location": jobs_dir,
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            assert (await ac.put("/api/prefs", json=seed)).status_code == 200

            # This is exactly what the frontend persistCommon sends.
            resp = await ac.put(
                "/api/prefs",
                json={"ui_prefs": {"theme": "dark", "density": "normal", "font_scale": 1.0}},
            )
            assert resp.status_code == 200

            after = (await ac.get("/api/prefs")).json()

        assert after["ui_prefs"]["theme"] == "dark"
        # App fields must NOT revert to defaults.
        assert after["default_engine"] == "tesseract"
        assert after["default_language"] == "de"
        assert after["recent_projects"] == [{"project_id": "p9", "name": "Keep"}]
        assert after["jobs_location"] == jobs_dir

    async def test_sequence_engine_theme_jobs_all_persist(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """set engine -> set theme -> set jobs_location: all three coexist.

        This is the regression that proves the clobber is gone end to end.
        """
        import pdomain_ocr_simple_gui.app as app_mod

        adapter = _stateful_adapter()
        monkeypatch.setattr(app_mod, "_prefs_adapter", adapter)

        jobs_dir = str(tmp_path)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            assert (await ac.put("/api/prefs", json={"default_engine": "tesseract"})).status_code == 200
            assert (
                await ac.put(
                    "/api/prefs",
                    json={"ui_prefs": {"theme": "dark", "density": "normal", "font_scale": 1.0}},
                )
            ).status_code == 200
            assert (await ac.put("/api/prefs", json={"jobs_location": jobs_dir})).status_code == 200

            after = (await ac.get("/api/prefs")).json()

        assert after["default_engine"] == "tesseract"
        assert after["ui_prefs"]["theme"] == "dark"
        assert after["jobs_location"] == jobs_dir

    async def test_empty_body_does_not_reset_fields(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """PUT {} must not wipe stored prefs back to defaults."""
        import pdomain_ocr_simple_gui.app as app_mod

        adapter = _stateful_adapter()
        monkeypatch.setattr(app_mod, "_prefs_adapter", adapter)

        seed = {"default_engine": "tesseract", "default_language": "fr"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            assert (await ac.put("/api/prefs", json=seed)).status_code == 200
            resp = await ac.put("/api/prefs", json={})
            assert resp.status_code == 200
            after = (await ac.get("/api/prefs")).json()

        assert after["default_engine"] == "tesseract"
        assert after["default_language"] == "fr"
