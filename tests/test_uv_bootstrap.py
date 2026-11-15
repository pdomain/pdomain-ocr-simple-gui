from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

INSTALL_SH = Path(__file__).resolve().parents[1] / "install.sh"


def _bootstrap_environment(tmp_path: Path) -> dict[str, str]:
    commands = tmp_path / "commands"
    commands.mkdir()
    for name in ("sh", "cat", "mkdir", "mktemp", "rm", "touch", "chmod", "dirname", "tail"):
        executable = shutil.which(name)
        assert executable is not None
        (commands / name).symlink_to(executable)
    bootstrap = tmp_path / "fake-installer.sh"
    _ = bootstrap.write_text(
        "\n".join(
            [
                "#!/bin/sh",
                "set -eu",
                'printf "%s" "${UV_NO_MODIFY_PATH:-}" > "$BOOTSTRAP_CALLED"',
                '_target="${UV_UNMANAGED_INSTALL:-$UV_INSTALL_DIR}"',
                'mkdir -p "$_target"',
                'if [ "$BOOTSTRAP_MODE" = failure ]; then exit 19; fi',
                'if [ "$BOOTSTRAP_MODE" = missing ]; then exit 0; fi',
                "cat > \"$_target/uv\" <<'UV'",
                "#!/bin/sh",
                "printf 'uv 0.13.8\\n'",
                'if [ "$BOOTSTRAP_MODE" = broken ]; then exit 17; fi',
                "UV",
                'chmod +x "$_target/uv"',
                "",
            ]
        )
    )
    curl = commands / "curl"
    _ = curl.write_text(
        "\n".join(
            [
                "#!/bin/sh",
                "set -eu",
                "out=''",
                'while [ "$#" -gt 0 ]; do',
                '  case "$1" in -o|--output) shift; out="$1";; esac',
                "  shift",
                "done",
                'if [ -n "$out" ]; then cat "$FAKE_BOOTSTRAP" > "$out";',
                'else cat "$FAKE_BOOTSTRAP"; fi',
                'if [ "$BOOTSTRAP_MODE" = download-failure ]; then exit 22; fi',
                "",
            ]
        )
    )
    curl.chmod(0o755)
    env = os.environ.copy()
    for name in ("UV_INSTALL_DIR", "UV_UNMANAGED_INSTALL", "XDG_BIN_HOME", "XDG_DATA_HOME"):
        _ = env.pop(name, None)
    env.update(
        PATH=str(commands),
        HOME=str(tmp_path / "home"),
        TMPDIR=str(tmp_path),
        ASSUME_YES="1",
        BOOTSTRAP_MODE="success",
        BOOTSTRAP_CALLED=str(tmp_path / "called"),
        FAKE_BOOTSTRAP=str(bootstrap),
    )
    return env


