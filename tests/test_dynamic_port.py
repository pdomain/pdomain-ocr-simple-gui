"""Tests for dynamic port selection via bootstrap_spa."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch


class TestDynamicPortCLI:
    """Unit tests: bootstrap_spa drives uvicorn.run."""

    def test_uvicorn_called_with_picked_port(self) -> None:
        """uvicorn.run receives the port returned by bootstrap_spa."""
        import pdomain_ocr_simple_gui.__main__ as main_mod

        mock_run = MagicMock()
        with (
            patch(
                "pdomain_ocr_simple_gui.__main__.bootstrap_spa",
                return_value=8007,
            ),
            patch("uvicorn.run", mock_run),
            patch.object(sys, "argv", ["pdomain-ocr-simple-gui"]),
        ):
            main_mod.main()

        assert mock_run.call_count == 1
        _, kwargs = mock_run.call_args
        assert kwargs["port"] == 8007

    def test_bootstrap_spa_called_with_expected_kwargs(self) -> None:
        """bootstrap_spa receives preferred, caller_package, and port_env."""
        import pdomain_ocr_simple_gui.__main__ as main_mod

        mock_bootstrap = MagicMock(return_value=8004)
        mock_run = MagicMock()
        with (
            patch(
                "pdomain_ocr_simple_gui.__main__.bootstrap_spa",
                mock_bootstrap,
            ),
            patch("uvicorn.run", mock_run),
            patch.object(sys, "argv", ["pdomain-ocr-simple-gui"]),
        ):
            main_mod.main()

        assert mock_bootstrap.call_count == 1
        _, kwargs = mock_bootstrap.call_args
        assert kwargs["caller_package"] == "pdomain_ocr_simple_gui"
        assert kwargs["port_env"] == "PD_OCR_SIMPLE_GUI_PORT"

    def test_cli_port_flag_overrides_default(self) -> None:
        """--port N flag is forwarded as preferred= to bootstrap_spa."""
        import pdomain_ocr_simple_gui.__main__ as main_mod

        captured_preferred: list[int] = []

        def _fake_bootstrap(**kwargs: object) -> int:
            captured_preferred.append(int(kwargs["preferred"]))  # type: ignore[arg-type]
            return int(kwargs["preferred"])  # type: ignore[return-value]

        mock_run = MagicMock()
        with (
            patch(
                "pdomain_ocr_simple_gui.__main__.bootstrap_spa",
                _fake_bootstrap,
            ),
            patch("uvicorn.run", mock_run),
            patch.object(sys, "argv", ["pdomain-ocr-simple-gui", "--port", "8010"]),
        ):
            main_mod.main()

        assert captured_preferred == [8010]


class TestBootstrapSpaImportable:
    """Verify bootstrap_spa is importable from pdomain_ops.suite."""

    def test_bootstrap_spa_is_importable(self) -> None:
        """bootstrap_spa is importable from pdomain_ops.suite."""
        from pdomain_ops.suite import bootstrap_spa

        assert callable(bootstrap_spa)

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
