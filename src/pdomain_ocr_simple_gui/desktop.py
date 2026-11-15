"""Launch one desktop-managed backend or show its existing browser client."""

from __future__ import annotations

import http.client
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from contextlib import redirect_stderr, redirect_stdout
from typing import TYPE_CHECKING

from filelock import Timeout
from pydantic import TypeAdapter

from pdomain_ocr_simple_gui.instance import InstanceStore, new_instance_record, request_instance
from pdomain_ocr_simple_gui.ports import bind_listening_socket, resolve_start_port

if TYPE_CHECKING:
    from pathlib import Path

    from pdomain_ocr_simple_gui.instance import InstanceRecord

logger = logging.getLogger(__name__)


def wait_for_instance(store: InstanceStore, *, timeout: float = 15.0) -> InstanceRecord:
    """Wait for a lifetime-lock owner's authenticated server without replacing it."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            record = store.read()
            if record is not None:
                reply = request_instance(
                    record, "status", timeout=min(2.0, max(0.05, deadline - time.monotonic()))
                )
                if reply.accepted:
                    return record
        except (OSError, ValueError, http.client.HTTPException):
            if time.monotonic() >= deadline:
                break
        time.sleep(min(0.1, max(0.0, deadline - time.monotonic())))
    raise RuntimeError("The running app is unresponsive. No second backend was started.")


def show_existing(record: InstanceRecord) -> None:
    """Ask a live page to show itself, opening one browser fallback if needed."""
    reply = request_instance(record, "show")
    if not reply.accepted and not webbrowser.open(record.origin):
        raise RuntimeError("The browser could not open the running app")


def _open_when_ready(record: InstanceRecord) -> None:
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        try:
            reply = request_instance(record, "status")
            if reply.accepted:
                if not webbrowser.open(record.origin):
                    logger.error("The browser could not open %s", record.origin)
                return
        except (OSError, ValueError, http.client.HTTPException):
            time.sleep(0.25)
    logger.error("App startup did not finish before the browser-open deadline")


def serve_new_instance(store: InstanceStore) -> None:
    """Run one loopback backend while retaining its lifetime lock."""
    from pdomain_ocr_simple_gui.cache_configuration import apply_saved_model_cache_location

    apply_saved_model_cache_location()

    import uvicorn
    from pdomain_ops.suite import register_self
    from pdomain_ops.suite.prefs import LocalFilePrefs

    from pdomain_ocr_simple_gui.app import app
    from pdomain_ocr_simple_gui.app_preferences import AppPreferencesStore
    from pdomain_ocr_simple_gui.constants import APP_ID
    from pdomain_ocr_simple_gui.desktop_runtime import DesktopRuntime
    from pdomain_ocr_simple_gui.lifecycle import LifecycleController
    from pdomain_ocr_simple_gui.locations import get_locations

    sock = bind_listening_socket("127.0.0.1", resolve_start_port(None, os.environ))
    _, port = TypeAdapter(tuple[str, int]).validate_python(sock.getsockname())
    record = new_instance_record(f"http://127.0.0.1:{port}")
    published = False
    try:
        config = uvicorn.Config(
            app, host="127.0.0.1", access_log=False, ws_ping_interval=20, ws_ping_timeout=60
        )
        server = uvicorn.Server(config)

        def request_exit() -> None:
            server.should_exit = True

        legacy_preferences: dict[str, object] = dict(LocalFilePrefs().read().apps.get(APP_ID, {}))
        preferences = AppPreferencesStore(get_locations().preferences_path).read_app(legacy_preferences)
        controller = LifecycleController(
            record.instance_id,
            request_exit=request_exit,
            keep_running=preferences.get("keep_running") is True,
        )
        app.state.desktop_runtime = DesktopRuntime(record, controller)
        config.load()
        store.publish(record)
        published = True
        store.startup_lock.release()
        try:
            register_self(_caller_package="pdomain_ocr_simple_gui", actual_port=port)
        except Exception:
            logger.exception("Suite registration failed; app launch will continue")
        browser_thread = threading.Thread(target=_open_when_ready, args=(record,), daemon=True)
        browser_thread.start()
        server.run(sockets=[sock])
        if not server.started:
            raise RuntimeError("The app server could not start; see the launcher log")
    finally:
        sock.close()
        if published:
            _ = store.remove_owned(record)


def run_desktop(state_root: Path) -> None:
    """Serialize discovery and startup without killing an unresponsive owner."""
    store = InstanceStore(state_root)
    with store.startup_lock.acquire(timeout=30):
        marker = state_root / "uninstall-in-progress.json"
        if marker.exists() or marker.is_symlink():
            raise RuntimeError("An uninstall is incomplete. Use Uninstall to retry.")
        try:
            _ = store.lifetime_lock.acquire(timeout=0)
        except Timeout:
            show_existing(wait_for_instance(store))
            return
        try:
            serve_new_instance(store)
        finally:
            store.lifetime_lock.release()


def show_launch_error(message: str) -> None:
    """Report a launcher failure through the platform's graphical dialog."""
    environment = dict(os.environ)
    environment["PD_OCR_LAUNCH_ERROR"] = message
    flags = 0
    if sys.platform == "win32":
        name = "powershell.exe"
        flags = subprocess.CREATE_NO_WINDOW
        arguments = [
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "Add-Type -AssemblyName PresentationFramework;[System.Windows.MessageBox]::Show($env:PD_OCR_LAUNCH_ERROR, 'OCR Simple GUI', 'OK', 'Error')",
        ]
    elif sys.platform == "darwin":
        name = "osascript"
        arguments = [
            "-e",
            'on run argv\ndisplay alert "OCR Simple GUI" message (item 1 of argv) as critical\nend run',
            "--",
            message,
        ]
    elif shutil.which("zenity"):
        name = "zenity"
        arguments = ["--error", "--title=OCR Simple GUI", f"--text={message}"]
    elif shutil.which("kdialog"):
        name = "kdialog"
        arguments = ["--error", message, "--title", "OCR Simple GUI"]
    else:
        logger.error("Graphical error dialog unavailable: %s", message)
        return
    executable = shutil.which(name)
    if executable is None:
        logger.error("Graphical error dialog executable unavailable: %s", name)
        return
    try:
        _ = subprocess.run(  # noqa: S603 # Resolved OS dialog allowlist; message stays argv/env data, shell=False.
            [executable, *arguments],
            env=environment,
            check=False,
            timeout=120,
            creationflags=flags,
        )
    except (OSError, subprocess.TimeoutExpired):
        logger.exception("Could not display the launcher error dialog")


def main() -> None:
    """Start the app from a desktop icon without requiring a terminal."""
    from pdomain_ocr_simple_gui.locations import get_locations

    try:
        locations = get_locations()
        locations.state_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        log_path = locations.state_root / "launcher.log"
        if log_path.exists() and log_path.stat().st_size > 4 * 1024 * 1024:
            _ = log_path.replace(log_path.with_suffix(".previous.log"))
        descriptor = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(descriptor, "a", encoding="utf-8") as log, redirect_stdout(log), redirect_stderr(log):
            try:
                run_desktop(locations.state_root)
            except Exception:
                logger.exception("Desktop launch failed")
                raise
    except Exception as exc:
        show_launch_error(str(exc))
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
