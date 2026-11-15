"""Entry point for pdomain-ocr-simple-gui."""

from __future__ import annotations

import argparse
import contextlib
import logging
import os
import sys
import threading
import time
import webbrowser
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from pdomain_ops.suite import register_self
from pdomain_ops.suite.desktop import (
    install_shortcut,
    remove_shortcut,
)
from pdomain_ops.suite.update import apply_upgrade
from uvicorn.config import STARTUP_FAILURE

from pdomain_ocr_simple_gui.ports import (
    PORT_ENV_VAR,
    PREFERRED_PORT,
    bind_listening_socket,
    is_valid_port,
    normalize_host,
    resolve_start_port,
    url_host,
)

if TYPE_CHECKING:
    import socket

    import uvicorn
    from pdomain_ops.suite.types import InstalledApp

logger = logging.getLogger(__name__)

_APP_IMPORT = "pdomain_ocr_simple_gui.app:app"


@dataclass(frozen=True)
class _CliArgs:
    host: str
    port: int | None
    reload: bool
    no_browser: bool
    update: bool
    unregister_suite: bool
    install_desktop_shortcut: bool
    remove_desktop_shortcut: bool


def _port_arg(text: str) -> int:
    """argparse type for ``--port``: an integer from 1 to 65535."""
    try:
        value = int(text)
    except ValueError:
        msg = f"invalid port: {text!r}"
        raise argparse.ArgumentTypeError(msg) from None
    if not is_valid_port(value):
        msg = f"port must be 1-65535, got {value}"
        raise argparse.ArgumentTypeError(msg)
    return value


def _parse_args(argv: list[str] | None = None) -> _CliArgs:
    parser = argparse.ArgumentParser(
        description="pdomain-ocr-simple-gui — drag-and-drop OCR app",
    )
    _ = parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)",
    )
    _ = parser.add_argument(
        "--port",
        type=_port_arg,
        default=None,
        help=(
            "Port to listen on. Precedence: this flag, then the "
            f"{PORT_ENV_VAR} env var, then {PREFERRED_PORT}. "
            "If that port is taken, the next free port is used."
        ),
    )
    _ = parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload (dev mode)",
    )
    _ = parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open the browser automatically (headless/CI/docker mode)",
    )
    _ = parser.add_argument(
        "--update",
        action="store_true",
        help="Run gated upgrade via pdomain_ops.suite.update.apply_upgrade then exit",
    )
    _ = parser.add_argument(
        "--unregister-suite",
        action="store_true",
        help="Unregister this app from the suite registry and exit",
    )
    _ = parser.add_argument(
        "--install-desktop-shortcut",
        action="store_true",
        help="Install a desktop shortcut for this app",
    )
    _ = parser.add_argument(
        "--remove-desktop-shortcut",
        action="store_true",
        help="Remove the desktop shortcut for this app",
    )

    parsed = parser.parse_args(argv)
    values = cast("dict[str, object]", vars(parsed))
    return _CliArgs(
        host=cast("str", values["host"]),
        port=cast("int | None", values["port"]),
        reload=cast("bool", values["reload"]),
        no_browser=cast("bool", values["no_browser"]),
        update=cast("bool", values["update"]),
        unregister_suite=cast("bool", values["unregister_suite"]),
        install_desktop_shortcut=cast(
            "bool",
            values["install_desktop_shortcut"],
        ),
        remove_desktop_shortcut=cast(
            "bool",
            values["remove_desktop_shortcut"],
        ),
    )


def _build_installed_app() -> InstalledApp:
    """Build an InstalledApp from the bundled pdomain-suite.json fragment.

    Returns an InstalledApp instance using metadata from the installed
    package and the bundled pdomain-suite.json resource.

    Returns:
        An InstalledApp Pydantic model populated from the suite fragment.
    """
    import importlib.metadata
    import importlib.resources
    import json
    from pathlib import Path

    from pdomain_ops.suite.types import InstalledApp

    pkg = "pdomain_ocr_simple_gui"
    raw = (importlib.resources.files(pkg) / "pdomain-suite.json").read_text(encoding="utf-8")
    fragment: dict[str, object] = cast("dict[str, object]", json.loads(raw))
    binary = str(Path(sys.argv[0]).resolve()) if sys.argv else ""
    try:
        version = importlib.metadata.version(pkg)
    except importlib.metadata.PackageNotFoundError:
        version = "0.0.0"
    return InstalledApp.model_validate({**fragment, "binary": binary, "version": version})


def _browser_url(host: str, port: int) -> str:
    """Return the URL to open in the browser.

    When host is a wildcard (0.0.0.0 or ::), resolve to 127.0.0.1 so the
    browser can actually connect.

    Args:
        host: The host the server is bound to.
        port: The port the server is listening on.

    Returns:
        A URL string like 'http://127.0.0.1:8004'.
    """
    bare = normalize_host(host)
    connect_host = "127.0.0.1" if bare in ("0.0.0.0", "::") else url_host(bare)  # noqa: S104
    return f"http://{connect_host}:{port}"


def _should_open_browser(*, no_browser: bool) -> bool:
    """Return True iff the browser should be opened automatically.

    Args:
        no_browser: True when --no-browser was passed.

    Returns:
        True when auto-open is desired.
    """
    return not no_browser


