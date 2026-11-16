"""Exercise the actual macOS installer, application and removal bundles."""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import shlex
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, final
from urllib.parse import urlsplit

from pdomain_ocr_simple_gui.instance import InstanceRecord, request_instance

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

JSONScalar = str | int | float | bool | None
JSONValue = JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]


class AcceptanceError(RuntimeError):
    """A required native observation failed or was unavailable."""


def read_object(path: Path) -> dict[str, JSONValue]:
    decoder: Callable[..., JSONValue] = json.loads
    value = decoder(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AcceptanceError(f"Expected an object in {path}")
    return value


def load_record(path: Path) -> InstanceRecord:
    return InstanceRecord.model_validate_json(path.read_text(encoding="utf-8"))


def command(argv: list[str], *, timeout: float = 30) -> str:
    completed = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
    output = completed.stdout + completed.stderr
    if completed.returncode:
        raise AcceptanceError(f"Command failed (exit {completed.returncode}): {output[-4000:]}")
    return output


def verify_open_environment_support() -> None:
    # open -h uses a nonzero exit status on some macOS versions.
    result = subprocess.run(["/usr/bin/open", "-h"], capture_output=True, text=True, check=False, timeout=10)
    if "--env" not in result.stdout + result.stderr:
        raise AcceptanceError("LaunchServices open lacks --env; cannot enforce isolated CPU acceptance")


def snapshot_files(roots: list[Path]) -> dict[str, str]:
    saved: dict[str, str] = {}
    for root in roots:
        for path in root.rglob("*"):
            if path.is_symlink():
                raise AcceptanceError(f"Unexpected symlink in test data: {path}")
            if path.is_file():
                saved[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return saved


def verify_retained(saved: Mapping[str, str]) -> None:
    for name, digest in saved.items():
        path = Path(name)
        if path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise AcceptanceError(f"Retained file missing or changed: {path}")


def run_ocr(repo: Path, output: Path, origin: str) -> dict[str, JSONValue]:
    target = output / "ocr"
    log = command(
        [
            sys.executable,
            str(repo / "scripts/windows_acceptance.py"),
            "--url",
            origin,
            "--headless",
            "--browser-channel",
            "chromium",
            "--fixtures",
            str(repo / "tests/e2e/fixtures/known_good_page.png"),
            "--out-dir",
            str(target),
        ],
        timeout=2400,
    )
    output.mkdir(parents=True, exist_ok=True)
    _ = (output / "ocr-driver.log").write_text(log, encoding="utf-8")
    result = target / "results.json"
    if not result.is_file():
        raise AcceptanceError("OCR acceptance result is missing; exit status alone is insufficient")
    data = read_object(result)
    if data.get("passed") is not True:
        raise AcceptanceError("OCR acceptance did not report PASS")
    return data


@dataclass(frozen=True)
class Configuration:
    repo: Path
    installer: Path
    work: Path
    output: Path
    home: Path = field(default_factory=Path.home)
    chrome: Path = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")

    @property
    def application(self) -> Path:
        return self.home / "Applications/OCR Simple GUI.app"

    @property
    def uninstaller(self) -> Path:
        return self.home / "Applications/Uninstall OCR Simple GUI.app"

    @property
    def tool(self) -> Path:
        return self.work / "tools/pdomain-ocr-simple-gui"

    @property
    def manifest(self) -> Path:
        return self.work / "xdg/data/pdomain-ocr-simple-gui/installation-manifest.json"

    @property
    def record(self) -> Path:
        return self.work / "state/instance.json"

    def check_fresh_installation(self) -> None:
        for path in (self.application, self.uninstaller, self.tool, self.manifest):
            if path.exists():
                raise AcceptanceError(f"Refusing native test: installation already exists at {path}")


@final
class NativeAcceptance:
    def __init__(self, config: Configuration) -> None:
        self.config = config
        self.checks: dict[str, JSONValue] = {}
        self.environment: dict[str, str] = {}
        self.record: InstanceRecord | None = None
        self.browser_port = 0

    def screenshot(self, name: str) -> None:
        try:
            _ = command(["/usr/sbin/screencapture", "-x", str(self.config.output / f"{name}.png")])
        except (OSError, subprocess.SubprocessError) as error:
            self.checks[f"screenshot_{name}"] = f"unavailable: {error}"

    def control(self, button: str, marker: str, *, timeout: int = 30) -> None:
        helper = str(self.config.repo / "scripts/macos_native_controls.applescript")
        _ = command(
            ["/usr/bin/osascript", helper, "wait", button, marker, str(timeout)], timeout=timeout + 10
        )
        self.screenshot(button.lower())
        _ = command(["/usr/bin/osascript", helper, "click", button, marker, "5"], timeout=15)

    def open_bundle(self, bundle: Path) -> None:
        argv = ["/usr/bin/open", "-n"]
        for name, value in self.environment.items():
            argv.extend(["--env", f"{name}={value}"])
        _ = command([*argv, str(bundle)], timeout=30)

    def prepare(self) -> None:
        if sys.platform != "darwin":
            raise AcceptanceError("Native macOS acceptance must run on macOS")
        self.config.check_fresh_installation()
        if not self.config.installer.is_dir() or not self.config.chrome.is_file():
            raise AcceptanceError("The installer bundle and Google Chrome must both exist")
        if self.config.work.exists() and any(self.config.work.iterdir()):
            raise AcceptanceError("Native test work directory must be empty")
        verify_open_environment_support()
        helper = str(self.config.repo / "scripts/macos_native_controls.applescript")
        _ = command(["/usr/bin/osascript", helper, "preflight"], timeout=15)
        self.checks["native_gui_preflight"] = True
        self.config.work.mkdir(parents=True, exist_ok=True)
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            get_address: Callable[[], tuple[str, int]] = listener.getsockname
            self.browser_port = get_address()[1]
        browser = self.config.work / "browser"
        _ = browser.write_text(
            "#!/bin/sh\nset -eu\nexec "
            + shlex.join(
                [
                    str(self.config.chrome),
                    f"--user-data-dir={self.config.work / 'chrome-profile'}",
                    f"--remote-debugging-port={self.browser_port}",
                    "--no-first-run",
                    "--no-default-browser-check",
                ]
            )
            + ' "$@"\n',
            encoding="utf-8",
        )
        browser.chmod(0o755)
        self.environment = {
            "UV_TOOL_DIR": str(self.config.work / "tools"),
            "UV_TOOL_BIN_DIR": str(self.config.work / "bin"),
            "XDG_DATA_HOME": str(self.config.work / "xdg/data"),
            "XDG_CONFIG_HOME": str(self.config.work / "xdg/config"),
            "XDG_CACHE_HOME": str(self.config.work / "xdg/cache"),
            "PD_OCR_SIMPLE_GUI_CONFIG_ROOT": str(self.config.work / "config"),
            "PD_OCR_SIMPLE_GUI_DATA_ROOT": str(self.config.work / "data"),
            "PD_OCR_SIMPLE_GUI_STATE_ROOT": str(self.config.work / "state"),
            "PD_OCR_SIMPLE_GUI_CACHE_ROOT": str(self.config.work / "cache"),
            "PD_SUITE_DATA_DIR": str(self.config.work / "suite"),
            "PDOMAIN_GPU_BACKEND": "cpu",
            "PDOMAIN_OCR_FAKE_DISPATCHER": "",
            "PDOMAIN_API_TOKEN": "",
            "OMP_NUM_THREADS": "2",
            "OPENBLAS_NUM_THREADS": "2",
            "MKL_NUM_THREADS": "2",
            "DOCTR_CACHE_DIR": str(self.config.work / "models/doctr"),
            "HF_HOME": str(self.config.work / "models/huggingface"),
            "TORCH_HOME": str(self.config.work / "models/torch"),
            "BROWSER": str(browser),
            "PATH": os.environ["PATH"],
            "UV_NO_MODIFY_PATH": "1",
        }

    def install(self) -> None:
        self.open_bundle(self.config.installer)
        self.control("Cancel", "Install OCR Simple GUI and required Python packages")
        time.sleep(1)
        self.config.check_fresh_installation()
        self.checks["native_install_cancel"] = True
        self.open_bundle(self.config.installer)
        self.control("Continue", "Install OCR Simple GUI and required Python packages")
        self.control("OK", "Installation complete.", timeout=1800)
        manifest = read_object(self.config.manifest)
        if manifest.get("uv_tool_dir") != str(self.config.work / "tools"):
            raise AcceptanceError("Installer used an unexpected tool directory")
        for path in (self.config.application, self.config.uninstaller, self.config.tool / "bin/python"):
            if not path.exists():
                raise AcceptanceError(f"Installed native control is missing: {path}")
        self.checks["native_gui_install"] = True

    def wait_for_backend(self) -> InstanceRecord:
        deadline = time.monotonic() + 240
        while time.monotonic() < deadline:
            try:
                record = load_record(self.config.record)
                _ = request_instance(record, "status")
            except (OSError, ValueError):
                time.sleep(0.2)
            else:
                self.record = record
                return record
        raise AcceptanceError("Installed application did not publish a verified ready backend")

    def verify_cpu(self, record: InstanceRecord) -> None:
        parsed = urlsplit(record.origin)
        if parsed.hostname is None:
            raise AcceptanceError("Missing instance host")
        connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=30)
        try:
            connection.request("GET", "/api/config")
            response = connection.getresponse()
            decoder: Callable[..., JSONValue] = json.loads
            value = decoder(response.read())
            if response.status != 200 or not isinstance(value, dict) or value.get("detected_device") != "cpu":
                raise AcceptanceError("Native app did not select CPU; OCR will not run")
        finally:
            connection.close()
        self.checks["native_cpu_selected"] = True

    def lifecycle(self, record: InstanceRecord) -> None:
        from playwright.sync_api import sync_playwright

        def tabs(expected: int) -> None:
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                if request_instance(record, "status").live_tabs == expected:
                    return
                time.sleep(0.1)
            raise AcceptanceError(f"Expected {expected} native browser leases")

        with sync_playwright() as playwright:
            browser = playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{self.browser_port}")
            context = browser.contexts[0]
            owned = [page for page in context.pages if page.url.startswith(record.origin)]
            if len(owned) != 1:
                raise AcceptanceError("Expected one app page in the private native browser")
            first = owned[0]
            second = context.new_page()
            _ = second.goto(record.origin)
            tabs(2)
            _ = second.reload()
            tabs(2)
            first.close()
            tabs(1)
            self.checks["two_tabs_refresh_close_one"] = True
            self.open_bundle(self.config.application)
            time.sleep(4)
            current = load_record(self.config.record)
            if current.pid != record.pid or current.instance_id != record.instance_id:
                raise AcceptanceError("Second native launch created another backend")
            self.checks["native_relaunch_same_backend"] = True
            pages = [page for page in context.pages if page.url.startswith(record.origin)]
            self.checks["native_relaunch_app_tab_count"] = len(pages)
            # Focus restrictions may produce a new fallback tab. Both outcomes are valid.
            fixture = (self.config.repo / "tests/e2e/fixtures/known_good_page.png").read_bytes()
            boundary = "native-macos-owned-upload"
            body = (
                f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="retained-page.png"\r\nContent-Type: image/png\r\n\r\n'.encode()
                + fixture
                + f"\r\n--{boundary}--\r\n".encode()
            )
            parsed = urlsplit(record.origin)
            if parsed.hostname is None:
                raise AcceptanceError("Missing instance host")
            connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=20)
            try:
                connection.putrequest("POST", "/api/uploads")
                connection.putheader("Content-Type", f"multipart/form-data; boundary={boundary}")
                connection.putheader("Content-Length", str(len(body)))
                connection.endheaders()
                split = len(body) // 2
                connection.send(body[:split])
                deadline = time.monotonic() + 10
                while request_instance(record, "status").active_operations < 1:
                    if time.monotonic() > deadline:
                        raise AcceptanceError("Upload activity was not reserved")
                    time.sleep(0.1)
                for page in pages:
                    page.close()
                tabs(0)
                start = time.monotonic()
                while time.monotonic() - start < 35:
                    state = request_instance(record, "status")
                    if state.live_tabs or not state.active_operations:
                        raise AcceptanceError("Last-tab shutdown did not preserve the active upload")
                    time.sleep(1)
                connection.send(body[split:])
                response = connection.getresponse()
                if response.status != 200:
                    raise AcceptanceError("Protected upload failed to complete")
                _ = response.read()
            finally:
                connection.close()
            deadline = time.monotonic() + 40
            while self.config.record.exists() and time.monotonic() < deadline:
                time.sleep(0.1)
            if self.config.record.exists():
                raise AcceptanceError("Native backend did not exit after the protected upload finished")
            self.checks["last_tab_upload_deferral_seconds"] = round(time.monotonic() - start, 2)
            # The private Chrome was started solely for this test.
            browser.close()
        self.record = None

    def wait_until_idle(self) -> None:
        """Wait until the open app has no API work. Uninstall refuses while any is active."""
        if self.record is None:
            raise AcceptanceError("No running app to check before uninstall")
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            try:
                status = request_instance(self.record, "status", timeout=5)
            except (OSError, ValueError):
                time.sleep(0.5)
                continue
            if status.accepted and status.active_operations == 0:
                return
            time.sleep(0.5)
        raise AcceptanceError("App still had an active operation when uninstall started")

    def uninstall(self) -> None:
        saved = snapshot_files([self.config.work / "data", self.config.work / "config"])
        model_sizes = {
            str(path): path.stat().st_size
            for path in (self.config.work / "models").rglob("*")
            if path.is_file()
        }
        interpreter = (self.config.tool / "bin/python").resolve()
        uv = shutil.which("uv")
        if uv is None:
            raise AcceptanceError("Shared uv was not found before removal")
        self.open_bundle(self.config.application)
        self.record = self.wait_for_backend()
        self.open_bundle(self.config.uninstaller)
        self.control("Cancel", "Remove OCR Simple GUI?")
        if not self.config.tool.is_dir() or not self.config.manifest.is_file():
            raise AcceptanceError("Cancelled native removal changed the installation")
        self.checks["native_uninstall_cancel"] = True
        self.wait_until_idle()
        self.open_bundle(self.config.uninstaller)
        self.control("Uninstall", "Remove OCR Simple GUI?")
        self.control("OK", "Operation complete.", timeout=180)
        verify_retained(saved)
        for path in (
            self.config.tool,
            self.config.manifest,
            self.config.application,
            self.config.uninstaller,
        ):
            if path.exists():
                raise AcceptanceError(f"Native removal left an owned control: {path}")
        if self.config.record.exists() or not interpreter.is_file() or not Path(uv).is_file():
            raise AcceptanceError("Removal did not stop the backend or retain shared runtimes")
        self.checks["native_gui_uninstall"] = True
        self.checks["retained_files_identical"] = len(saved)
        self.checks["shared_uv_and_python_retained"] = True
        for name, size in model_sizes.items():
            model = Path(name)
            if not model.is_file() or model.stat().st_size != size:
                raise AcceptanceError(f"Retained model cache is missing or changed size: {model}")
        self.checks["retained_model_files_same_size"] = len(model_sizes)
        if (self.config.work / "suite/installed.toml").exists():
            raise AcceptanceError("The known last-app suite registry remains after removal")
        self.checks["known_last_app_suite_registry_removed"] = True
        self.record = None

    def cleanup(self) -> None:
        # Never terminate an installer or kill an arbitrary PID on failure.
        if self.record is not None:
            try:
                result = request_instance(self.record, "quit", confirm_other_tabs=True)
                self.checks["failure_cleanup_graceful_quit"] = result.accepted
            except (OSError, ValueError) as error:
                self.checks["failure_cleanup_graceful_quit"] = str(error)
        launcher_log = self.config.work / "state/launcher.log"
        if launcher_log.is_file():
            _ = shutil.copyfile(launcher_log, self.config.output / "launcher.log")

    def run(self) -> None:
        self.config.output.mkdir(parents=True, exist_ok=True)
        passed = False
        error_message: str | None = None
        try:
            self.prepare()
            self.install()
            self.open_bundle(self.config.application)
            record = self.wait_for_backend()
            self.checks["native_bundle_launch"] = True
            self.verify_cpu(record)
            self.checks["real_cpu_ocr"] = run_ocr(self.config.repo, self.config.output, record.origin)
            self.lifecycle(record)
            self.uninstall()
            passed = True
        except Exception as error:
            error_message = str(error)
            self.screenshot("failure")
            raise
        finally:
            self.cleanup()
            _ = (self.config.output / "results.json").write_text(
                json.dumps({"passed": passed, "error": error_message, "checks": self.checks}, indent=2)
                + "\n",
                encoding="utf-8",
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--installer", type=Path, required=True)
    _ = parser.add_argument("--work-dir", type=Path, required=True)
    _ = parser.add_argument("--out-dir", type=Path, default=Path("acceptance-out/native"))

    class Arguments(argparse.Namespace):
        installer: Path = Path()
        work_dir: Path = Path()
        out_dir: Path = Path()

    args = parser.parse_args(namespace=Arguments())
    config = Configuration(
        repo=Path(__file__).resolve().parents[1],
        installer=Path(args.installer).resolve(),
        work=Path(args.work_dir).resolve(),
        output=Path(args.out_dir).resolve(),
    )
    NativeAcceptance(config).run()


if __name__ == "__main__":
    main()
