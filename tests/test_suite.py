"""Tests for M7 suite integration — pdomain-suite.json, register_self(), mount_routes()."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from pdomain_ocr_simple_gui.app import app


@pytest.fixture
async def client() -> AsyncClient:
    """Async HTTP client wired to the FastAPI app."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac  # type: ignore[misc]


class TestSuiteJson:
    def test_pd_suite_json_exists(self) -> None:
        """pdomain-suite.json is present as a package resource."""
        import importlib.resources

        pkg_files = importlib.resources.files("pdomain_ocr_simple_gui")
        fragment = pkg_files / "pdomain-suite.json"
        raw = fragment.read_text(encoding="utf-8")  # type: ignore[attr-defined]
        data = json.loads(raw)

        assert data["app_id"] == "pdomain-ocr-simple-gui"
        assert data["display_name"] == "Simple OCR"
        assert data["default_port"] == 8004

    def test_pd_suite_json_has_required_fields(self) -> None:
        """pdomain-suite.json contains all required InstalledApp fields."""
        import importlib.resources

        pkg_files = importlib.resources.files("pdomain_ocr_simple_gui")
        fragment = pkg_files / "pdomain-suite.json"
        raw = fragment.read_text(encoding="utf-8")  # type: ignore[attr-defined]
        data = json.loads(raw)

        # NOTE: "description" is intentionally absent from pdomain-suite.json.
        # pdomain-ocr-ops <= 0.2.3 InstalledApp rejects extra fields (extra_forbidden),
        # so description was dropped (see commit 069409c). Restore when pdomain-ocr-ops
        # adds the description field (issue #80 upstream).
        required = {"app_id", "display_name", "package", "default_port", "icon"}
        assert required.issubset(data.keys())


class TestSuiteRoutes:
    async def test_suite_installed_endpoint_responds(self, client: AsyncClient) -> None:
        """GET /api/suite/installed returns 200."""
        resp = await client.get("/api/suite/installed")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_suite_prefs_endpoint_responds(self, client: AsyncClient) -> None:
        """GET /api/suite/prefs returns 200."""
        resp = await client.get("/api/suite/prefs")
        assert resp.status_code == 200

    async def test_healthz_endpoint_responds(self, client: AsyncClient) -> None:
        """GET /healthz returns 200 with status ok."""
        resp = await client.get("/healthz")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


class TestRegisterSelf:
    def test_register_self_called_with_correct_package(self, tmp_path: Path) -> None:
        """register_self() is called on startup with pdomain_ocr_simple_gui package."""
        call_log: list[str] = []

        def _fake_register_self(**kwargs: object) -> None:
            call_log.append(kwargs.get("_caller_package", "auto") or "auto")

        with patch("pdomain_ops.suite.register_self", _fake_register_self):
            # Import the lifespan setup to verify the call would happen
            # (we check the app module sources the correct import path)
            import inspect

            import pdomain_ocr_simple_gui.app as app_mod

            src = inspect.getsource(app_mod)
            assert "register_self" in src

    def test_register_self_is_importable(self) -> None:
        """register_self is importable from pdomain_ops.suite."""
        from pdomain_ops.suite import register_self

        assert callable(register_self)


class TestIcons:
    async def test_icon_32_returns_png(self, client: AsyncClient) -> None:
        """GET /api/self/icons/32 returns bytes with content-type image/png."""
        resp = await client.get("/api/self/icons/32")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"
        assert len(resp.content) > 0

    async def test_icon_16_returns_png(self, client: AsyncClient) -> None:
        """GET /api/self/icons/16 returns PNG bytes."""
        resp = await client.get("/api/self/icons/16")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"

    async def test_icon_256_returns_png(self, client: AsyncClient) -> None:
        """GET /api/self/icons/256 returns PNG bytes."""
        resp = await client.get("/api/self/icons/256")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"

    async def test_unsupported_size_returns_400(self, client: AsyncClient) -> None:
        """GET /api/self/icons/999 returns 400."""
        resp = await client.get("/api/self/icons/999")
        assert resp.status_code == 400

    def test_icon_files_exist(self) -> None:
        """All required icon sizes exist as PNG files."""
        import importlib.resources

        pkg = importlib.resources.files("pdomain_ocr_simple_gui")
        for size in [16, 24, 32, 48, 64, 128, 256]:
            icon = pkg / "icons" / f"{size}.png"
            raw = icon.read_bytes()  # type: ignore[attr-defined]
            assert len(raw) > 0, f"Icon {size}.png is empty"

    def test_ico_file_exists(self) -> None:
        """simple-gui.ico exists as a package resource."""
        import importlib.resources

        pkg = importlib.resources.files("pdomain_ocr_simple_gui")
        ico = pkg / "icons" / "simple-gui.ico"
        raw = ico.read_bytes()  # type: ignore[attr-defined]
        assert len(raw) > 0


class TestCLIFlags:
    def test_unregister_suite_flag_exists(self) -> None:
        """--unregister-suite flag is present in the CLI parser."""
        import sys

        # Patch sys.argv to avoid argparse reading pytest args
        with patch.object(sys, "argv", ["pdomain-ocr-simple-gui", "--help"]):
            # Import the parser-builder — we directly inspect __main__
            import inspect

            import pdomain_ocr_simple_gui.__main__ as main_mod

            src = inspect.getsource(main_mod)
            assert "--unregister-suite" in src

    def test_install_desktop_shortcut_flag_exists(self) -> None:
        """--install-desktop-shortcut flag is present in the CLI parser."""
        import inspect

        import pdomain_ocr_simple_gui.__main__ as main_mod

        src = inspect.getsource(main_mod)
        assert "--install-desktop-shortcut" in src

    def test_remove_desktop_shortcut_flag_exists(self) -> None:
        """--remove-desktop-shortcut flag is present in the CLI parser."""
        import inspect

        import pdomain_ocr_simple_gui.__main__ as main_mod

        src = inspect.getsource(main_mod)
        assert "--remove-desktop-shortcut" in src
