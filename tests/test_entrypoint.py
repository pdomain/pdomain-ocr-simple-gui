"""Tests for pdomain_ocr_simple_gui.__main__ entry point."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

# When tests run from a git worktree, the shared venv's editable install
# points to the canonical src/ (not the worktree src/). Subprocess tests
# that invoke the module via `python -m` must override PYTHONPATH so they
# see the worktree's source instead of the installed package.
_WORKTREE_SRC = str(Path(__file__).parent.parent / "src")
_SUBPROCESS_ENV = {**os.environ, "PYTHONPATH": _WORKTREE_SRC}


class TestEntrypoint:
    def test_help_exits_zero(self) -> None:
        """--help exits 0 and prints usage."""
        result = subprocess.run(
            [sys.executable, "-m", "pdomain_ocr_simple_gui", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
            env=_SUBPROCESS_ENV,
        )
        assert result.returncode == 0
        assert "--port" in result.stdout
        assert "--host" in result.stdout

    def test_unknown_flag_exits_nonzero(self) -> None:
        """An unrecognized flag must exit non-zero (argparse default)."""
        result = subprocess.run(
            [sys.executable, "-m", "pdomain_ocr_simple_gui", "--not-a-real-flag"],
            capture_output=True,
            text=True,
            timeout=10,
            env=_SUBPROCESS_ENV,
        )
        assert result.returncode != 0

    def test_module_main_importable(self) -> None:
        """The main() function is importable without side effects."""
        from pdomain_ocr_simple_gui.__main__ import main

        assert callable(main)

    def test_desktop_flag_rejected(self) -> None:
        """--desktop is not a valid flag; argparse must reject it (exit non-zero)."""
        result = subprocess.run(
            [sys.executable, "-m", "pdomain_ocr_simple_gui", "--desktop"],
            capture_output=True,
            text=True,
            timeout=10,
            env=_SUBPROCESS_ENV,
        )
        assert result.returncode != 0

    def test_no_browser_flag_accepted(self) -> None:
        """--no-browser is a valid flag; --help must mention it."""
        result = subprocess.run(
            [sys.executable, "-m", "pdomain_ocr_simple_gui", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
            env=_SUBPROCESS_ENV,
        )
        assert result.returncode == 0
        assert "--no-browser" in result.stdout


class TestBrowserUrl:
    def test_localhost_passthrough(self) -> None:
        """127.0.0.1 host → URL uses 127.0.0.1."""
        from pdomain_ocr_simple_gui.__main__ import _browser_url

        assert _browser_url("127.0.0.1", 8004) == "http://127.0.0.1:8004"

    def test_wildcard_ipv4_resolves_to_localhost(self) -> None:
        """0.0.0.0 → resolves to 127.0.0.1 in the browser URL."""
        from pdomain_ocr_simple_gui.__main__ import _browser_url

        assert _browser_url("0.0.0.0", 8004) == "http://127.0.0.1:8004"

    def test_wildcard_ipv6_resolves_to_localhost(self) -> None:
        """:: → resolves to 127.0.0.1 in the browser URL."""
        from pdomain_ocr_simple_gui.__main__ import _browser_url

        assert _browser_url("::", 8004) == "http://127.0.0.1:8004"

    def test_custom_host_preserved(self) -> None:
        """A non-wildcard host is preserved as-is."""
        from pdomain_ocr_simple_gui.__main__ import _browser_url

        assert _browser_url("192.168.1.10", 9000) == "http://192.168.1.10:9000"


class TestShouldOpenBrowser:
    def test_default_opens_browser(self) -> None:
        """no_browser=False → should open (the default)."""
        from pdomain_ocr_simple_gui.__main__ import _should_open_browser

        assert _should_open_browser(no_browser=False) is True

    def test_no_browser_suppresses(self) -> None:
        """no_browser=True → should NOT open."""
        from pdomain_ocr_simple_gui.__main__ import _should_open_browser

        assert _should_open_browser(no_browser=True) is False


class TestOpenBrowserWhenReady:
    def test_opens_browser_when_server_responds(self) -> None:
        """Server responds quickly → webbrowser.open is called with the URL."""
        from pdomain_ocr_simple_gui.__main__ import _open_browser_when_ready

        open_calls: list[str] = []

        class _FakeConn:
            def __init__(self, *a: object, **kw: object) -> None:
                pass

            def request(self, *a: object, **kw: object) -> None:
                pass

            def getresponse(self) -> MagicMock:
                resp = MagicMock()
                resp.status = 200
                return resp

            def close(self) -> None:
                pass

        with (
            patch("webbrowser.open", side_effect=open_calls.append),
            patch("http.client.HTTPConnection", _FakeConn),
        ):
            _open_browser_when_ready("http://127.0.0.1:8004", timeout=5.0)

        assert open_calls == ["http://127.0.0.1:8004"]

    def test_no_browser_on_timeout(self) -> None:
        """Server never responds → webbrowser.open is NOT called (silent timeout)."""
        from pdomain_ocr_simple_gui.__main__ import _open_browser_when_ready

        open_calls: list[str] = []

        def _always_fail(*a: object, **kw: object) -> None:
            raise OSError("connection refused")

        with (
            patch("webbrowser.open", side_effect=open_calls.append),
            patch("http.client.HTTPConnection", side_effect=_always_fail),
        ):
            _open_browser_when_ready("http://127.0.0.1:8004", timeout=0.1)

        assert open_calls == []

    def test_browser_thread_starts_by_default(self) -> None:
        """Default launch (no --no-browser) starts a daemon thread before uvicorn.run."""
        started_threads: list[threading.Thread] = []
        original_start = threading.Thread.start

        def _capture_start(self: threading.Thread) -> None:
            started_threads.append(self)
            # Do NOT actually start the thread — we just capture it.
            # This prevents the real poll logic from running in tests.

        open_calls: list[str] = []

        with (
            patch("pdomain_ocr_simple_gui.__main__.bootstrap_spa", return_value=8004),
            patch("uvicorn.run"),
            patch.object(threading.Thread, "start", _capture_start),
            patch("webbrowser.open", side_effect=open_calls.append),
        ):
            from pdomain_ocr_simple_gui.__main__ import main

            main([])

        assert len(started_threads) >= 1
        daemon_threads = [t for t in started_threads if t.daemon]
        assert len(daemon_threads) >= 1
        # Restore
        threading.Thread.start = original_start  # type: ignore[method-assign]

    def test_no_browser_flag_skips_thread(self) -> None:
        """--no-browser → no browser-open thread is started."""
        started_threads: list[threading.Thread] = []
        original_start = threading.Thread.start

        def _capture_start(self: threading.Thread) -> None:
            started_threads.append(self)

        with (
            patch("pdomain_ocr_simple_gui.__main__.bootstrap_spa", return_value=8004),
            patch("uvicorn.run"),
            patch.object(threading.Thread, "start", _capture_start),
        ):
            from pdomain_ocr_simple_gui.__main__ import main

            main(["--no-browser"])

        assert started_threads == []
        # Restore
        threading.Thread.start = original_start  # type: ignore[method-assign]