def _open_browser_when_ready(url: str, *, timeout: float = 10.0) -> None:
    """Poll the server until it responds, then open the browser.

    Runs as a daemon thread.  Polls ``url`` with HTTP GET until a non-error
    response is received, or until ``timeout`` seconds elapse.  Opens the
    browser on first success; silently gives up on timeout (no crash).

    Args:
        url:     The URL to open (already resolved to 127.0.0.1 if needed).
        timeout: Maximum seconds to wait before giving up.
    """
    import http.client
    import urllib.parse

    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 80
    path = parsed.path or "/"

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with contextlib.suppress(Exception):
            conn = http.client.HTTPConnection(host, port, timeout=2)
            try:
                conn.request("GET", path)
                resp = conn.getresponse()
                if resp.status < 500:
                    _ = webbrowser.open(url)
                    return
            finally:
                with contextlib.suppress(Exception):
                    conn.close()
        time.sleep(0.25)
    # Timeout elapsed — give up silently.


def _tolerate_unencodable_output() -> None:
    """Replace characters stdout/stderr cannot encode instead of raising.

    Windows Python writes cp1252 to a redirected stdout. pdomain-ops prints an
    emoji at startup, which raised UnicodeEncodeError and stopped the app
    before it served (seen on Windows 11, 2026-11-13).
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            with contextlib.suppress(ValueError, OSError):
                _ = reconfigure(errors="backslashreplace")


def _register_and_announce(*, host: str, port: int) -> None:
    """Record the real port in the suite registry and print the URL line."""
    try:
        register_self(_caller_package="pdomain_ocr_simple_gui", actual_port=port)
    except Exception as exc:  # noqa: BLE001  # optional registry; startup continues
        logger.warning("Suite registry registration failed (non-fatal): %s", exc)
    line = f"🚀 pdomain-ocr-simple-gui at http://{url_host(host)}:{port}/"
    try:
        print(line)  # startup URL is intentional CLI output
    except UnicodeEncodeError:
        # cp1252 redirected stdout on Windows has no emoji; nothing was written.
        print(line.removeprefix("🚀 "))  # startup URL is intentional CLI output


def _serve(sock: socket.socket, config: uvicorn.Config) -> None:
    """Run uvicorn on the already-bound, listening ``sock``."""
    import uvicorn
    from uvicorn.supervisors import ChangeReload

    server = uvicorn.Server(config)
    try:
        if config.should_reload:
            ChangeReload(config, target=server.run, sockets=[sock]).run()
        else:
            server.run(sockets=[sock])
    except KeyboardInterrupt:
        return
    if not server.started and not config.should_reload:
        sys.exit(STARTUP_FAILURE)


def main(argv: list[str] | None = None) -> None:
    """Start the pdomain-ocr-simple-gui server."""
    _tolerate_unencodable_output()
    args = _parse_args(argv)

    if args.update:
        try:
            apply_upgrade("pdomain-ocr-simple-gui")
        except NotImplementedError as exc:
            print(f"error: {exc}", file=sys.stderr)
            sys.exit(1)
        return

    if args.unregister_suite:
        try:
            from pdomain_ops.suite.registry import (
                LocalTomlSuiteRegistry,
            )

            registry = LocalTomlSuiteRegistry()
            registry.unregister("pdomain-ocr-simple-gui")
        except Exception:  # best-effort suite unregister — never block shutdown
            logger.exception(
                "Failed to unregister from suite registry; stale entry may remain",
                extra={"context": "LocalTomlSuiteRegistry.unregister('pdomain-ocr-simple-gui')"},
            )
        return

    if args.install_desktop_shortcut:
        try:
            install_shortcut(_build_installed_app())
        except NotImplementedError as exc:
            print(f"error: {exc}", file=sys.stderr)
            sys.exit(1)
        return

    if args.remove_desktop_shortcut:
        try:
            remove_shortcut("pdomain-ocr-simple-gui")
        except NotImplementedError as exc:
            print(f"error: {exc}", file=sys.stderr)
            sys.exit(1)
        return

    import uvicorn

    from pdomain_ocr_simple_gui.cache_configuration import apply_saved_model_cache_location

    apply_saved_model_cache_location()
    host = normalize_host(args.host)
    sock = bind_listening_socket(host, resolve_start_port(args.port, os.environ))
    try:
        port = int(cast("tuple[str, int]", sock.getsockname())[1])
        config = uvicorn.Config(_APP_IMPORT, host=host, port=port, reload=args.reload)
        if not config.should_reload:
            # Load the config and import the app first, so an import failure exits before the
            # registry write, the URL line and the browser open, as before.
            config.load()
        _register_and_announce(host=host, port=port)

        if _should_open_browser(no_browser=args.no_browser):
            url = _browser_url(host, port)
            t = threading.Thread(target=_open_browser_when_ready, args=(url,), daemon=True)
            t.start()

        _serve(sock, config)
    finally:
        # uvicorn closes its own sockets on shutdown; a second close is a
        # harmless no-op, and this one covers every path that never reached it.
        sock.close()


if __name__ == "__main__":
    main()