def _run_bootstrap(tmp_path: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    source = INSTALL_SH.read_text().split("# Version guard:", 1)[0]
    script = tmp_path / "bootstrap-under-test.sh"
    _ = script.write_text(source + "\nuv --version\ncommand -v uv\n")
    return subprocess.run(
        [os.environ.get("PD_INSTALL_TEST_SHELL", "/bin/sh"), str(script)],
        env=env,
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    "setting", ["default", "XDG_DATA_HOME", "XDG_BIN_HOME", "UV_INSTALL_DIR", "UV_UNMANAGED_INSTALL"]
)
def test_bootstrap_uses_resolved_directory_without_profile_changes(tmp_path: Path, setting: str) -> None:
    env = _bootstrap_environment(tmp_path)
    expected = tmp_path / "home/.local/bin"
    if setting == "XDG_DATA_HOME":
        env[setting] = str(tmp_path / "custom data/share")
        expected = tmp_path / "custom data/bin"
    elif setting != "default":
        env["XDG_DATA_HOME"] = str(tmp_path / "fallback data")
        if setting in {"UV_INSTALL_DIR", "UV_UNMANAGED_INSTALL"}:
            env["XDG_BIN_HOME"] = str(tmp_path / "fallback bin")
        if setting == "UV_UNMANAGED_INSTALL":
            env["UV_INSTALL_DIR"] = str(tmp_path / "fallback uv")
        env[setting] = str(tmp_path / "custom bin")
        expected = tmp_path / "custom bin"
    env["EXPECTED_UV_DIR"] = str(expected)
    result = _run_bootstrap(tmp_path, env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "uv 0.13.8" in result.stdout
    assert (expected / "uv").is_file()
    assert Path(env["BOOTSTRAP_CALLED"]).read_text() == "1"
    assert (
        Path(env.get("XDG_DATA_HOME", str(tmp_path / "home/.local/share")))
        / "pdomain-ocr-simple-gui/uv-installed-by-installer"
    ).exists()
    assert not list(tmp_path.glob("pdomain-uv-bootstrap.*"))


def test_bootstrap_reuses_configured_uv_without_claiming_it(tmp_path: Path) -> None:
    env = _bootstrap_environment(tmp_path)
    directory = tmp_path / "custom bin"
    directory.mkdir()
    executable = directory / "uv"
    _ = executable.write_text("#!/bin/sh\necho 'uv 0.13.8'\n")
    executable.chmod(0o755)
    env["UV_INSTALL_DIR"] = str(directory)
    result = _run_bootstrap(tmp_path, env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not Path(env["BOOTSTRAP_CALLED"]).exists()
    assert not (tmp_path / "home/.local/share/pdomain-ocr-simple-gui/uv-installed-by-installer").exists()


@pytest.mark.parametrize("mode", ["download-failure", "failure", "missing", "broken"])
def test_failed_bootstrap_does_not_claim_ownership(tmp_path: Path, mode: str) -> None:
    env = _bootstrap_environment(tmp_path)
    env["XDG_DATA_HOME"] = str(tmp_path / "data")
    env["EXPECTED_UV_DIR"] = str(tmp_path / "data/../bin")
    env["BOOTSTRAP_MODE"] = mode
    result = _run_bootstrap(tmp_path, env)
    assert result.returncode != 0
    assert not (tmp_path / "data/pdomain-ocr-simple-gui/uv-installed-by-installer").exists()
    if mode == "download-failure":
        assert not Path(env["BOOTSTRAP_CALLED"]).exists()
    assert not list(tmp_path.glob("pdomain-uv-bootstrap.*"))


@pytest.mark.parametrize(
    "setting", ["XDG_DATA_HOME", "XDG_BIN_HOME", "UV_INSTALL_DIR", "UV_UNMANAGED_INSTALL"]
)
def test_macos_wrapper_finds_uv_created_by_install_child(tmp_path: Path, setting: str) -> None:
    env = _bootstrap_environment(tmp_path)
    bin_dir = tmp_path / "custom bin"
    if setting == "XDG_DATA_HOME":
        env[setting] = str(tmp_path / "data/share")
        Path(env[setting]).mkdir(parents=True)
        bin_dir = tmp_path / "data/bin"
    else:
        env[setting] = str(bin_dir)
    env["EXPECTED_UV_DIR"] = str(bin_dir)
    tool_root = tmp_path / "tools"
    env["TEST_TOOL_ROOT"] = str(tool_root)
    env["TEST_INTEGRATION_LOG"] = str(tmp_path / "integration.log")
    interpreter = tool_root / "pdomain-ocr-simple-gui/bin/python"
    interpreter.parent.mkdir(parents=True)
    _ = interpreter.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$TEST_INTEGRATION_LOG"\n')
    interpreter.chmod(0o755)
    dialog = tmp_path / "dialog"
    _ = dialog.write_text(
        "\n".join(
            [
                "#!/bin/sh",
                'case "$3" in "Installation failed."*) exit 1;; esac',
                'if [ "$2" = progress ]; then exec /bin/sleep 30; fi',
                "",
            ]
        )
    )
    dialog.chmod(0o755)
    payload = tmp_path / "payload"
    payload.mkdir()
    _ = (payload / "install.sh").write_text(
        "\n".join(
            [
                "#!/bin/sh",
                "set -eu",
                'mkdir -p "$EXPECTED_UV_DIR"',
                "cat > \"$EXPECTED_UV_DIR/uv\" <<'UV'",
                "#!/bin/sh",
                'printf "%s\\n" "$TEST_TOOL_ROOT"',
                "UV",
                'chmod +x "$EXPECTED_UV_DIR/uv"',
                "",
            ]
        )
    )
    wrapper = payload / "install-native.sh"
    original = INSTALL_SH.parent / "installer/macos/install-native.sh"
    _ = wrapper.write_text(original.read_text().replace("/usr/bin/osascript", str(dialog)))
    result = subprocess.run(
        [os.environ.get("PD_INSTALL_TEST_SHELL", "/bin/sh"), str(wrapper)],
        env=env,
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "--integrate-only" in Path(env["TEST_INTEGRATION_LOG"]).read_text()
