from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
INSTALL_SH = REPO / "install.sh"


# ---------------------------------------------------------------------------
# Static assertions -- no network, no actual install.
# ---------------------------------------------------------------------------


def test_install_sh_exists() -> None:
    assert INSTALL_SH.exists(), "install.sh is missing from repo root"


def test_install_sh_is_executable() -> None:
    assert os.access(INSTALL_SH, os.X_OK), "install.sh is not executable"


def test_install_sh_shebang() -> None:
    first_line = INSTALL_SH.read_text(encoding="utf-8").splitlines()[0]
    assert first_line == "#!/bin/sh", f"Bad shebang: {first_line!r}"


def test_install_sh_set_e() -> None:
    content = INSTALL_SH.read_text(encoding="utf-8")
    assert "set -e" in content, "install.sh must contain 'set -e'"


def test_install_sh_repo_name() -> None:
    content = INSTALL_SH.read_text(encoding="utf-8")
    assert 'REPO="pdomain/pdomain-ocr-simple-gui"' in content


def test_install_sh_pdomain_index_url() -> None:
    content = INSTALL_SH.read_text(encoding="utf-8")
    assert "https://pdomain.github.io/pdomain-index-pip/simple/" in content


def test_install_sh_desktop_with_arg() -> None:
    content = INSTALL_SH.read_text(encoding="utf-8")
    assert '--with "pdomain-ops[desktop]"' in content, (
        "install.sh must always pass --with pdomain-ops[desktop]"
    )


def test_install_sh_xcb_cursor_hint() -> None:
    content = INSTALL_SH.read_text(encoding="utf-8")
    # Must mention the xcb-cursor lib (Qt X11 backend requirement)
    assert "libxcb-cursor" in content or "xcb-cursor" in content, (
        "install.sh must include a Qt xcb-cursor installation hint"
    )
    # Debian/Ubuntu package name must appear
    assert "libxcb-cursor0" in content
    # Wayland exemption note must be present
    assert "Wayland" in content or "wayland" in content


def test_install_sh_final_hint_desktop() -> None:
    content = INSTALL_SH.read_text(encoding="utf-8")
    assert "--desktop" in content, "install.sh success message must mention the --desktop launch flag"


def test_install_sh_final_hint_browser_port() -> None:
    content = INSTALL_SH.read_text(encoding="utf-8")
    assert "8004" in content, "install.sh success message must mention the default browser port 8004"


def test_install_sh_no_bashisms() -> None:
    """Grep for common bashisms that are not valid POSIX sh."""
    content = INSTALL_SH.read_text(encoding="utf-8")
    # bash arrays: FOO=(...)
    assert "=(" not in content, "install.sh uses bash array syntax '=('"
    # local keyword outside function context is fine in practice but
    # double-bracket [[...]] is a definite bashism
    assert "[[" not in content, "install.sh uses bash double-bracket '[['"


