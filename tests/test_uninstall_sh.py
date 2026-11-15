from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
UNINSTALL_SH = REPO / "uninstall.sh"


def _write_executable(path: Path, body: str) -> None:
    _ = path.write_text(f"#!/bin/sh\nset -eu\n{body}\n", encoding="utf-8")
    _ = path.chmod(0o755)


def _fake_environment(tmp_path: Path, *, with_uv: bool = True) -> tuple[dict[str, str], Path, Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    call_log = tmp_path / "calls.log"
    app = bin_dir / "pdomain-ocr-simple-gui"
    _write_executable(app, f'printf "app %s\\n" "$*" >> "{call_log}"')
    if with_uv:
        uv = bin_dir / "uv"
        _write_executable(uv, f'printf "uv %s\\n" "$*" >> "{call_log}"')
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
    env["HOME"] = str(tmp_path / "home")
    env["XDG_DATA_HOME"] = str(tmp_path / "data")
    return env, call_log, app


def _run_uninstall(tmp_path: Path, env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    shell = os.environ.get("UNINSTALL_TEST_SHELL", "sh")
    return subprocess.run(
        [shell, str(UNINSTALL_SH), *args],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_uninstall_sh_exists() -> None:
    assert UNINSTALL_SH.exists(), "uninstall.sh is missing from repo root"


def test_uninstall_sh_is_executable() -> None:
    assert os.access(UNINSTALL_SH, os.X_OK), "uninstall.sh is not executable"


def test_uninstall_sh_is_posix_strict() -> None:
    content = UNINSTALL_SH.read_text(encoding="utf-8")
    assert content.startswith("#!/bin/sh\nset -eu\n")


def test_uninstall_sh_syntax() -> None:
    """sh -n is a pure-syntax pass; it never executes the script."""
    result = subprocess.run(
        ["sh", "-n", str(UNINSTALL_SH)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"sh -n uninstall.sh failed:\n{result.stderr}"


def test_uninstall_sh_no_bashisms() -> None:
    content = UNINSTALL_SH.read_text(encoding="utf-8")
    assert "=(" not in content, "uninstall.sh uses bash array syntax '=('"
    assert "[[" not in content, "uninstall.sh uses bash double-bracket '[['"


def test_uninstall_sh_uses_controlling_terminal_for_confirmation() -> None:
    content = UNINSTALL_SH.read_text(encoding="utf-8")
    assert "exec 3</dev/tty" in content
    assert 'sh -c "exec 3</dev/tty"' in content
    assert "read -r answer <&3" in content


def test_uninstall_sh_never_removes_uv() -> None:
    content = UNINSTALL_SH.read_text(encoding="utf-8")
    assert "uv self uninstall" not in content
    assert "uv-installed-by-installer" not in content
    assert "Keeping uv, its Python installations, and other uv tools." in content


def test_uninstall_sh_documents_actual_data_locations_and_overrides() -> None:
    content = UNINSTALL_SH.read_text(encoding="utf-8")
    assert "pdomain-suite/simple-gui/projects" in content
    assert "PD_OCR_SIMPLE_GUI_PROJECTS_ROOT" in content
    assert "PD_OCR_SIMPLE_GUI_OUTPUT_ROOT" in content
    assert "PD_OCR_SIMPLE_GUI_UPLOAD_ROOT" in content
    assert "PD_OCR_SIMPLE_GUI_JOBS_META_ROOT" in content
    assert "rm -rf" not in content


def test_uninstall_sh_cancel_has_no_side_effects(tmp_path: Path) -> None:
    env, call_log, _ = _fake_environment(tmp_path)

    result = _run_uninstall(tmp_path, env)

    assert result.returncode == 0, result.stderr + result.stdout
    assert not call_log.exists(), call_log.read_text(encoding="utf-8")
    assert "No changes were made." in result.stdout


def test_uninstall_sh_yes_removes_only_the_app_and_preserves_uv(tmp_path: Path) -> None:
    env, call_log, _ = _fake_environment(tmp_path)

    result = _run_uninstall(tmp_path, env, "-y")

    assert result.returncode == 0, result.stderr + result.stdout
    log = call_log.read_text(encoding="utf-8")
    assert "app --remove-desktop-shortcut" in log
    assert "app --unregister-suite" in log
    assert "uv tool uninstall pdomain-ocr-simple-gui" in log
    assert "uv self uninstall" not in log
    assert "Keeping uv, its Python installations, and other uv tools." in result.stdout


def test_uninstall_sh_headless_mode_does_not_mutate(tmp_path: Path) -> None:
    env, call_log, _ = _fake_environment(tmp_path)

    result = _run_uninstall(tmp_path, env)

    assert result.returncode == 0, result.stderr + result.stdout
    assert not call_log.exists(), call_log.read_text(encoding="utf-8")


def test_uninstall_sh_handles_absent_uv_without_side_effects(tmp_path: Path) -> None:
    env, call_log, _ = _fake_environment(tmp_path, with_uv=False)
    env["ASSUME_YES"] = "1"
    env["PATH"] = f"{tmp_path / 'bin'}:/usr/bin:/bin"

    result = _run_uninstall(tmp_path, env)

    assert result.returncode == 0, result.stderr + result.stdout
    assert not call_log.exists(), call_log.read_text(encoding="utf-8")
    assert "uv is not on PATH" in result.stdout


def test_uninstall_sh_propagates_native_shortcut_failure(tmp_path: Path) -> None:
    env, call_log, app = _fake_environment(tmp_path)
    _write_executable(app, f'printf "app %s\\n" "$*" >> "{call_log}"\nexit 23')
    env["ASSUME_YES"] = "1"

    result = _run_uninstall(tmp_path, env)

    assert result.returncode == 23, result.stderr + result.stdout
    log = call_log.read_text(encoding="utf-8")
    assert "app --remove-desktop-shortcut" in log
    assert "uv tool uninstall" not in log


def test_uninstall_sh_propagates_uv_failure(tmp_path: Path) -> None:
    env, call_log, _ = _fake_environment(tmp_path)
    _write_executable(
        tmp_path / "bin" / "uv",
        f'printf "uv %s\\n" "$*" >> "{call_log}"\nexit 37',
    )
    env["ASSUME_YES"] = "1"

    result = _run_uninstall(tmp_path, env)

    assert result.returncode == 37, result.stderr + result.stdout
    assert "uv tool uninstall pdomain-ocr-simple-gui" in call_log.read_text(encoding="utf-8")
