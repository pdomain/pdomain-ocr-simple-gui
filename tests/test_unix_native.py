from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

from installer.install_engine import GPU_SETUP_GUIDE_URL as ENGINE_GUIDE_URL
from installer.unix.native import (
    GPU_SETUP_GUIDE_URL,
    install_command,
    install_entries,
    open_gpu_setup_guide,
)


def test_open_gpu_setup_guide_uses_the_published_page(monkeypatch: pytest.MonkeyPatch) -> None:
    opened: list[str] = []

    def _open(url: str) -> bool:
        opened.append(url)
        return True

    monkeypatch.setattr("installer.unix.native.webbrowser.open", _open)
    open_gpu_setup_guide()
    assert GPU_SETUP_GUIDE_URL == ENGINE_GUIDE_URL
    assert opened == [GPU_SETUP_GUIDE_URL]


def test_desktop_installers_name_the_gpu_guide() -> None:
    root = Path(__file__).resolve().parents[1]
    native = (root / "installer/unix/native.py").read_text(encoding="utf-8")
    windows = (root / "installer/windows/Bootstrapper.cs").read_text(encoding="utf-8")
    applescript = (root / "installer/macos/dialog.applescript").read_text(encoding="utf-8")
    mac_install = (root / "installer/macos/install-native.sh").read_text(encoding="utf-8")
    assert "GPU setup guide" in native
    assert "GPU guide" in native
    assert "from installer.install_engine import" not in native
    assert GPU_SETUP_GUIDE_URL in native
    assert "GPU setup guide" in windows
    assert GPU_SETUP_GUIDE_URL in windows
    assert '{"Cancel", "GPU guide", "Continue"}' in applescript
    assert "buttons {}" not in native
    assert "buttons {}" not in applescript
    assert "You can close this window" in native
    controls = (root / "scripts/macos_native_controls.applescript").read_text(encoding="utf-8")
    assert "unix id of every application process whose name is" in controls
    assert "repeat with candidate in (application processes whose name is" not in controls
    assert "button returned:GPU guide" in mac_install
    assert GPU_SETUP_GUIDE_URL in mac_install
    assert "does not install an NVIDIA driver" in mac_install
    build = (root / "installer/macos/build.sh").read_text(encoding="utf-8")
    install_sh = (root / "install.sh").read_text(encoding="utf-8")
    for script in (mac_install, build, install_sh):
        assert "sysctl.proc_translated" in script
        assert "/usr/bin/arch -arm64 /bin/sh" in script


def test_payload_copy_runs_without_the_installer_package(tmp_path: Path) -> None:
    script = tmp_path / "native.py"
    source = Path(__file__).resolve().parents[1] / "installer/unix/native.py"
    _ = script.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-I", str(script), "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "integrate-only" in result.stdout


def test_install_command_uses_payload_script(tmp_path: Path) -> None:
    assert install_command(tmp_path) == ["/bin/sh", str(tmp_path / "install.sh"), "--no-appimage", "-y"]


