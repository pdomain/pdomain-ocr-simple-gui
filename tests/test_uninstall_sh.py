from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
UNINSTALL_SH = REPO / "uninstall.sh"


# ---------------------------------------------------------------------------
# Static assertions -- no network, no actual uninstall.
# ---------------------------------------------------------------------------


def test_uninstall_sh_exists() -> None:
    assert UNINSTALL_SH.exists(), "uninstall.sh is missing from repo root"


def test_uninstall_sh_is_executable() -> None:
    assert os.access(UNINSTALL_SH, os.X_OK), "uninstall.sh is not executable"


def test_uninstall_sh_shebang() -> None:
    first_line = UNINSTALL_SH.read_text(encoding="utf-8").splitlines()[0]
    assert first_line == "#!/bin/sh", f"Bad shebang: {first_line!r}"


def test_uninstall_sh_set_e() -> None:
    content = UNINSTALL_SH.read_text(encoding="utf-8")
    assert "set -e" in content, "uninstall.sh must contain 'set -e'"


def test_uninstall_sh_syntax() -> None:
    """sh -n is a pure-syntax pass; never executes the script."""
    result = subprocess.run(
        ["sh", "-n", str(UNINSTALL_SH)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"sh -n uninstall.sh failed:\n{result.stderr}"


def test_uninstall_sh_no_bashisms() -> None:
    """Grep for common bashisms that are not valid POSIX sh."""
    content = UNINSTALL_SH.read_text(encoding="utf-8")
    assert "=(" not in content, "uninstall.sh uses bash array syntax '=('"
    assert "[[" not in content, "uninstall.sh uses bash double-bracket '[['"


# ---------------------------------------------------------------------------
# TTY / gate mechanism assertions (static grep)
# ---------------------------------------------------------------------------


def test_uninstall_sh_tty_detection_uses_dev_tty() -> None:
    """Gate reads from /dev/tty, not stdin, so curl-pipe works."""
    content = UNINSTALL_SH.read_text(encoding="utf-8")
    assert "/dev/tty" in content, "uninstall.sh must reference /dev/tty for terminal detection"


def test_uninstall_sh_tty_detection_exec_style() -> None:
    """Must use exec 3</dev/tty style; must not use [ -t 0 ] outside of comments."""
    content = UNINSTALL_SH.read_text(encoding="utf-8")
    assert "exec 3</dev/tty" in content, "uninstall.sh must use 'exec 3</dev/tty' for TTY detection"
    # [ -t 0 ] must not appear as actual sh code (comments are fine)
    non_comment_lines = [line for line in content.splitlines() if not line.lstrip().startswith("#")]
    assert not any("[ -t 0 ]" in line for line in non_comment_lines), (
        "uninstall.sh must NOT use [ -t 0 ] in executable code (false under curl|sh)"
    )
    # Must use the subshell-probe pattern for dash-compatible TTY detection
    assert 'sh -c "exec 3</dev/tty"' in content, (
        "uninstall.sh must probe /dev/tty in a subshell for dash compatibility"
    )


def test_uninstall_sh_read_from_fd3() -> None:
    """Gate reads answer from fd 3 (the /dev/tty fd)."""
    content = UNINSTALL_SH.read_text(encoding="utf-8")
    assert "read _ans <&3" in content, "uninstall.sh must read answer from fd 3"


def test_uninstall_sh_assume_yes_flag() -> None:
    """Must support -y / --yes flag and ASSUME_YES env var."""
    content = UNINSTALL_SH.read_text(encoding="utf-8")
    assert "ASSUME_YES" in content, "uninstall.sh must support ASSUME_YES env var"
    assert "-y|--yes" in content, "uninstall.sh must parse -y/--yes flag"
    assert '[ "$ASSUME_YES" = "1" ]' in content, "uninstall.sh must gate on ASSUME_YES=1"


# ---------------------------------------------------------------------------
# Step content assertions (static grep)
# ---------------------------------------------------------------------------


def test_uninstall_sh_calls_remove_desktop_shortcut() -> None:
    """Must call --remove-desktop-shortcut on the app (best-effort)."""
    content = UNINSTALL_SH.read_text(encoding="utf-8")
    assert "--remove-desktop-shortcut" in content, (
        "uninstall.sh must call pdomain-ocr-simple-gui --remove-desktop-shortcut"
    )


def test_uninstall_sh_calls_unregister_suite() -> None:
    """Must call --unregister-suite on the app (best-effort)."""
    content = UNINSTALL_SH.read_text(encoding="utf-8")
    assert "--unregister-suite" in content, "uninstall.sh must call pdomain-ocr-simple-gui --unregister-suite"


def test_uninstall_sh_suite_registry_note() -> None:
    """Must mention installed.toml so user can hand-edit if needed."""
    content = UNINSTALL_SH.read_text(encoding="utf-8")
    assert "installed.toml" in content, "uninstall.sh must mention installed.toml for manual registry editing"


def test_uninstall_sh_uv_tool_uninstall() -> None:
    """Must call uv tool uninstall pdomain-ocr-simple-gui."""
    content = UNINSTALL_SH.read_text(encoding="utf-8")
    assert "uv tool uninstall pdomain-ocr-simple-gui" in content, (
        "uninstall.sh must call 'uv tool uninstall pdomain-ocr-simple-gui'"
    )


def test_uninstall_sh_remove_app_gate() -> None:
    """Must gate tool removal with prompt_yn."""
    content = UNINSTALL_SH.read_text(encoding="utf-8")
    assert 'prompt_yn "Remove pdomain-ocr-simple-gui?" "Y"' in content, (
        "uninstall.sh must gate uv tool uninstall with prompt_yn 'Remove pdomain-ocr-simple-gui?'"
    )


def test_uninstall_sh_uv_marker_aware() -> None:
    """Must check the uv-installed-by-installer marker for context-aware default."""
    content = UNINSTALL_SH.read_text(encoding="utf-8")
    assert "uv-installed-by-installer" in content, (
        "uninstall.sh must check the uv-installed-by-installer marker"
    )


def test_uninstall_sh_uv_removal_default_yes_when_marker_present() -> None:
    """When marker is present, default for uv removal prompt must be Y."""
    content = UNINSTALL_SH.read_text(encoding="utf-8")
    # The marker-present branch sets _UV_DEFAULT="Y"
    assert '_UV_DEFAULT="Y"' in content, (
        "uninstall.sh must default to Y (remove uv) when the marker is present"
    )


def test_uninstall_sh_uv_removal_default_no_when_marker_absent() -> None:
    """When marker is absent, default for uv removal prompt must be N."""
    content = UNINSTALL_SH.read_text(encoding="utf-8")
    # The marker-absent branch sets _UV_DEFAULT="N"
    assert '_UV_DEFAULT="N"' in content, "uninstall.sh must default to N (keep uv) when the marker is absent"


def test_uninstall_sh_uv_self_uninstall() -> None:
    """Must attempt uv self uninstall."""
    content = UNINSTALL_SH.read_text(encoding="utf-8")
    assert "uv self uninstall" in content, "uninstall.sh must attempt 'uv self uninstall'"


def test_uninstall_sh_uv_removal_warning() -> None:
    """Must warn that removing uv affects other tools."""
    content = UNINSTALL_SH.read_text(encoding="utf-8")
    assert "other uv-managed tools" in content or "other uv" in content.lower(), (
        "uninstall.sh must warn that removing uv breaks other uv tools"
    )


def test_uninstall_sh_webkit_note() -> None:
    """Must mention WebKitGTK as a system package for manual removal."""
    content = UNINSTALL_SH.read_text(encoding="utf-8")
    assert "WebKitGTK" in content or "webkit" in content.lower(), (
        "uninstall.sh must mention WebKitGTK in final notes"
    )
    assert "system package" in content or "package manager" in content, (
        "uninstall.sh must note that WebKitGTK is a system package"
    )


def test_uninstall_sh_model_cache_note() -> None:
    """Must mention where OCR model caches can be found."""
    content = UNINSTALL_SH.read_text(encoding="utf-8")
    assert "doctr" in content.lower() or "model" in content.lower(), (
        "uninstall.sh must mention model cache paths in final notes"
    )
    assert ".cache" in content, "uninstall.sh must mention ~/.cache paths for model weights"


# ---------------------------------------------------------------------------
# Integration smoke -- fake environment, ASSUME_YES=1, no real uninstall.
# ---------------------------------------------------------------------------


def test_uninstall_sh_runs_end_to_end(tmp_path: Path) -> None:
    """Run uninstall.sh in a fake env with ASSUME_YES; verify expected calls."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    call_log = tmp_path / "calls.log"

    # Fake pdomain-ocr-simple-gui: log flags and exit 0
    (bin_dir / "pdomain-ocr-simple-gui").write_text(
        f"#!/bin/sh\nprintf 'pdomain-ocr-simple-gui %s\\n' \"$@\" >> {call_log}\nexit 0\n",
        encoding="utf-8",
    )
    (bin_dir / "pdomain-ocr-simple-gui").chmod(0o755)

    # Fake uv: log args and exit 0; uv self uninstall also exits 0
    (bin_dir / "uv").write_text(
        f"#!/bin/sh\nprintf 'uv %s\\n' \"$@\" >> {call_log}\nexit 0\n",
        encoding="utf-8",
    )
    (bin_dir / "uv").chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
    env["ASSUME_YES"] = "1"
    env["HOME"] = str(tmp_path)
    env["XDG_DATA_HOME"] = str(tmp_path / ".local" / "share")

    result = subprocess.run(
        ["sh", str(UNINSTALL_SH)],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    log = call_log.read_text(encoding="utf-8")

    # Must have called --remove-desktop-shortcut
    assert "--remove-desktop-shortcut" in log, f"Expected --remove-desktop-shortcut in calls; got:\n{log}"

    # Must have called --unregister-suite
    assert "--unregister-suite" in log, f"Expected --unregister-suite in calls; got:\n{log}"

    # Must have called uv tool uninstall
    assert "uv tool uninstall pdomain-ocr-simple-gui" in log or (
        "tool" in log and "uninstall" in log and "pdomain-ocr-simple-gui" in log
    ), f"Expected uv tool uninstall in calls; got:\n{log}"
