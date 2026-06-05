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
imported (e.g. for testing) without a display.  ``make ci`` never calls the
GUI path, so the import guard is CI-safe.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from typing import cast

from installer.install_engine import (
    Step,
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

    # Simple heuristic: try importing the webview Python binding.
    # If it raises, assume the native runtime is absent.
    has_webview = False
    try:
        import webview as _webview  # type: ignore[import-not-found]  # pyright: ignore[reportMissingImports]  # import for side-effect availability check

        has_webview = _webview is not None
    except ImportError:
        pass

    gpu = detect_nvidia()
    return plan_steps(has_uv=has_uv, has_webview=has_webview, gpu=gpu, mgr=mgr)


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
    """Launch the tkinter step-by-step wizard.

    The wizard is a simple multi-page dialog:
      Page 0 — welcome / prerequisites summary
      Pages 1…N — one step per page (description + command + Yes/Skip)
      Final page — success summary

    tkinter is imported here (not at module level) so the module is importable
    in headless environments without raising TclError.
    """
    import tkinter as tk
    from tkinter import ttk

    steps = _build_steps()

    root = tk.Tk()
    root.title("pdomain-ocr-simple-gui Installer")
    root.resizable(False, False)

    # ── State ──────────────────────────────────────────────────────────────
    # Index 0 = welcome page; indices 1…N = step pages; index N+1 = done page
    current: list[int] = [0]  # mutable int via list (tk callbacks are closures)

    # ── Widgets ────────────────────────────────────────────────────────────
    frame = ttk.Frame(root, padding=20)
    frame.grid(sticky="nsew")
    _ = root.columnconfigure(0, weight=1)
    _ = root.rowconfigure(0, weight=1)

    title_var = tk.StringVar()
    body_var = tk.StringVar()
    cmd_var = tk.StringVar()

    ttk.Label(frame, textvariable=title_var, font=("TkDefaultFont", 14, "bold")).grid(
        row=0, column=0, columnspan=2, sticky="w", pady=(0, 8)
    )
    ttk.Label(frame, textvariable=body_var, wraplength=480, justify="left").grid(
        row=1, column=0, columnspan=2, sticky="w", pady=(0, 6)
    )
    cmd_label = ttk.Label(
        frame,
        textvariable=cmd_var,
        font=("TkFixedFont", 10),
        foreground="#555",
        wraplength=480,
        justify="left",
    )
    cmd_label.grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 12))

    btn_yes = ttk.Button(frame, text="Install →")
    btn_yes.grid(row=3, column=0, sticky="w", padx=(0, 4))
    btn_skip = ttk.Button(frame, text="Skip")
    btn_skip.grid(row=3, column=1, sticky="w")

    status_var = tk.StringVar()
    ttk.Label(frame, textvariable=status_var, foreground="#c00").grid(
        row=4, column=0, columnspan=2, sticky="w", pady=(6, 0)
    )

    # ── Page rendering ─────────────────────────────────────────────────────

    def render_page(idx: int) -> None:
        """Update labels and button states for page at index ``idx``."""
        if idx == 0:
            title_var.set("pdomain-ocr-simple-gui Installer")
            body_var.set(
                "This wizard will install pdomain-ocr-simple-gui and its prerequisites.\n\n"
                + f"{len(steps)} step(s) identified for this system.\n\n"
                + "Click 'Install →' to begin."
            )
            cmd_var.set("")
            _ = btn_yes.config(text="Begin →", state="normal")
            _ = btn_skip.config(state="disabled")
        elif idx <= len(steps):
            step = steps[idx - 1]
            sudo_tag = " (requires sudo)" if step.needs_sudo else ""
            title_var.set(f"Step {idx} of {len(steps)}: {step.id}")
            body_var.set(step.description + sudo_tag)
            cmd_var.set(f"$ {step.command}")
            _ = btn_yes.config(text="Run this step →", state="normal")
            _ = btn_skip.config(state="normal")
        else:
            title_var.set("Installation complete")
            body_var.set(
                "pdomain-ocr-simple-gui has been installed.\n\n"
                + "Launch it from your application menu or run:\n"
                + "    pdomain-ocr-simple-gui\n\n"
                + "Close this window to exit."
            )
            cmd_var.set("")
            _ = btn_yes.config(text="Close", state="normal")
            _ = btn_skip.config(state="disabled")

    # ── Button handlers ────────────────────────────────────────────────────

    def on_yes() -> None:
        idx = current[0]
        if idx == 0:
            # Welcome page — advance
            current[0] = 1
            render_page(1)
            return
        if idx > len(steps):
            # Done page — close
            root.destroy()
            return
        step = steps[idx - 1]
        status_var.set("")
        if not dry_run:
            import shlex as _shlex

            cmd_tokens = list(step.command) if isinstance(step.command, list) else _shlex.split(step.command)
            if step.needs_sudo:
                cmd_tokens = ["sudo", *cmd_tokens]
            try:
                _ = subprocess.run(cmd_tokens, check=True)  # noqa: S603
            except subprocess.CalledProcessError as exc:
                status_var.set(f"Step failed (exit {exc.returncode}). Check terminal output.")
                return
        _advance()

    def on_skip() -> None:
        status_var.set("")
        _advance()

    def _advance() -> None:
        next_idx = current[0] + 1
        current[0] = next_idx
        render_page(next_idx)

    _ = btn_yes.config(command=on_yes)
    _ = btn_skip.config(command=on_skip)

    render_page(0)
    root.mainloop()


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
