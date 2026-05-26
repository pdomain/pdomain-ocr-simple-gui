"""Tests for pdomain_ocr_simple_gui.__main__ entry point."""

from __future__ import annotations

import subprocess
import sys


class TestEntrypoint:
    def test_help_exits_zero(self) -> None:
        """--help exits 0 and prints usage."""
        result = subprocess.run(
            [sys.executable, "-m", "pdomain_ocr_simple_gui", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert "--port" in result.stdout
        assert "--host" in result.stdout

    def test_module_main_importable(self) -> None:
        """The main() function is importable without side effects."""
        from pdomain_ocr_simple_gui.__main__ import main

        assert callable(main)
