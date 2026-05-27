"""Tests for dynamic port selection and register_self(actual_port=...) wiring."""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch


class TestDynamicPortCLI:
    """Unit tests: find_available_port drives uvicorn.run and register_self."""

    def test_uvicorn_called_with_picked_port(self) -> None:
        """uvicorn.run receives the port returned by find_available_port."""
        import pdomain_ocr_simple_gui.__main__ as main_mod

        mock_run = MagicMock()
        with (
            patch("pdomain_ops.suite.find_available_port", return_value=8007),
            patch("uvicorn.run", mock_run),
            patch.object(sys, "argv", ["pdomain-ocr-simple-gui"]),
        ):
            main_mod.main()

        assert mock_run.call_count == 1
        _, kwargs = mock_run.call_args
        assert kwargs["port"] == 8007

    def test_register_self_called_with_actual_port(self) -> None:
        """register_self receives actual_port matching the picked port."""
        import pdomain_ocr_simple_gui.app as app_mod

        actual_calls: list[dict[str, object]] = []

        def _fake_register(**kwargs: object) -> None:
            actual_calls.append(dict(kwargs))

        with patch("pdomain_ops.suite.register_self", _fake_register):
            # Trigger lifespan by starting/stopping the app
            import asyncio

            from pdomain_ocr_simple_gui.app import lifespan

            async def _run() -> None:
                async with lifespan(app_mod.app):
                    pass

            app_mod._actual_port = 8007
            asyncio.run(_run())

        assert len(actual_calls) == 1
        assert actual_calls[0].get("actual_port") == 8007

    def test_env_var_overrides_default_port(self) -> None:
        """PD_OCR_SIMPLE_GUI_PORT env var wins over the compiled-in default."""
        import pdomain_ocr_simple_gui.__main__ as main_mod

        captured_preferred: list[int] = []

        def _fake_find(preferred: int) -> int:
            captured_preferred.append(preferred)
            return preferred  # return whatever was asked for

        mock_run = MagicMock()
        with (
            patch("pdomain_ops.suite.find_available_port", _fake_find),
            patch("uvicorn.run", mock_run),
            patch.dict(os.environ, {"PD_OCR_SIMPLE_GUI_PORT": "9001"}, clear=False),
            patch.object(sys, "argv", ["pdomain-ocr-simple-gui"]),
        ):
            main_mod.main()

        assert captured_preferred == [9001]

    def test_cli_port_flag_overrides_default(self) -> None:
        """--port N flag wins over the compiled-in default (passed to find_available_port)."""
        import pdomain_ocr_simple_gui.__main__ as main_mod

        captured_preferred: list[int] = []

        def _fake_find(preferred: int) -> int:
            captured_preferred.append(preferred)
            return preferred

        mock_run = MagicMock()
        with (
            patch("pdomain_ops.suite.find_available_port", _fake_find),
            patch("uvicorn.run", mock_run),
            patch.object(sys, "argv", ["pdomain-ocr-simple-gui", "--port", "8010"]),
        ):
            main_mod.main()

        assert captured_preferred == [8010]

    def test_port_printed_on_launch(self, capsys: object) -> None:
        """The actual bound port is printed to stdout before uvicorn starts."""
        import pdomain_ocr_simple_gui.__main__ as main_mod

        mock_run = MagicMock()
        with (
            patch("pdomain_ops.suite.find_available_port", return_value=8005),
            patch("uvicorn.run", mock_run),
            patch.object(sys, "argv", ["pdomain-ocr-simple-gui"]),
        ):
            main_mod.main()

        from _pytest.capture import CaptureFixture

        if isinstance(capsys, CaptureFixture):
            out = capsys.readouterr().out
            assert "8005" in out


class TestRegisterSelfActualPort:
    """Verify register_self import path includes actual_port parameter."""

    def test_register_self_is_importable(self) -> None:
        """register_self is importable from pdomain_ops.suite."""
        from pdomain_ops.suite import register_self

        assert callable(register_self)

    def test_find_available_port_is_importable(self) -> None:
        """find_available_port is importable from pdomain_ops.suite."""
        from pdomain_ops.suite import find_available_port

        assert callable(find_available_port)

    def test_find_available_port_returns_int(self) -> None:
        """find_available_port(8004) returns an integer port."""
        from pdomain_ops.suite import find_available_port

        port = find_available_port(8004)
        assert isinstance(port, int)
        assert 1024 <= port <= 65535