def test_entries_reject_missing_desktop_command(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        _ = install_entries(tmp_path, tmp_path / "missing", tmp_path / "native.py")
    assert not (tmp_path / ".local/share/applications").exists()


def test_entries_use_verified_gui_command_and_native_uninstall(tmp_path: Path) -> None:
    command = tmp_path / "tool bin" / "pdomain-ocr-simple-gui-desktop"
    command.parent.mkdir()
    _ = command.write_text("#!/bin/sh\nexit 0\n")
    command.chmod(0o755)
    wrapper = tmp_path / "native.py"
    _ = wrapper.write_text('print("test")\n')
    entries = install_entries(tmp_path, command, wrapper)
    assert len(entries) == 2
    launch = entries[0].read_text()
    assert "Terminal=false" in launch
    assert str(command) in launch
    assert "--uninstall" in entries[1].read_text()


def test_macos_builder_makes_native_bundle_without_host_python(tmp_path: Path) -> None:
    import plistlib
    import subprocess

    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        ["/bin/sh", str(root / "installer/macos/build.sh"), str(tmp_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    bundle = Path(result.stdout.strip())
    read_plist: Callable[..., dict[str, object]] = plistlib.load
    with (bundle / "Contents/Info.plist").open("rb") as stream:
        info = read_plist(stream)
    assert info["CFBundleExecutable"] == "launch"
    payload = bundle / "Contents/Resources/payload"
    assert (payload / "install.sh").is_file()
    assert (payload / "native.py").is_file()
    assert "/usr/bin/osascript" in (payload / "install-native.sh").read_text()


@pytest.mark.parametrize("shell", ["dash", "bash"])
def test_local_wheel_skips_network_release_resolution(tmp_path: Path, shell: str) -> None:
    import os
    import shlex
    import shutil
    import subprocess

    interpreter = shutil.which(shell)
    if interpreter is None:
        pytest.skip(f"{shell} is unavailable")
    binaries = tmp_path / "bin"
    binaries.mkdir()
    wheel = tmp_path / "pdomain_ocr_simple_gui-1.0-py3-none-any.whl"
    _ = wheel.write_bytes(b"proof wheel")
    log = tmp_path / "uv.log"
    commands = {
        "uv": '#!/bin/sh\nif [ "$1" = --version ]; then echo "uv 0.11.16"; exit; fi\nprintf "%s\\n" "$@" > '
        + shlex.quote(str(log))
        + "\n",
        "curl": '#!/bin/sh\necho "network must not be used" >&2\nexit 97\n',
        "gh": '#!/bin/sh\necho "release lookup must not be used" >&2\nexit 97\n',
        "nvidia-smi": '#!/bin/sh\nprintf "CUDA Version: 13.1\\n"\n',
    }
    for name, source in commands.items():
        path = binaries / name
        _ = path.write_text(source)
        path.chmod(0o755)
    env = {
        **os.environ,
        "PATH": str(binaries) + os.pathsep + os.environ["PATH"],
        "PD_SIMPLE_GUI_INSTALL_WHEEL": str(wheel),
        "HOME": str(tmp_path),
    }
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [interpreter, str(root / "install.sh"), "--no-appimage", "-y"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    arguments = log.read_text()
    assert "pdomain-book-tools[gpu]" not in arguments
    assert "--with" not in arguments
    assert "--torch-backend\nauto" in arguments
    assert wheel.name in arguments


@pytest.mark.asyncio
async def test_install_missing_launcher_never_publishes_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer.unix import native

    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setattr(native, "uv_executable", lambda: "/fake/uv")

    async def execute(command: list[str], output: Callable[[str], None]) -> str:
        del output
        if command[-1] == "--bin":
            return str(tmp_path / "bin")
        return str(tmp_path / "tools")

    monkeypatch.setattr(native, "execute", execute)
    output: list[str] = []
    with pytest.raises(FileNotFoundError, match="no desktop launcher"):
        await native.install(tmp_path, output.append)
    assert not (tmp_path / "data/applications").exists()
    assert not any("complete" in line for line in output)


@pytest.mark.asyncio
async def test_uninstall_retries_finalization_after_tool_was_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    from installer.unix import native

    data = tmp_path / "data"
    owned = data / native.APP
    wrapper = owned / "native/native.py"
    wrapper.parent.mkdir(parents=True)
    _ = wrapper.write_text("wrapper")
    sentinel = owned / "jobs/document.txt"
    sentinel.parent.mkdir()
    _ = sentinel.write_text("retained OCR")
    manifest = owned / "installation-manifest.json"
    tool_root = tmp_path / "tools"
    environment = tool_root / native.APP
    environment.mkdir(parents=True)
    _ = manifest.write_text(
        json.dumps(
            {
                "uv_tool_dir": str(tool_root),
                "uv_tool_bin_dir": str(tmp_path / "bin"),
                "owned_paths": [str(wrapper)],
            }
        )
    )
    monkeypatch.setenv("XDG_DATA_HOME", str(data))
    monkeypatch.setenv("UV_TOOL_DIR", str(tool_root))
    monkeypatch.setenv("UV_TOOL_BIN_DIR", str(tmp_path / "bin"))
    monkeypatch.setattr(native, "uv_executable", lambda: "/fake/uv")
    commands: list[list[str]] = []
    fail_finalize = True

    async def execute(command: list[str], output: Callable[[str], None]) -> str:
        commands.append(command)
        if "--prepare" in command:
            return json.dumps(
                {
                    "prepared": True,
                    "base_python": "/base/python",
                    "finalize_script": "/private/finalize.py",
                    "plan_path": "/private/plan.json",
                }
            )
        if "uninstall" in command:
            shutil.rmtree(environment)
        if "--execute-plan" in command and fail_finalize:
            raise RuntimeError("finalize failed")
        if "--execute-plan" in command:
            output('{"operation_token":"private-finalization-token"}')
        return "{}"

    monkeypatch.setattr(native, "execute", execute)
    with pytest.raises(RuntimeError, match="finalize failed"):
        await native.uninstall(lambda _: None)
    assert manifest.exists()
    assert wrapper.exists()
    fail_finalize = False
    messages: list[str] = []
    await native.uninstall(messages.append)
    assert not any("private-finalization-token" in message for message in messages)
    assert sum("--prepare" in command for command in commands) == 1
    assert sum("uninstall" in command for command in commands) == 1
    assert not wrapper.exists()
    assert not manifest.exists()
    assert sentinel.read_text() == "retained OCR"


@pytest.mark.parametrize("custom", [False, True])
def test_only_verified_legacy_shortcut_is_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, custom: bool
) -> None:
    import shlex

    from installer.unix import native

    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    command = tmp_path / "bin/pdomain-ocr-simple-gui-desktop"
    command.parent.mkdir()
    _ = command.write_text("#!/bin/sh\nexit 0\n")
    command.chmod(0o755)
    console = command.parent / native.APP
    _ = console.write_text("#!/bin/sh\nexit 0\n")
    directory = tmp_path / "data/applications"
    directory.mkdir(parents=True)
    legacy = directory / ("pdomain-" + native.APP + ".desktop")
    content = "\n".join(
        [
            "[Desktop Entry]",
            "Version=1.0",
            "Type=Application",
            "Name=Simple OCR",
            "Exec=" + shlex.quote(str(console.resolve())),
            "Icon=" + native.APP,
            "Terminal=false",
            "Categories=Utility;",
            "",
        ]
    )
    if custom:
        content += "X-Owner-Custom=true\n"
    _ = legacy.write_text(content)
    reports: list[str] = []
    entries = native.install_entries(tmp_path, command, tmp_path / "native.py", reports.append)
    assert legacy.exists() is custom
    assert (legacy in entries) is not custom
    assert bool(reports) is custom


@pytest.mark.asyncio
async def test_macos_cancel_returns_without_mutation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from installer.unix import native

    calls: list[list[str]] = []

    async def cancelled(command: list[str], output: Callable[[str], None]) -> str:
        del output
        calls.append(command)
        raise native.NativeCommandError(1, "execution error: User canceled. (-128)")

    monkeypatch.setattr(native, "execute", cancelled)
    await native.mac_dialog(tmp_path, removing=True)
    assert len(calls) == 1
    assert not list(tmp_path.iterdir())


@pytest.mark.asyncio
async def test_macos_install_retry_keeps_the_gpu_guide_button(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer.unix import native

    calls: list[list[str]] = []
    answers = iter(["button returned:Install", "button returned:Cancel"])

    async def fake_execute(command: list[str], output: Callable[[str], None]) -> str:
        del output
        calls.append(command)
        if command[0] == "/usr/bin/open":
            return ""
        return next(answers)

    class FakeProgress:
        returncode: int | None = None

        def terminate(self) -> None:
            self.returncode = -15

        async def wait(self) -> int:
            self.returncode = -15
            return -15

    async def fake_spawn(*_args: object, **_kwargs: object) -> FakeProgress:
        return FakeProgress()

    async def fail_install(payload: Path, output: Callable[[str], None]) -> None:
        del payload, output
        raise RuntimeError("disk full")

    monkeypatch.setattr(native, "execute", fake_execute)
    monkeypatch.setattr(native.asyncio, "create_subprocess_exec", fake_spawn)
    monkeypatch.setattr(native, "install", fail_install)
    await native.mac_dialog(tmp_path, removing=False)

    scripts = [command[2] for command in calls if command[0] == "/usr/bin/osascript"]
    assert len(scripts) == 2
    assert 'buttons {"Cancel", "GPU guide", "Install"}' in scripts[0]
    assert 'default button "Install"' in scripts[0]
    assert 'buttons {"Cancel", "GPU guide", "Retry"}' in scripts[1]
    assert 'default button "Retry"' in scripts[1]


@pytest.mark.asyncio
async def test_macos_gpu_guide_opens_the_page_and_asks_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer.unix import native

    calls: list[list[str]] = []
    answers = iter(["button returned:GPU guide", "button returned:Cancel"])

    async def fake_execute(command: list[str], output: Callable[[str], None]) -> str:
        del output
        calls.append(command)
        if command[0] == "/usr/bin/open":
            return ""
        return next(answers)

    monkeypatch.setattr(native, "execute", fake_execute)
    await native.mac_dialog(tmp_path, removing=False)
    assert calls[1] == ["/usr/bin/open", GPU_SETUP_GUIDE_URL]
    assert len([command for command in calls if command[0] == "/usr/bin/osascript"]) == 2


@pytest.mark.parametrize("platform", ["linux", "darwin"])
def test_uninstall_entry_runs_after_tool_python_disappears(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, platform: str
) -> None:
    import shlex
    import shutil
    import subprocess
    import sys

    from installer.unix import native

    retained = str(Path(getattr(sys, "_base_executable", sys.executable)).resolve())
    tool = tmp_path / "tools/pdomain-ocr-simple-gui"
    command = tool / "bin/pdomain-ocr-simple-gui-desktop"
    command.parent.mkdir(parents=True)
    _ = command.write_text("#!/bin/sh\nexit 0\n")
    command.chmod(0o755)
    tool_python = tool / "bin/python"
    tool_python.symlink_to(retained)
    marker = tmp_path / "retried"
    wrapper = tmp_path / "native.py"
    _ = wrapper.write_text(
        "from pathlib import Path\nPath(" + repr(str(marker)) + ').write_text("retry works")\n'
    )
    with monkeypatch.context() as patch:
        patch.setattr(sys, "platform", platform)
        patch.setattr(sys, "executable", str(tool_python))
        patch.setattr(sys, "prefix", str(tool))
        patch.setattr(sys, "_base_executable", retained)
        patch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
        entries = native.install_entries(tmp_path, command, wrapper)
    removal = entries[1]
    if platform == "darwin":
        launcher = ["/bin/sh", str(removal / "Contents/MacOS/launch")]
        launch_script = (removal / "Contents/MacOS/launch").read_text()
        assert retained in launch_script
        assert "sysctl.proc_translated" in launch_script
        assert "/usr/bin/arch -arm64 /bin/sh" in launch_script
    else:
        launcher = shlex.split(
            next(line[5:] for line in removal.read_text().splitlines() if line.startswith("Exec="))
        )
        assert launcher[0] == retained
    shutil.rmtree(tool)
    _ = subprocess.run(launcher, check=True, capture_output=True)
    assert marker.read_text() == "retry works"


@pytest.mark.asyncio
async def test_macos_confirmation_errors_are_not_treated_as_cancel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer.unix import native

    async def failed(command: list[str], output: Callable[[str], None]) -> str:
        del command, output
        raise native.NativeCommandError(1, "Not authorized to send Apple events. (-1743)")

    monkeypatch.setattr(native, "execute", failed)
    with pytest.raises(native.NativeCommandError, match="-1743"):
        await native.mac_dialog(tmp_path, removing=True)


def test_uninstall_launcher_rejects_interpreter_inside_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sys

    from installer.unix import native

    interpreter = tmp_path / "tool/bin/python"
    interpreter.parent.mkdir(parents=True)
    _ = interpreter.write_text("#!/bin/sh\nexit 0\n")
    interpreter.chmod(0o755)
    monkeypatch.setattr(sys, "_base_executable", str(interpreter))
    monkeypatch.setattr(sys, "prefix", str(tmp_path / "tool"))
    with pytest.raises(ValueError, match="outside the removable tool environment"):
        _ = native.retained_base_python()


def test_apprun_rejects_unsupported_python_before_import(tmp_path: Path) -> None:
    import os
    import subprocess

    binaries = tmp_path / "bin"
    binaries.mkdir()
    python = binaries / "python3"
    _ = python.write_text("#!/bin/sh\nexit 1\n")
    python.chmod(0o755)
    notify = binaries / "notify-send"
    _ = notify.write_text("#!/bin/sh\nexit 0\n")
    notify.chmod(0o755)
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        ["bash", str(root / "installer/appimage/AppRun"), "--cli", "--dry-run"],
        env={**os.environ, "APPDIR": str(tmp_path), "PATH": str(binaries) + os.pathsep + os.environ["PATH"]},
        text=True,
        capture_output=True,
    )
    assert result.returncode == 1
    assert "Python 3.10+" in result.stderr


def _missing_uv(_command: str) -> None:
    return None


@pytest.mark.parametrize(
    "setting", ["UV_UNMANAGED_INSTALL", "UV_INSTALL_DIR", "XDG_BIN_HOME", "XDG_DATA_HOME"]
)
def test_uv_executable_finds_bootstrap_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, setting: str
) -> None:
    from installer.unix import native

    for key in ("UV_UNMANAGED_INSTALL", "UV_INSTALL_DIR", "XDG_BIN_HOME", "XDG_DATA_HOME"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(shutil, "which", _missing_uv)
    selected = tmp_path / "custom location"
    selected.mkdir()
    monkeypatch.setenv(setting, str(selected))
    executable = (selected / "../bin/uv") if setting == "XDG_DATA_HOME" else selected / "uv"
    executable.parent.mkdir(exist_ok=True)
    _ = executable.write_text("#!/bin/sh\nexit 0\n")
    executable.chmod(0o755)
    assert Path(native.uv_executable()).resolve() == executable.resolve()


def test_uv_executable_does_not_accept_nonexecutable_bootstrap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from installer.unix import native

    monkeypatch.setattr(shutil, "which", _missing_uv)
    monkeypatch.delenv("UV_UNMANAGED_INSTALL", raising=False)
    monkeypatch.setenv("UV_INSTALL_DIR", str(tmp_path))
    _ = (tmp_path / "uv").write_text("not executable")
    with pytest.raises(FileNotFoundError):
        _ = native.uv_executable()


@pytest.mark.asyncio
@pytest.mark.parametrize("dangling", [False, True])
async def test_uninstall_keeps_controls_when_uv_reports_success_but_tool_remains(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, dangling: bool
) -> None:
    import json

    from installer.unix import native

    data = tmp_path / "data"
    owned = data / native.APP
    wrapper = owned / "native/native.py"
    wrapper.parent.mkdir(parents=True)
    _ = wrapper.write_text("owned wrapper")
    tools = tmp_path / "tools"
    environment = tools / native.APP
    tools.mkdir()
    if dangling:
        environment.symlink_to(tmp_path / "absent-target", target_is_directory=True)
    else:
        environment.mkdir()
    manifest = owned / "installation-manifest.json"
    _ = manifest.write_text(
        json.dumps(
            {
                "uv_tool_dir": str(tools),
                "uv_tool_bin_dir": str(tmp_path / "bin"),
                "owned_paths": [str(wrapper)],
            }
        )
    )
    monkeypatch.setenv("XDG_DATA_HOME", str(data))
    monkeypatch.setattr(native, "uv_executable", lambda: "/fake/uv")
    finalized = False

    async def execute(command: list[str], output: Callable[[str], None]) -> str:
        nonlocal finalized
        del output
        if "--prepare" in command:
            return json.dumps(
                {
                    "prepared": True,
                    "base_python": "/base/python",
                    "finalize_script": "/private/helper.py",
                    "plan_path": "/private/plan.json",
                }
            )
        if "--execute-plan" in command:
            finalized = True
        return "{}"

    monkeypatch.setattr(native, "execute", execute)
    with pytest.raises(RuntimeError, match="tool environment"):
        await native.uninstall(lambda _: None)
    assert environment.is_symlink() if dangling else environment.is_dir()
    assert manifest.is_file()
    assert wrapper.is_file()
    assert not finalized
    saved = native.decode_object((owned / "native/removal-state.json").read_text())
    assert saved.get("tool_removed") is not True


@pytest.mark.parametrize("fault", ["fsync", "replace"])
def test_removal_state_interruption_keeps_previous_recovery_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    from installer.unix import native

    path = tmp_path / "removal-state.json"
    previous = '{"prepared": true, "plan_path": "/retained/plan.json"}'
    _ = path.write_text(previous)

    def interrupt(*_arguments: object) -> None:
        raise OSError("interrupted state publication")

    monkeypatch.setattr(os, fault, interrupt)
    with pytest.raises(OSError, match="interrupted state publication"):
        native.save_removal_state(path, {"prepared": True, "tool_removed": True})
    assert path.read_text() == previous
    assert not tuple(tmp_path.glob(".removal-state.json.*"))