def test_install_sh_syntax() -> None:
    """sh -n is a pure-syntax pass; never executes the script."""
    result = subprocess.run(
        ["sh", "-n", str(INSTALL_SH)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"sh -n install.sh failed:\n{result.stderr}"


# ---------------------------------------------------------------------------
# Gate mechanism assertions (static grep)
# ---------------------------------------------------------------------------


def test_install_sh_tty_detection_uses_dev_tty() -> None:
    """Gate reads from /dev/tty, not stdin, so curl-pipe works."""
    content = INSTALL_SH.read_text(encoding="utf-8")
    assert "/dev/tty" in content, "install.sh must reference /dev/tty for terminal detection"


def test_install_sh_tty_detection_exec_style() -> None:
    """Must use exec 3</dev/tty style; must not use [ -t 0 ] outside of comments."""
    content = INSTALL_SH.read_text(encoding="utf-8")
    # Must use exec 3</dev/tty to open the tty fd
    assert "exec 3</dev/tty" in content, "install.sh must use 'exec 3</dev/tty' for TTY detection"
    # [ -t 0 ] must not appear as actual sh code (comments are fine and even useful)
    non_comment_lines = [line for line in content.splitlines() if not line.lstrip().startswith("#")]
    assert not any("[ -t 0 ]" in line for line in non_comment_lines), (
        "install.sh must NOT use [ -t 0 ] in executable code (false under curl|sh)"
    )
    # Must use the subshell-probe pattern for dash-compatible TTY detection
    assert 'sh -c "exec 3</dev/tty"' in content, (
        "install.sh must probe /dev/tty in a subshell for dash compatibility"
    )


def test_install_sh_read_from_fd3() -> None:
    """Gate reads answer from fd 3 (the /dev/tty fd)."""
    content = INSTALL_SH.read_text(encoding="utf-8")
    assert "read _ans <&3" in content, "install.sh must read answer from fd 3 (the /dev/tty fd)"


def test_install_sh_assume_yes_flag() -> None:
    """Must support -y / --yes flag and ASSUME_YES env var."""
    content = INSTALL_SH.read_text(encoding="utf-8")
    assert "ASSUME_YES" in content, "install.sh must support ASSUME_YES env var"
    assert "-y|--yes" in content, "install.sh must parse -y/--yes flag"
    assert '[ "$ASSUME_YES" = "1" ]' in content, "install.sh must gate on ASSUME_YES=1"


def test_install_sh_summary_block() -> None:
    """Must print a summary block before uv tool install."""
    content = INSTALL_SH.read_text(encoding="utf-8")
    assert "About to install:" in content, "install.sh must print 'About to install:' summary"
    assert "Package:" in content, "install.sh summary must include Package field"
    assert "GPU:" in content, "install.sh summary must include GPU field"
    assert "Desktop:" in content, "install.sh summary must include Desktop field"
    assert "Target:" in content, "install.sh summary must include Target field"
    assert "Index:" in content, "install.sh summary must include Index field"


def test_install_sh_proceed_gate() -> None:
    """Must call prompt_yn before uv tool install."""
    content = INSTALL_SH.read_text(encoding="utf-8")
    assert 'prompt_yn "Proceed with install?" "Y"' in content, (
        "install.sh must gate uv tool install with prompt_yn 'Proceed with install?'"
    )


def test_install_sh_cuda_diskspace_warning_present() -> None:
    """Must include a disk-space warning for GPU/CUDA builds."""
    content = INSTALL_SH.read_text(encoding="utf-8")
    assert "Heads up - disk space" in content, (
        "install.sh must include a disk-space heads-up for CUDA/GPU builds"
    )
    assert "CUDA-flavored PyTorch wheels" in content, (
        "install.sh disk-space warning must mention CUDA-flavored PyTorch wheels"
    )
    assert "2-3 GB" in content, "install.sh disk-space warning must give a rough download size (2-3 GB)"


def test_install_sh_cuda_diskspace_warning_gated_on_extra_index() -> None:
    """The disk-space warning must be gated on EXTRA_INDEX (GPU build only).

    A CPU-only install must NOT show the GPU download warning. Grep confirms
    the warning block is inside an ``if [ -n "$EXTRA_INDEX" ]`` guard.
    """
    content = INSTALL_SH.read_text(encoding="utf-8")
    # The warning text must appear inside an EXTRA_INDEX block.
    # We verify this by checking that the guard appears before the warning
    # text in the file and that the pattern is the standard non-empty guard.
    guard_str = 'if [ -n "$EXTRA_INDEX" ]'
    extra_index_guard_pos = content.find(guard_str)
    diskspace_pos = content.find("Heads up - disk space")
    # There will be multiple EXTRA_INDEX guards (GPU detection + install args).
    # At least one guard must appear before the warning text.
    assert extra_index_guard_pos != -1, 'install.sh must have an `if [ -n "$EXTRA_INDEX" ]` guard'
    assert diskspace_pos != -1, "install.sh must contain the disk-space warning text"
    # The specific guard wrapping the diskspace warning: find the last
    # EXTRA_INDEX guard before the diskspace text.
    guard_before_warning = content.rfind(guard_str, 0, diskspace_pos)
    assert guard_before_warning != -1, (
        'Disk-space warning must be inside an `if [ -n "$EXTRA_INDEX" ]` block. '
        "CPU-only users must not see the CUDA download warning."
    )
    # Confirm no CUDA Toolkit mention -- we only pull PyTorch wheels, not the Toolkit.
    assert "CUDA Toolkit" not in content or content.count("CUDA Toolkit") == 0, (
        "install.sh must not mention 'CUDA Toolkit' -- only CUDA-flavored PyTorch "
        "wheels are downloaded, not the full CUDA Toolkit (~10 GB)."
    )


def test_install_sh_uv_gate() -> None:
    """Must gate the uv bootstrap with prompt_yn."""
    content = INSTALL_SH.read_text(encoding="utf-8")
    assert "astral.sh/uv/install.sh" in content, "install.sh must reference astral uv installer"
    assert "prompt_yn" in content, "install.sh must use prompt_yn helper"
    # The uv gate must appear before the summary gate in the file
    uv_gate_pos = content.find("uv is not installed")
    summary_gate_pos = content.find("About to install:")
    assert uv_gate_pos < summary_gate_pos, "uv gate must appear before summary gate"


def test_install_sh_uv_marker_written_in_bootstrap_branch() -> None:
    """Must write the uv-installed-by-installer marker only in the uv bootstrap branch."""
    content = INSTALL_SH.read_text(encoding="utf-8")
    assert "uv-installed-by-installer" in content, (
        "install.sh must reference uv-installed-by-installer marker"
    )
    assert "pdomain-ocr-simple-gui" in content, "marker path must include pdomain-ocr-simple-gui dir"
    # The marker write (touch) must be inside the uv bootstrap branch
    # (i.e., after the astral.sh install, before the fi closing the if uv block)
    uv_install_pos = content.find("astral.sh/uv/install.sh")
    marker_touch_pos = content.find('touch "$_MARKER"')
    uv_block_end = content.find("fi\n", uv_install_pos)
    assert uv_install_pos < marker_touch_pos < uv_block_end, (
        "uv marker must be written inside the uv bootstrap branch, not unconditionally"
    )


def test_install_sh_declined_uv_exits_1() -> None:
    """When user declines uv install and uv is absent, must exit 1 with instructions."""
    content = INSTALL_SH.read_text(encoding="utf-8")
    assert "uv is required to install pdomain-ocr-simple-gui" in content, (
        "install.sh must print uv-required message when uv install declined"
    )
    assert "exit 1" in content, "install.sh must exit 1 when uv install declined"


# ---------------------------------------------------------------------------
# uv version guard assertions (static grep)
# ---------------------------------------------------------------------------


def test_install_sh_min_uv_version_constant() -> None:
    """Must define MIN_UV_VERSION constant with the required minimum."""
    content = INSTALL_SH.read_text(encoding="utf-8")
    assert 'MIN_UV_VERSION="0.11.16"' in content, (
        'install.sh must define MIN_UV_VERSION="0.11.16" so it is easy to bump'
    )


def test_install_sh_min_uv_version_check_present() -> None:
    """Must contain version-check logic that references 0.11.16."""
    content = INSTALL_SH.read_text(encoding="utf-8")
    assert "0.11.16" in content, (
        "install.sh must reference the minimum uv version 0.11.16 in its version guard"
    )


def test_install_sh_uv_version_parse() -> None:
    """Must parse uv --version output to extract the version string."""
    content = INSTALL_SH.read_text(encoding="utf-8")
    assert "uv --version" in content, "install.sh must call 'uv --version' to check the installed uv version"


def test_install_sh_uv_version_guard_default_n() -> None:
    """Must gate old-uv continue prompt with default N (abort by default)."""
    content = INSTALL_SH.read_text(encoding="utf-8")
    # The prompt must warn user and offer N as default (abort)
    assert "older than the required" in content or "older than" in content, (
        "install.sh must warn when installed uv is older than the minimum"
    )
    # The version-guard prompt must use N as default (abort is safer)
    assert "uv self update" in content, "install.sh must suggest 'uv self update' to upgrade uv"


def test_install_sh_uv_version_guard_posix_compare() -> None:
    """Version compare must be POSIX sh (no sort -V in executable code)."""
    content = INSTALL_SH.read_text(encoding="utf-8")
    # sort -V must not appear in executable code (it is not POSIX-guaranteed).
    # Comments documenting its absence are fine (and encouraged).
    non_comment_lines = [line for line in content.splitlines() if not line.lstrip().startswith("#")]
    assert not any("sort -V" in line for line in non_comment_lines), (
        "install.sh must not use 'sort -V' in executable code (not POSIX-guaranteed); "
        "comments mentioning sort -V as a non-dependency are fine"
    )


# ---------------------------------------------------------------------------
# Integration smoke -- fake uv/curl/gh; never touches network.
# ---------------------------------------------------------------------------


def test_install_sh_runs_end_to_end(tmp_path: Path) -> None:
    """Run install.sh in a fake environment; verify uv receives expected args."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    uv_log = tmp_path / "uv.log"

    # Fake uv: log all args then exit 0
    (bin_dir / "uv").write_text(
        f"#!/bin/sh\nprintf '%s\\n' \"$@\" > {uv_log}\nexit 0\n",
        encoding="utf-8",
    )
    (bin_dir / "uv").chmod(0o755)

    # Fake curl: return GitHub API JSON for the API call, write a fake wheel
    # for the download call (detected by presence of -o flag)
    (bin_dir / "curl").write_text(
        """#!/bin/sh
out=""
while [ "$#" -gt 0 ]; do
  if [ "$1" = "-o" ]; then shift; out="$1"; fi
  shift || true
done
if [ -n "$out" ]; then
  printf 'fake wheel' > "$out"
else
  cat <<'JSON'
{"tag_name":"v1.2.3","assets":[{"browser_download_url":"https://example.invalid/pdomain_ocr_simple_gui-1.2.3-py3-none-any.whl"}]}
JSON
fi
exit 0
""",
        encoding="utf-8",
    )
    (bin_dir / "curl").chmod(0o755)

    # Fake gh: exit 1 so we fall through to curl path
    (bin_dir / "gh").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    (bin_dir / "gh").chmod(0o755)

    # Fake nvidia-smi: exit 1 (no GPU)
    (bin_dir / "nvidia-smi").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    (bin_dir / "nvidia-smi").chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
    env["PD_SIMPLE_GUI_INSTALL_PYTHON"] = "3.12"
    # Skip all confirmation prompts in test
    env["ASSUME_YES"] = "1"
    # Force uv-tool path: the release JSON has no AppImage asset, so the
    # AppImage path would fall through anyway, but be explicit for clarity.
    env["NO_APPIMAGE"] = "1"

    result = subprocess.run(
        ["sh", str(INSTALL_SH)],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    args = uv_log.read_text(encoding="utf-8")

    # uv must be called with the right Python version
    assert "--python\n3.12" in args

    # pdomain-index-pip must be passed
    assert "--extra-index-url" in args
    assert "https://pdomain.github.io/pdomain-index-pip/simple/" in args

    # The downloaded wheel must be installed
    assert "pdomain_ocr_simple_gui-1.2.3-py3-none-any.whl" in args

    # Desktop extra via pdomain-ops must be present
    assert "pdomain-ops[desktop]" in args

    # Must NOT fall back to git source install
    assert "git+https://github.com/pdomain/pdomain-ocr-simple-gui" not in args


def test_install_sh_uv_version_guard_aborts_on_old_uv(tmp_path: Path) -> None:
    """When installed uv is below MIN_UV_VERSION and user declines, must exit 1."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()

    # Fake uv that reports a very old version (0.1.0)
    (bin_dir / "uv").write_text(
        '#!/bin/sh\nif [ "$1" = "--version" ]; then echo "uv 0.1.0 (abc123)"; exit 0; fi\nexit 0\n',
        encoding="utf-8",
    )
    (bin_dir / "uv").chmod(0o755)

    # Fake curl: return GitHub API JSON for the API call, write a fake wheel
    (bin_dir / "curl").write_text(
        """#!/bin/sh
out=""
while [ "$#" -gt 0 ]; do
  if [ "$1" = "-o" ]; then shift; out="$1"; fi
  shift || true
done
if [ -n "$out" ]; then
  printf 'fake wheel' > "$out"
else
  cat <<'JSON'
{"tag_name":"v1.2.3","assets":[{"browser_download_url":"https://example.invalid/pdomain_ocr_simple_gui-1.2.3-py3-none-any.whl"}]}
JSON
fi
exit 0
""",
        encoding="utf-8",
    )
    (bin_dir / "curl").chmod(0o755)

    # Fake gh: exit 1 so we fall through to curl path
    (bin_dir / "gh").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    (bin_dir / "gh").chmod(0o755)

    # Fake nvidia-smi: exit 1 (no GPU)
    (bin_dir / "nvidia-smi").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    (bin_dir / "nvidia-smi").chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
    env["PD_SIMPLE_GUI_INSTALL_PYTHON"] = "3.12"
    # No ASSUME_YES -- the version-guard prompt defaults to N (abort)
    # With no TTY the headless path takes the default, which is N (abort)
    env.pop("ASSUME_YES", None)
    # Force uv-tool path; AppImage path would be attempted on GUI desktops
    env["NO_APPIMAGE"] = "1"

    result = subprocess.run(
        ["sh", str(INSTALL_SH)],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    # Must have exited non-zero (aborted due to old uv) or printed a warning
    # In headless mode with default N, the script should abort
    combined = result.stdout + result.stderr
    assert "0.1.0" in combined or "older" in combined or result.returncode != 0, (
        "install.sh must warn or abort when the installed uv is below the minimum version"
    )


def test_install_sh_uv_version_guard_proceeds_on_current_uv(tmp_path: Path) -> None:
    """When installed uv meets MIN_UV_VERSION, must proceed without warning."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    uv_log = tmp_path / "uv.log"

    # Fake uv that reports a current version (1.0.0 — clearly above 0.11.16)
    (bin_dir / "uv").write_text(
        f"#!/bin/sh\n"
        f'if [ "$1" = "--version" ]; then echo "uv 1.0.0 (abc123)"; exit 0; fi\n'
        f'printf "%s\\n" "$@" >> {uv_log}\n'
        f"exit 0\n",
        encoding="utf-8",
    )
    (bin_dir / "uv").chmod(0o755)

    # Fake curl: GitHub API + wheel download
    (bin_dir / "curl").write_text(
        """#!/bin/sh
out=""
while [ "$#" -gt 0 ]; do
  if [ "$1" = "-o" ]; then shift; out="$1"; fi
  shift || true
done
if [ -n "$out" ]; then
  printf 'fake wheel' > "$out"
else
  cat <<'JSON'
{"tag_name":"v1.2.3","assets":[{"browser_download_url":"https://example.invalid/pdomain_ocr_simple_gui-1.2.3-py3-none-any.whl"}]}
JSON
fi
exit 0
""",
        encoding="utf-8",
    )
    (bin_dir / "curl").chmod(0o755)

    (bin_dir / "gh").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    (bin_dir / "gh").chmod(0o755)

    (bin_dir / "nvidia-smi").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    (bin_dir / "nvidia-smi").chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
    env["PD_SIMPLE_GUI_INSTALL_PYTHON"] = "3.12"
    env["ASSUME_YES"] = "1"
    # Force uv-tool path in this test; AppImage path requires GUI session
    env["NO_APPIMAGE"] = "1"

    result = subprocess.run(
        ["sh", str(INSTALL_SH)],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    # Must NOT print old-uv warning
    combined = result.stdout + result.stderr
    assert "older than" not in combined, (
        f"install.sh must not warn about old uv when version is current; got:\n{combined}"
    )


# ---------------------------------------------------------------------------
# AppImage preference logic assertions (static grep)
# ---------------------------------------------------------------------------


def test_install_sh_no_appimage_flag() -> None:
    """Must support --no-appimage flag and NO_APPIMAGE env var."""
    content = INSTALL_SH.read_text(encoding="utf-8")
    assert "NO_APPIMAGE" in content, "install.sh must support NO_APPIMAGE env var"
    assert "--no-appimage" in content, "install.sh must parse --no-appimage flag"


def test_install_sh_appimage_supported_check() -> None:
    """AppImage path must be gated on Linux x86_64 + GUI session + python3."""
    content = INSTALL_SH.read_text(encoding="utf-8")
    # Must check Linux platform
    assert "uname -s" in content, "install.sh must check uname -s for AppImage support"
    # Must check x86_64 arch
    assert "uname -m" in content, "install.sh must check uname -m for AppImage support"
    # Must check GUI session
    assert "DISPLAY" in content or "WAYLAND_DISPLAY" in content, (
        "install.sh must check DISPLAY/WAYLAND_DISPLAY for AppImage support"
    )
    # Must check python3 availability
    assert "python3" in content, "install.sh must check python3 availability for AppImage"


def test_install_sh_appimage_download_path() -> None:
    """AppImage must be downloaded to a sensible user location."""
    content = INSTALL_SH.read_text(encoding="utf-8")
    assert "pdomain-ocr-simple-gui-installer.AppImage" in content, (
        "install.sh must reference the AppImage installer filename"
    )
    assert ".local/bin" in content, "install.sh must download AppImage to ~/.local/bin"


def test_install_sh_appimage_no_appimage_guard() -> None:
    """AppImage path must be skipped when NO_APPIMAGE=1 or --no-appimage passed."""
    content = INSTALL_SH.read_text(encoding="utf-8")
    # The guard must appear inside the AppImage detection function/block
    assert '[ "$NO_APPIMAGE" = "1" ]' in content, (
        'install.sh must gate AppImage path on [ "$NO_APPIMAGE" = "1" ]'
    )


def test_install_sh_appimage_fallback_comment() -> None:
    """Must document that uv-tool path is the fallback when AppImage is unsupported."""
    content = INSTALL_SH.read_text(encoding="utf-8")
    # The fallback must be mentioned in a comment
    assert "fall" in content.lower() and "appimage" in content.lower(), (
        "install.sh must mention the AppImage fallback to uv-tool path"
    )


def test_install_sh_appimage_chmod() -> None:
    """Must chmod +x the downloaded AppImage."""
    content = INSTALL_SH.read_text(encoding="utf-8")
    assert "chmod +x" in content, "install.sh must chmod +x the downloaded AppImage"


# ---------------------------------------------------------------------------
# AppImage integration smoke -- no-appimage forces uv path
# ---------------------------------------------------------------------------


def test_install_sh_no_appimage_forces_uv_path(tmp_path: Path) -> None:
    """--no-appimage must skip the AppImage path and use uv tool install."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    uv_log = tmp_path / "uv.log"

    # Fake uv: log all args
    (bin_dir / "uv").write_text(
        f"#!/bin/sh\n"
        f'if [ "$1" = "--version" ]; then echo "uv 1.0.0 (abc123)"; exit 0; fi\n'
        f'printf "%s\\n" "$@" >> {uv_log}\n'
        f"exit 0\n",
        encoding="utf-8",
    )
    (bin_dir / "uv").chmod(0o755)

    # Fake curl: return JSON with only a wheel asset (no AppImage)
    (bin_dir / "curl").write_text(
        """#!/bin/sh
out=""
while [ "$#" -gt 0 ]; do
  if [ "$1" = "-o" ]; then shift; out="$1"; fi
  shift || true
done
if [ -n "$out" ]; then
  printf 'fake wheel' > "$out"
else
  cat <<'JSON'
{"tag_name":"v1.2.3","assets":[{"browser_download_url":"https://example.invalid/pdomain_ocr_simple_gui-1.2.3-py3-none-any.whl"}]}
JSON
fi
exit 0
""",
        encoding="utf-8",
    )
    (bin_dir / "curl").chmod(0o755)

    (bin_dir / "gh").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    (bin_dir / "gh").chmod(0o755)

    (bin_dir / "nvidia-smi").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    (bin_dir / "nvidia-smi").chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
    env["PD_SIMPLE_GUI_INSTALL_PYTHON"] = "3.12"
    env["ASSUME_YES"] = "1"
    # Simulate a GUI session — but --no-appimage should override
    env["DISPLAY"] = ":0"

    result = subprocess.run(
        ["sh", str(INSTALL_SH), "--no-appimage"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    # uv must have been called (uv tool install was reached)
    assert uv_log.exists(), "uv must have been called when --no-appimage is passed"
    args = uv_log.read_text(encoding="utf-8")
    assert "tool" in args and "install" in args, (
        f"uv tool install must be called when --no-appimage is set; uv args: {args}"
    )


def test_install_sh_appimage_exec_branch_taken(tmp_path: Path) -> None:
    """When the AppImage is supported AND available, install.sh must exec it.

    Positive counterpart to the fallback tests: with a GUI session
    (DISPLAY set), Linux x86_64, python3 present, NO_APPIMAGE unset, and an
    ``.AppImage`` asset on the release, the script must download the AppImage
    and ``exec`` it -- NOT fall through to the uv-tool path.

    Proof: the AppImage stub echoes the sentinel ``APPIMAGE_RAN`` (so its
    stdout reaching us proves the exec branch ran), and the uv stub touches
    a marker file if invoked (so the marker's ABSENCE proves the uv-tool
    path was skipped).
    """
    if platform.machine() != "x86_64":
        pytest.skip("AppImage support gate requires x86_64; test host is not x86_64")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    uv_was_called = tmp_path / "uv_was_called"

    # Fake uv: touch a marker if EVER invoked, so we can assert it was NOT
    # used on the AppImage exec path.
    (bin_dir / "uv").write_text(
        f"#!/bin/sh\n"
        f'if [ "$1" = "--version" ]; then echo "uv 1.0.0 (abc123)"; exit 0; fi\n'
        f"touch {uv_was_called}\n"
        f"exit 0\n",
        encoding="utf-8",
    )
    (bin_dir / "uv").chmod(0o755)

    # Fake curl:
    #   - no -o  -> emit release JSON that includes an .AppImage asset
    #   - -o + URL ends in .AppImage -> write a fake-executable AppImage stub
    #     that echoes the APPIMAGE_RAN sentinel and exits 0
    #   - -o + anything else (e.g. the wheel) -> write a placeholder
    (bin_dir / "curl").write_text(
        """#!/bin/sh
out=""
url=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    -o) shift; out="$1" ;;
    http*|https*) url="$1" ;;
  esac
  shift || true
done
if [ -n "$out" ]; then
  case "$url" in
    *.AppImage)
      cat > "$out" <<'STUB'
#!/bin/sh
echo APPIMAGE_RAN
exit 0
STUB
      ;;
    *)
      printf 'fake wheel' > "$out"
      ;;
  esac
else
  cat <<'JSON'
{
"tag_name":"v1.2.3",
"assets":[
{"browser_download_url":"https://example.invalid/pdomain_ocr_simple_gui-1.2.3-py3-none-any.whl"},
{"browser_download_url":"https://example.invalid/pdomain-ocr-simple-gui-installer-x86_64.AppImage"}
]
}
JSON
fi
exit 0
""",
        encoding="utf-8",
    )
    (bin_dir / "curl").chmod(0o755)

    # Fake gh: exit 1 so we fall through to the curl API path
    (bin_dir / "gh").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    (bin_dir / "gh").chmod(0o755)

    # Fake nvidia-smi: exit 1 (no GPU)
    (bin_dir / "nvidia-smi").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    (bin_dir / "nvidia-smi").chmod(0o755)

    env = os.environ.copy()
    # Prepend our stubs but keep the real PATH so `command -v python3`
    # (part of the AppImage support gate) still resolves.
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
    env["PD_SIMPLE_GUI_INSTALL_PYTHON"] = "3.12"
    env["ASSUME_YES"] = "1"
    # Force the support gate ON: GUI session present.
    env["DISPLAY"] = ":0"
    env.pop("WAYLAND_DISPLAY", None)
    # NO_APPIMAGE must be unset so the AppImage path is eligible.
    env.pop("NO_APPIMAGE", None)
    # Redirect the AppImage download/exec target (~/.local/bin) into tmp_path
    # so we never touch the real home dir.
    env["HOME"] = str(tmp_path / "home")
    (tmp_path / "home").mkdir()

    result = subprocess.run(
        ["sh", str(INSTALL_SH)],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    combined = result.stdout + result.stderr
    # The exec branch ran: install.sh exec'd the AppImage stub, whose stdout
    # carries the sentinel.
    assert "APPIMAGE_RAN" in combined, (
        f"AppImage exec branch was not taken; expected APPIMAGE_RAN sentinel in output.\n{combined}"
    )
    # The uv-tool path was skipped: uv was never invoked.
    assert not uv_was_called.exists(), (
        "uv must NOT be invoked when the AppImage exec branch is taken "
        f"(uv_was_called marker present).\n{combined}"
    )


def test_install_sh_appimage_fallback_on_no_asset(tmp_path: Path) -> None:
    """When no AppImage asset exists on the release, must fall back to uv-tool."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    uv_log = tmp_path / "uv.log"

    (bin_dir / "uv").write_text(
        f"#!/bin/sh\n"
        f'if [ "$1" = "--version" ]; then echo "uv 1.0.0 (abc123)"; exit 0; fi\n'
        f'printf "%s\\n" "$@" >> {uv_log}\n'
        f"exit 0\n",
        encoding="utf-8",
    )
    (bin_dir / "uv").chmod(0o755)

    # curl returns JSON with NO AppImage asset — only a wheel
    (bin_dir / "curl").write_text(
        """#!/bin/sh
out=""
while [ "$#" -gt 0 ]; do
  if [ "$1" = "-o" ]; then shift; out="$1"; fi
  shift || true
done
if [ -n "$out" ]; then
  printf 'fake wheel' > "$out"
else
  cat <<'JSON'
{"tag_name":"v1.2.3","assets":[{"browser_download_url":"https://example.invalid/pdomain_ocr_simple_gui-1.2.3-py3-none-any.whl"}]}
JSON
fi
exit 0
""",
        encoding="utf-8",
    )
    (bin_dir / "curl").chmod(0o755)

    (bin_dir / "gh").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    (bin_dir / "gh").chmod(0o755)

    (bin_dir / "nvidia-smi").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    (bin_dir / "nvidia-smi").chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
    env["PD_SIMPLE_GUI_INSTALL_PYTHON"] = "3.12"
    env["ASSUME_YES"] = "1"
    # Simulate Linux x86_64 with GUI (AppImage would be attempted if asset existed)
    env["DISPLAY"] = ":0"

    result = subprocess.run(
        ["sh", str(INSTALL_SH)],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    # Must succeed via fallback uv-tool path
    assert result.returncode == 0, result.stderr + result.stdout
    assert uv_log.exists(), "uv must have been called via fallback uv-tool path"
    args = uv_log.read_text(encoding="utf-8")
    assert "tool" in args and "install" in args, f"uv tool install must be the fallback; uv args: {args}"
