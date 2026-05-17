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
    args = parser.parse_args()

    import uvicorn

    uvicorn.run(
        "pd_ocr_simple_gui.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
