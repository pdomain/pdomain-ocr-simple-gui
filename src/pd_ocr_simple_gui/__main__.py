"""Entry point for pd-ocr-simple-gui."""

from __future__ import annotations

import argparse


def main() -> None:
    """Start the pd-ocr-simple-gui server."""
    parser = argparse.ArgumentParser(
        description="pd-ocr-simple-gui — drag-and-drop OCR app",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8004,
        help="Port to listen on (default: 8004)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload (dev mode)",
    )
    parser.add_argument(
        "--unregister-suite",
        action="store_true",
        help="Unregister this app from the suite registry and exit",
    )
    parser.add_argument(
        "--install-desktop-shortcut",
        action="store_true",
        help="Install a desktop shortcut for this app (not implemented)",
    )
    parser.add_argument(
        "--remove-desktop-shortcut",
        action="store_true",
        help="Remove the desktop shortcut for this app (not implemented)",
    )
    args = parser.parse_args()

    if args.unregister_suite:
        try:
            from pd_ocr_ops.suite.registry import LocalTomlSuiteRegistry

            registry = LocalTomlSuiteRegistry()
            registry.unregister("pd-ocr-simple-gui")
        except Exception:  # noqa: BLE001, S110  # best-effort suite unregister — never block shutdown
            pass
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
