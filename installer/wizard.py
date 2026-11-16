"""AppImage installer wizard for pdomain-ocr-simple-gui.

Entry point: ``python -m installer.wizard [--cli] [--yes] [--dry-run]``

GUI path (default when DISPLAY is available):
  A minimal tkinter wizard walks the user through the same gated steps
  produced by ``install_engine.plan_steps()``.  Each page shows one step:
  description, the exact command that will run (with sudo marker), and
  Yes/Skip buttons.

CLI path (``--cli`` flag or no DISPLAY):
  Delegates directly to ``install_engine.run()`` with optional ``--yes``.

The tkinter import is deferred inside ``_run_gui()`` so this module can be
imported (e.g. for testing) without a display.  ``just ci`` never calls the
GUI path, so the import guard is CI-safe.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from typing import cast

from installer.install_engine import (
    Step,
    _query_cuda_version,  # pyright: ignore[reportPrivateUsage]
    detect_nvidia,
    detect_pkg_manager,
    plan_steps,
    run,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_steps() -> list[Step]:
    """Probe the environment and return the plan for this machine."""
    has_uv = shutil.which("uv") is not None
    mgr = detect_pkg_manager()

    gpu = detect_nvidia()
    # A detected CUDA version turns on `--torch-backend auto`.
    # cuda_version is None when CUDA is not detectable (CPU fallback).
    cuda_version = _query_cuda_version() if gpu == "nvidia" else None
    return plan_steps(
        has_uv=has_uv,
        gpu=gpu,
        mgr=mgr,
        cuda_version=cuda_version,
    )


# ---------------------------------------------------------------------------
# CLI path
# ---------------------------------------------------------------------------


def _run_cli(*, assume_yes: bool, dry_run: bool) -> None:
    """Run the installer in headless / interactive CLI mode."""
    steps = _build_steps()
    if not steps:
        print("Nothing to install — all prerequisites already satisfied.")  # noqa: T201
        return
    run(steps, assume_yes=assume_yes, dry_run=dry_run)


# ---------------------------------------------------------------------------
# GUI path (tkinter wizard)
# ---------------------------------------------------------------------------


def _run_gui(*, dry_run: bool) -> None:
    """Install through the bundled script with native progress and retry."""
    import os
    from pathlib import Path

    from installer.unix.native import linux_dialog

    payload = Path(os.environ.get("PD_SIMPLE_GUI_INSTALL_ROOT", Path(__file__).resolve().parent.parent))
    linux_dialog(payload, removing=False, dry_run=dry_run)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    """Parse args and dispatch to GUI or CLI installer."""
    parser = argparse.ArgumentParser(
        prog="pdomain-ocr-simple-gui-installer",
        description="Install pdomain-ocr-simple-gui and its prerequisites.",
    )
    _ = parser.add_argument("--cli", action="store_true", help="Force CLI (no GUI) mode")
    _ = parser.add_argument("--yes", action="store_true", help="Assume yes to all prompts (non-interactive)")
    _ = parser.add_argument("--dry-run", action="store_true", help="Print the plan but do not execute")
    args = parser.parse_args(argv)

    # argparse.Namespace attrs are typed as Any; cast to concrete types
    cli: bool = cast("bool", args.cli)
    yes: bool = cast("bool", args.yes)
    dry_run_flag: bool = cast("bool", args.dry_run)

    use_cli = cli or (not sys.stdin.isatty() and not _has_display())

    if use_cli:
        _run_cli(assume_yes=yes, dry_run=dry_run_flag)
    else:
        _run_gui(dry_run=dry_run_flag)


def _has_display() -> bool:
    """Return True if a display server is available."""
    import os

    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


if __name__ == "__main__":
    main()
