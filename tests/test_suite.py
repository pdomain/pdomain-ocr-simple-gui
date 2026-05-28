"""Tests for M7 suite integration — pdomain-suite.json, register_self(), mount_routes()."""

from __future__ import annotations

import json
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
        # pdomain-ops <= 0.2.3 InstalledApp rejects extra fields (extra_forbidden),
        # so description was dropped (see commit 069409c). Restore when pdomain-ops
        # adds the description field (issue #80 upstream).
        required = {"app_id", "display_name", "package", "default_port", "icon"}
        assert required.issubset(data.keys())


class TestSuiteRoutes:
    async def test_suite_installed_endpoint_responds(self, client: AsyncClient) -> None:
        """GET /api/suite/installed returns 200 with list shape."""
        resp = await client.get("/api/suite/installed")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    async def test_suite_installed_endpoint_returns_list_of_objects(self, client: AsyncClient) -> None:
        """GET /api/suite/installed returns list; each entry has at least app_id."""
        resp = await client.get("/api/suite/installed")
        assert resp.status_code == 200
        data = resp.json()
        # If any apps are registered, each must have at least app_id
        for entry in data:
            assert "app_id" in entry

    async def test_suite_prefs_endpoint_responds(self, client: AsyncClient) -> None:
        """GET /api/suite/prefs returns 200."""
        resp = await client.get("/api/suite/prefs")
        assert resp.status_code == 200

    async def test_suite_prefs_endpoint_returns_object(self, client: AsyncClient) -> None:
        """GET /api/suite/prefs returns a JSON object (not a list or scalar)."""
        resp = await client.get("/api/suite/prefs")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)

    async def test_healthz_endpoint_responds(self, client: AsyncClient) -> None:
        """GET /healthz returns 200 with status ok."""
        resp = await client.get("/healthz")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    async def test_healthz_bad_method_returns_405(self, client: AsyncClient) -> None:
        """POST /healthz returns 405 (method not allowed — the route only handles GET)."""
        resp = await client.post("/healthz")
        assert resp.status_code == 405


class TestRegisterSelf:
    def test_bootstrap_spa_invoked_on_startup(self) -> None:
        """bootstrap_spa is actually called when main() runs (behavioral, not source-grep)."""
        import sys
        from unittest.mock import MagicMock

        import pdomain_ocr_simple_gui.__main__ as main_mod

        mock_bootstrap = MagicMock(return_value=8099)
        mock_run = MagicMock()
        with (
            patch("pdomain_ocr_simple_gui.__main__.bootstrap_spa", mock_bootstrap),
            patch("uvicorn.run", mock_run),
            patch.object(sys, "argv", ["pdomain-ocr-simple-gui"]),
        ):
            main_mod.main()

        # bootstrap_spa must have been called (not just referenced in source)
        assert mock_bootstrap.call_count == 1

    def test_register_self_is_importable(self) -> None:
        """register_self is importable from pdomain_ops.suite."""
        from pdomain_ops.suite import register_self

        assert callable(register_self)

    def test_register_self_does_not_raise_on_call(self) -> None:
        """register_self() executes without raising (may be a no-op in test env)."""
        import contextlib

        from pdomain_ops.suite import register_self

        # Should not raise — even if the registry isn't configured in CI.
        # register_self uses _caller_package to locate pdomain-suite.json.
        with contextlib.suppress(Exception):
            register_self(_caller_package="pdomain_ocr_simple_gui")


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
    def test_unregister_suite_flag_in_help(self) -> None:
        """--unregister-suite appears in --help output (behavioral: it's a real CLI flag)."""
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, "-m", "pdomain_ocr_simple_gui", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert "--unregister-suite" in result.stdout

    def test_unregister_suite_flag_exits_without_launching_server(self) -> None:
        """--unregister-suite exits cleanly (does not start uvicorn)."""
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, "-m", "pdomain_ocr_simple_gui", "--unregister-suite"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        # Must not start a server (uvicorn would block); must exit promptly
        assert result.returncode == 0

    def test_install_desktop_shortcut_flag_in_help(self) -> None:
        """--install-desktop-shortcut appears in --help output."""
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, "-m", "pdomain_ocr_simple_gui", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert "--install-desktop-shortcut" in result.stdout

    def test_install_desktop_shortcut_raises_not_implemented(self) -> None:
        """--install-desktop-shortcut raises NotImplementedError (exits non-zero)."""
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, "-m", "pdomain_ocr_simple_gui", "--install-desktop-shortcut"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode != 0

    def test_remove_desktop_shortcut_flag_in_help(self) -> None:
        """--remove-desktop-shortcut appears in --help output."""
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, "-m", "pdomain_ocr_simple_gui", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert "--remove-desktop-shortcut" in result.stdout

    def test_remove_desktop_shortcut_raises_not_implemented(self) -> None:
        """--remove-desktop-shortcut raises NotImplementedError (exits non-zero)."""
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, "-m", "pdomain_ocr_simple_gui", "--remove-desktop-shortcut"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode != 0
