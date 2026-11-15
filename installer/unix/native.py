"""Native user installation controls for Linux and macOS."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import plistlib
import shlex
import shutil
import sys
import tempfile
import threading
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

APP = "pdomain-ocr-simple-gui"

JSONScalar = str | int | float | bool | None
JSONValue = JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]


def decode_object(text: str) -> dict[str, JSONValue]:
    """Decode native helper output through a typed JSON boundary."""
    decoder: Callable[..., JSONValue] = json.loads
    value = decoder(text)
    if not isinstance(value, dict):
        raise TypeError("Expected a JSON object")
    return value


def install_command(payload: Path) -> list[str]:
    """Use the release installer for both bundled and published wheels."""
    return ["/bin/sh", str(payload / "install.sh"), "--no-appimage", "-y"]


def desktop_quote(value: str) -> str:
    """Quote one desktop Exec field argument."""
    return (
        '"'
        + value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("`", "\\`")
        .replace("$", "\\$")
        .replace("%", "%%")
        + '"'
    )


def application_bundle(target: Path, command: list[str]) -> Path:
    """Create an application bundle with an executable launch script."""
    contents = target / "Contents"
    executable = contents / "MacOS" / "launch"
    executable.parent.mkdir(parents=True, exist_ok=True)
    import shlex

    _ = executable.write_text("#!/bin/sh\nset -eu\nexec " + shlex.join(command) + "\n")
    executable.chmod(0o755)
    with (contents / "Info.plist").open("wb") as stream:
        plistlib.dump(
            {
                "CFBundleName": target.stem,
                "CFBundleExecutable": "launch",
                "CFBundlePackageType": "APPL",
                "LSUIElement": True,
            },
            stream,
        )
    return target


def retained_base_python() -> str:
    """Keep removal launchers independent of the removable tool environment."""
    base: object = getattr(sys, "_base_executable", None)
    if not isinstance(base, str):
        raise TypeError("Python does not report a retained base interpreter")
    interpreter = Path(base).resolve()
    if not interpreter.is_file() or not os.access(interpreter, os.X_OK):
        raise FileNotFoundError(f"Retained base Python is not executable: {interpreter}")
    if sys.prefix != sys.base_prefix and interpreter.is_relative_to(Path(sys.prefix).resolve()):
        raise ValueError("Uninstall launcher requires Python outside the removable tool environment")
    return str(interpreter)


def install_entries(
    home: Path, command: Path, wrapper: Path, report: Callable[[str], None] | None = None
) -> list[Path]:
    """Publish desktop controls only after verifying their launch target."""
    if not command.is_file() or not os.access(command, os.X_OK):
        raise FileNotFoundError(f"Installed desktop launcher is missing or not executable: {command}")
    removal_python = retained_base_python()
    if sys.platform == "darwin":
        applications = home / "Applications"
        return [
            application_bundle(applications / "OCR Simple GUI.app", [str(command)]),
            application_bundle(
                applications / "Uninstall OCR Simple GUI.app", [removal_python, str(wrapper), "--uninstall"]
            ),
        ]
    directory = Path(os.environ.get("XDG_DATA_HOME", str(home / ".local/share"))) / "applications"
    directory.mkdir(parents=True, exist_ok=True)
    legacy = directory / ("pdomain-" + APP + ".desktop")
    verified_legacy = False
    if legacy.is_file():
        console = command.parent / APP
        expected = [
            "[Desktop Entry]",
            "Version=1.0",
            "Type=Application",
            "Name=Simple OCR",
            "Exec=" + shlex.quote(str(console.resolve())),
            "Icon=" + APP,
            "Terminal=false",
            "Categories=Utility;",
            "",
        ]
        verified_legacy = console.is_file() and legacy.read_text() == "\n".join(expected)
        if not verified_legacy and report is not None:
            report(f"Kept an unrecognized existing shortcut: {legacy}\n")
    entries: list[Path] = []
    for name, filename, argv in [
        ("OCR Simple GUI", APP, [str(command)]),
        ("Uninstall OCR Simple GUI", APP + "-uninstall", [removal_python, str(wrapper), "--uninstall"]),
    ]:
        entry = directory / (filename + ".desktop")
        _ = entry.write_text(
            "[Desktop Entry]\nType=Application\nName="
            + name
            + "\nExec="
            + " ".join(desktop_quote(arg) for arg in argv)
            + "\nTerminal=false\nCategories=Office;\n"
        )
        entry.chmod(0o755)
        entries.append(entry)
    if verified_legacy:
        legacy.unlink()
        entries.append(legacy)
    return entries


class NativeCommandError(RuntimeError):
    """Retain native exit details for cancellation handling."""

    def __init__(self, status: int, output: str) -> None:
        self.status: int = status
        self.output: str = output
        super().__init__(f"Operation failed (exit {status}).\n" + output[-6000:])


async def execute(command: list[str], output: Callable[[str], None]) -> str:
    """Capture child output while leaving the native event loop responsive."""
    process = await asyncio.create_subprocess_exec(
        *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
    )
    if process.stdout is None:
        raise RuntimeError("Could not capture installer output")
    chunks: list[str] = []
    async for line in process.stdout:
        text = line.decode(errors="replace")
        chunks.append(text)
        output(text)
    status = await process.wait()
    if status:
        raise NativeCommandError(status, "".join(chunks))
    return "".join(chunks)


def uv_executable() -> str:
    """Locate uv even when Finder supplies a minimal PATH."""
    candidate = shutil.which("uv")
    if candidate:
        return candidate
    destination = next(
        (
            os.environ[key]
            for key in ("UV_UNMANAGED_INSTALL", "UV_INSTALL_DIR", "XDG_BIN_HOME")
            if os.environ.get(key)
        ),
        None,
    )
    if destination is None:
        data_home = os.environ.get("XDG_DATA_HOME")
        destination = str(Path(data_home) / "../bin") if data_home else str(Path.home() / ".local/bin")
    local = Path(destination) / "uv"
    if local.is_file() and os.access(local, os.X_OK):
        return str(local)
    raise FileNotFoundError("uv was not found. Retry the installer to repair the installation.")


async def install(payload: Path, output: Callable[[str], None]) -> None:
    """Install the tool and record the exact desktop integration paths."""
    wheels = list(payload.glob("*.whl"))
    if len(wheels) == 1:
        os.environ["PD_SIMPLE_GUI_INSTALL_WHEEL"] = str(wheels[0].resolve())
    _ = await execute(install_command(payload), output)
    await integrate(output)


async def integrate(output: Callable[[str], None]) -> None:
    """Add desktop controls to the installed tool."""
    uv = uv_executable()
    bin_dir = Path((await execute([uv, "tool", "dir", "--bin"], lambda _: None)).strip())
    tool_dir = Path((await execute([uv, "tool", "dir"], lambda _: None)).strip())
    command = bin_dir / "pdomain-ocr-simple-gui-desktop"
    if not command.is_file() or not os.access(command, os.X_OK):
        raise FileNotFoundError(f"The installed wheel has no desktop launcher: {command}")
    owned = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share"))) / APP / "native"
    owned.mkdir(parents=True, exist_ok=True)
    wrapper = owned / "native.py"
    _ = shutil.copyfile(__file__, wrapper)
    entries = install_entries(Path.home(), command, wrapper, output)
    manifest = {
        "schema_version": 1,
        "uv_tool_dir": str(tool_dir),
        "uv_tool_bin_dir": str(bin_dir),
        "owned_paths": [str(path) for path in [wrapper, *entries]],
        "desktop_entries": [str(path) for path in entries],
        "wrapper_paths": [str(wrapper)],
    }
    _ = (owned.parent / "installation-manifest.json").write_text(json.dumps(manifest, indent=2))
    output("Installation complete. Open OCR Simple GUI from your applications menu.\n")


def save_removal_state(path: Path, state: dict[str, JSONValue]) -> None:
    """Publish durable recovery state without truncating its previous record."""
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    staged = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            _ = stream.write(json.dumps(state))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(staged, path)
    finally:
        staged.unlink(missing_ok=True)


def _entry_present(path: Path) -> bool:
    try:
        _ = path.lstat()
    except FileNotFoundError:
        return False
    return True


async def uninstall(output: Callable[[str], None]) -> None:
    """Stage removal before deleting the tool interpreter."""
    manifest_path = (
        Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share")))
        / APP
        / "installation-manifest.json"
    )
    manifest = decode_object(manifest_path.read_text())
    tool_dir = manifest.get("uv_tool_dir")
    bin_dir = manifest.get("uv_tool_bin_dir")
    if not isinstance(tool_dir, str) or not isinstance(bin_dir, str):
        raise TypeError("Installation manifest has no tool paths")
    os.environ["UV_TOOL_DIR"] = tool_dir
    os.environ["UV_TOOL_BIN_DIR"] = bin_dir
    environment = Path(tool_dir) / APP
    python = environment / "bin/python"
    state_path = manifest_path.parent / "native/removal-state.json"
    if state_path.is_file():
        prepared = decode_object(state_path.read_text())
    else:
        prepared = decode_object(
            await execute(
                [
                    str(python),
                    "-m",
                    "pdomain_ocr_simple_gui.uninstall_support",
                    "--prepare",
                    "--tool-dir",
                    tool_dir,
                    "--json",
                ],
                lambda _: None,
            )
        )
        save_removal_state(state_path, prepared)
    if prepared.get("prepared") is not True:
        raise ValueError("Removal could not be prepared")
    arguments = [prepared.get(key) for key in ("base_python", "finalize_script", "plan_path")]
    if not all(isinstance(value, str) and Path(value).is_absolute() for value in arguments):
        raise ValueError("Removal preparation returned invalid helper paths")
    base, helper, plan = (str(value) for value in arguments)
    if prepared.get("tool_removed") is not True or _entry_present(environment):
        if _entry_present(environment):
            _ = await execute([uv_executable(), "tool", "uninstall", APP], output)
        if _entry_present(environment):
            raise RuntimeError(
                "The tool environment remains after uv removal. Installation controls were kept for Retry."
            )
        prepared["tool_removed"] = True
        save_removal_state(state_path, prepared)
    _ = await execute([base, helper, "--execute-plan", plan, "--json"], lambda _: None)
    owned_paths = manifest.get("owned_paths", [])
    if not isinstance(owned_paths, list):
        raise TypeError("Invalid owned paths")
    for value in owned_paths:
        if isinstance(value, str):
            target = Path(value)
            if target in {
                Path.home() / "Applications/OCR Simple GUI.app",
                Path.home() / "Applications/Uninstall OCR Simple GUI.app",
            }:
                shutil.rmtree(target, ignore_errors=False) if target.exists() else None
            elif target == manifest_path.parent / "native/native.py" or (
                target.parent
                == Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share"))) / "applications"
                and target.name
                in {APP + ".desktop", APP + "-uninstall.desktop", "pdomain-" + APP + ".desktop"}
            ):
                target.unlink(missing_ok=True)
    state_path.unlink(missing_ok=True)
    manifest_path.unlink(missing_ok=True)
    output("OCR Simple GUI was removed. Your data and shared tools were retained.\n")


def linux_dialog(payload: Path, *, removing: bool, dry_run: bool) -> None:
    """Show confirmation, live progress, errors and retry in a native window."""
    import queue
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.title("Uninstall OCR Simple GUI" if removing else "Install OCR Simple GUI")
    root.minsize(480, 280)
    frame = ttk.Frame(root, padding=20)
    frame.pack(fill="both", expand=True)
    ttk.Label(
        frame,
        text="Remove this app and its shortcuts? Your data and shared tools will be kept."
        if removing
        else "Install OCR Simple GUI and its required Python packages for your user account?",
        wraplength=600,
    ).pack()
    buttons = ttk.Frame(frame)
    buttons.pack(side="bottom", fill="x")
    action = ttk.Button(buttons, text="Uninstall" if removing else "Install")
    action.pack(side="left")
    close = ttk.Button(buttons, text="Cancel", command=root.destroy)
    close.pack(side="right")
    text = tk.Text(frame, width=85, height=20, state="disabled")
    text.pack(fill="both", expand=True, pady=10)
    events: queue.Queue[tuple[str, str]] = queue.Queue()

    def work() -> None:
        try:
            if dry_run:
                events.put(
                    ("output", "Preview: " + " ".join(install_command(payload)) + "\nNo changes made.\n")
                )
            else:
                asyncio.run(
                    uninstall(lambda line: events.put(("output", line)))
                    if removing
                    else install(payload, lambda line: events.put(("output", line)))
                )
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            events.put(("error", str(exc)))
        else:
            events.put(("done", "Preview complete." if dry_run else "Complete."))

    def start() -> None:
        _ = action.configure(state="disabled")
        _ = close.configure(state="disabled")
        root.protocol("WM_DELETE_WINDOW", lambda: None)
        threading.Thread(target=work, daemon=True).start()

    def poll() -> None:
        while not events.empty():
            kind, message = events.get_nowait()
            _ = text.configure(state="normal")
            text.insert("end", message + ("\n" if kind != "output" else ""))
            text.see("end")
            _ = text.configure(state="disabled")
            if kind in {"done", "error"}:
                _ = close.configure(text="Close", state="normal")
                root.protocol("WM_DELETE_WINDOW", root.destroy)
                if kind == "error":
                    _ = action.configure(text="Retry", state="normal")
        _ = root.after(100, poll)

    _ = action.configure(command=start)
    poll()
    root.mainloop()


async def mac_dialog(payload: Path, *, removing: bool) -> None:
    """Use system dialogs without requiring Tk or a terminal on macOS."""
    action = "Uninstall" if removing else "Install"
    message = (
        "Remove OCR Simple GUI? Your data and shared tools will be kept."
        if removing
        else "Install OCR Simple GUI and required Python packages in your user account?"
    )
    while True:
        try:
            response = await execute(
                [
                    "/usr/bin/osascript",
                    "-e",
                    "display dialog "
                    + json.dumps(message)
                    + ' buttons {"Cancel", "'
                    + action
                    + '"} default button "'
                    + action
                    + '" cancel button "Cancel"',
                ],
                lambda _: None,
            )
        except NativeCommandError as exc:
            if exc.status == 1 and "(-128)" in exc.output:
                return
            raise
        if action not in response:
            return
        progress = await asyncio.create_subprocess_exec(
            "/usr/bin/osascript",
            "-e",
            'display dialog "Working. Installation or removal can take several minutes. This window closes when the operation finishes." buttons {} giving up after 86400',
        )
        try:
            await (uninstall(lambda _: None) if removing else install(payload, lambda _: None))
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            message = str(exc)[-5000:] + "\nRetry the operation?"
            action = "Retry"
        else:
            if progress.returncode is None:
                progress.terminate()
                _ = await progress.wait()
            _ = await execute(
                [
                    "/usr/bin/osascript",
                    "-e",
                    'display dialog "Operation complete." buttons {"OK"} default button "OK"',
                ],
                lambda _: None,
            )
            return
        finally:
            if progress.returncode is None:
                progress.terminate()
                _ = await progress.wait()


def main() -> None:
    """Start a native installer or removal dialog."""
    parser = argparse.ArgumentParser()
    _ = parser.add_argument("--uninstall", action="store_true")
    _ = parser.add_argument(
        "--payload",
        type=Path,
        default=Path(os.environ.get("PD_SIMPLE_GUI_INSTALL_ROOT", Path(__file__).resolve().parents[2])),
    )
    _ = parser.add_argument("--integrate-only", action="store_true")

    class Arguments(argparse.Namespace):
        payload: Path = Path()
        uninstall: bool = False
        integrate_only: bool = False

    args = parser.parse_args(namespace=Arguments())
    if args.integrate_only:
        asyncio.run(integrate(lambda _: None))
        return
    if sys.platform == "darwin":
        asyncio.run(mac_dialog(args.payload, removing=args.uninstall))
    else:
        linux_dialog(args.payload, removing=args.uninstall, dry_run=False)


if __name__ == "__main__":
    main()
