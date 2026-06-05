from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
INSTALL_SH = REPO / "install.sh"


# ---------------------------------------------------------------------------
# Static assertions — no network, no actual install.
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


def test_install_sh_webkitgtk_hint() -> None:
    content = INSTALL_SH.read_text(encoding="utf-8")
    assert "WebKitGTK" in content or "webkit" in content.lower(), (
        "install.sh must include a WebKitGTK installation hint"
    )
    # At minimum the Debian/Ubuntu package name must appear
    assert "gir1.2-webkit2-4.1" in content


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
# Integration smoke — fake uv/curl/gh; never touches network.
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
