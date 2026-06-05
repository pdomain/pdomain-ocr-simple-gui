"""Entry point for pdomain-ocr-simple-gui."""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from pdomain_ops.desktop import run_windowed
from pdomain_ops.suite import bootstrap_spa
from pdomain_ops.suite.desktop import (
    install_shortcut,
    remove_shortcut,
)
from pdomain_ops.suite.update import apply_upgrade

if TYPE_CHECKING:
    from pdomain_ops.suite.types import InstalledApp

logger = logging.getLogger(__name__)

PREFERRED_PORT = 8004


@dataclass(frozen=True)
class _CliArgs:
    host: str
    port: int
    reload: bool
    desktop: bool
    update: bool
    unregister_suite: bool
    install_desktop_shortcut: bool
    remove_desktop_shortcut: bool


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
        type=int,
        default=PREFERRED_PORT,
        help="Port to listen on (default: 8004, or PD_OCR_SIMPLE_GUI_PORT env var)",
    )
    _ = parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload (dev mode)",
    )
    _ = parser.add_argument(
        "--desktop",
        action="store_true",
        help="Launch in a native desktop window via pdomain_ops.desktop.run_windowed",
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
        port=cast("int", values["port"]),
        reload=cast("bool", values["reload"]),
        desktop=cast("bool", values["desktop"]),
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


def main(argv: list[str] | None = None) -> None:
    """Start the pdomain-ocr-simple-gui server."""
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

    if args.desktop:
        run_windowed("pdomain_ocr_simple_gui.app:app", title="OCR Simple GUI", preferred_port=args.port)
        return

    import uvicorn

    port = bootstrap_spa(
        preferred=args.port,
        caller_package="pdomain_ocr_simple_gui",
        port_env="PD_OCR_SIMPLE_GUI_PORT",
        host=args.host,
        url_label="pdomain-ocr-simple-gui",
    )

    uvicorn.run(
        "pdomain_ocr_simple_gui.app:app",
        host=args.host,
        port=port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
