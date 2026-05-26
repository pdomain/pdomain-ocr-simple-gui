"""Entry point for pd-ocr-simple-gui."""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from typing import cast

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _CliArgs:
    host: str
    port: int
    reload: bool
    unregister_suite: bool
    install_desktop_shortcut: bool
    remove_desktop_shortcut: bool


def _parse_args() -> _CliArgs:
    parser = argparse.ArgumentParser(
        description="pd-ocr-simple-gui — drag-and-drop OCR app",
    )
    _ = parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)",
    )
    _ = parser.add_argument(
        "--port",
        type=int,
        default=8004,
        help="Port to listen on (default: 8004)",
    )
    _ = parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload (dev mode)",
    )
    _ = parser.add_argument(
        "--unregister-suite",
        action="store_true",
        help="Unregister this app from the suite registry and exit",
    )
    _ = parser.add_argument(
        "--install-desktop-shortcut",
        action="store_true",
        help="Install a desktop shortcut for this app (not implemented)",
    )
    _ = parser.add_argument(
        "--remove-desktop-shortcut",
        action="store_true",
        help="Remove the desktop shortcut for this app (not implemented)",
    )

    parsed = parser.parse_args()
    values = cast("dict[str, object]", vars(parsed))
    return _CliArgs(
        host=cast("str", values["host"]),
        port=cast("int", values["port"]),
        reload=cast("bool", values["reload"]),
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


def main() -> None:
    """Start the pd-ocr-simple-gui server."""
    args = _parse_args()

    if args.unregister_suite:
        try:
            from pd_ocr_ops.suite.registry import (  # pyright: ignore[reportMissingTypeStubs] pd_ocr_ops dependency may omit typing stubs
                LocalTomlSuiteRegistry,
            )

            registry = LocalTomlSuiteRegistry()
            registry.unregister("pd-ocr-simple-gui")
        except Exception:  # best-effort suite unregister — never block shutdown
            logger.exception(
                "Failed to unregister from suite registry; stale entry may remain",
                extra={"context": "LocalTomlSuiteRegistry.unregister('pd-ocr-simple-gui')"},
            )
        return

    if args.install_desktop_shortcut:
        raise NotImplementedError("--install-desktop-shortcut is not implemented in Phase 1")

    if args.remove_desktop_shortcut:
        raise NotImplementedError("--remove-desktop-shortcut is not implemented in Phase 1")

    import uvicorn

    uvicorn.run(
        "pd_ocr_simple_gui.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
