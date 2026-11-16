from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# The fake Invoke-WebRequest below writes exactly these bytes (no trailing
# newline: -NoNewline) to the wheel file it is asked to download, so tests
# can assert digest verification against a known hash without hardcoding a
# magic value.
FAKE_WHEEL_BYTES = b"fake wheel"
FAKE_WHEEL_DIGEST = f"sha256:{hashlib.sha256(FAKE_WHEEL_BYTES).hexdigest()}"
MISMATCHED_DIGEST = f"sha256:{hashlib.sha256(b'different bytes').hexdigest()}"


def _write_fake_exe(path: Path, body: str) -> None:
    _ = path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def _run_install_ps1(
    tmp_path: Path, digest_property: str, cuda_version: str | None = "12.4"
) -> tuple[subprocess.CompletedProcess[str], Path]:
    result, uv_log, _perm_log = _run_install_ps1_full(tmp_path, digest_property, cuda_version=cuda_version)
    return result, uv_log


def _run_install_ps1_full(
    tmp_path: Path,
    digest_property: str,
    *,
    umask: int | None = None,
    cuda_version: str | None = "12.4",
    uv_exit_logic: str = "exit 0",
    release_version: str | None = None,
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    """Run install.ps1 through pwsh with mocked GitHub API + uv + nvidia-smi."""
    release_endpoint = "latest" if release_version is None else f"tags/v{release_version}"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    uv_log = tmp_path / "uv.log"
    perm_log = tmp_path / "perm.log"

    _write_fake_exe(
        bin_dir / "uv",
        f"""#!/bin/sh
n=$(cat {tmp_path / "uv.count"} 2>/dev/null || echo 0)
n=$((n + 1))
echo "$n" > {tmp_path / "uv.count"}
if [ "$n" -gt 1 ]; then echo "--call--" >> {uv_log}; fi
printf '%s\\n' "$@" >> {uv_log}
for a in "$@"; do
  if [ -f "$a" ]; then
    stat -c '%a' "$(dirname "$a")" > {perm_log} 2>/dev/null || true
    break
  fi
done
{uv_exit_logic}
""",
    )
    smi_output = (
        f"printf '%s\\n' 'CUDA Version                          : {cuda_version}'"
        if cuda_version is not None
        else ":"
    )
    _write_fake_exe(
        bin_dir / "nvidia-smi",
        f"""#!/bin/sh
{smi_output}
exit 0
""",
    )

    script = (REPO / "install.ps1").read_text(encoding="utf-8")
    escaped_script = script.replace("'@", "' + \"@\" + '")
    harness = tmp_path / "run.ps1"
    _ = harness.write_text(
        f"""
$ErrorActionPreference = "Stop"
function Invoke-RestMethod {{
  param([string]$Uri)
  if ($Uri -like "*api.github.com/repos/pdomain/pdomain-ocr-simple-gui/releases/{release_endpoint}*") {{
    return [pscustomobject]@{{
      tag_name = "v9.9.9"
      assets = @([pscustomobject]@{{
        name = "pdomain_ocr_simple_gui-9.9.9-py3-none-any.whl"
        browser_download_url = "https://example.invalid/pdomain_ocr_simple_gui-9.9.9-py3-none-any.whl"
        {digest_property}
      }})
    }}
  }}
  throw "unexpected Invoke-RestMethod: $Uri"
}}
function Invoke-WebRequest {{
  param([string]$Uri, [string]$OutFile, [switch]$UseBasicParsing)
  if ($Uri -ne "https://example.invalid/pdomain_ocr_simple_gui-9.9.9-py3-none-any.whl") {{
    throw "unexpected Invoke-WebRequest: $Uri"
  }}
  Set-Content -Path $OutFile -Value "fake wheel" -NoNewline
}}
function irm {{
  param([string]$Uri)
  throw "unexpected irm: $Uri"
}}
function Start-Sleep {{
  param([int]$Seconds)
  Add-Content -Path "{tmp_path / "sleep.log"}" -Value $Seconds
}}
$InstallerText = @'
{escaped_script}
'@
Invoke-Expression $InstallerText
""",
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
    env["PD_SIMPLE_GUI_INSTALL_PYTHON"] = "3.12"
    _ = env.pop("CUDA_VERSION", None)
    _ = env.pop("PD_SIMPLE_GUI_INSTALL_VERSION", None)
    if release_version is not None:
        env["PD_SIMPLE_GUI_INSTALL_VERSION"] = release_version
    preexec_fn = (lambda: os.umask(umask)) if umask is not None else None
    result = subprocess.run(
        ["pwsh", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(harness)],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        preexec_fn=preexec_fn,
    )
    return result, uv_log, perm_log


def _assert_torch_backend_auto(args: str) -> None:
    """uv picks the PyTorch CUDA build itself; no PyTorch index is passed."""
    assert "--torch-backend\nauto" in args
    assert "pytorch-cuda" not in args
    assert "download.pytorch.org" not in args


def test_install_ps1_piped_mode_is_self_contained_and_uses_release_wheel(
    tmp_path: Path,
) -> None:
    result, uv_log = _run_install_ps1(tmp_path, f'digest = "{FAKE_WHEEL_DIGEST}"')

    assert result.returncode == 0, result.stderr + result.stdout
    args = uv_log.read_text(encoding="utf-8")
    assert "--python\n3.12" in args
    # Runtime proof (not just a text grep): --index-strategy first-index and
    # the pdomain binding actually reach `uv`, via a named --index (not the
    # deprecated --extra-index-url, which a hostile UV_INDEX env var beats).
    assert "--index-strategy\nfirst-index" in args
    assert "--index\npdomain=https://pdomain.github.io/pdomain-index-pip/simple/" in args
    assert "--extra-index-url" not in args
    assert "pdomain_ocr_simple_gui-9.9.9-py3-none-any.whl" in args
    assert "git+https://github.com/pdomain/pdomain-ocr-simple-gui" not in args
    # This harness's fake nvidia-smi reports CUDA 12.4 by default: uv picks
    # the PyTorch CUDA build and does not install CuPy.
    _assert_torch_backend_auto(args)
    assert "--with" not in args


def test_install_ps1_cuda_13_uses_torch_backend_without_cupy(tmp_path: Path) -> None:
    result, uv_log = _run_install_ps1(tmp_path, f'digest = "{FAKE_WHEEL_DIGEST}"', cuda_version="13.0")

    assert result.returncode == 0, result.stderr + result.stdout
    args = uv_log.read_text(encoding="utf-8")
    _assert_torch_backend_auto(args)
    assert "--with" not in args


def test_install_ps1_without_cuda_passes_no_torch_backend(tmp_path: Path) -> None:
    result, uv_log = _run_install_ps1(tmp_path, f'digest = "{FAKE_WHEEL_DIGEST}"', cuda_version=None)

    assert result.returncode == 0, result.stderr + result.stdout
    args = uv_log.read_text(encoding="utf-8")
    assert "--torch-backend" not in args
    assert "pytorch-cuda" not in args
    assert "--with" not in args
    combined = result.stdout + result.stderr
    assert "https://www.nvidia.com/en-us/drivers/" in combined
    assert "docs/usage/nvidia-gpu-setup.md" in combined


def test_install_ps1_uses_first_index_strategy() -> None:
    script = (REPO / "install.ps1").read_text(encoding="utf-8")
    assert '"--index-strategy", "first-index"' in script


def test_install_ps1_unix_file_mode_skips_windows_powershell_5() -> None:
    """Windows PowerShell 5.1 leaves $IsWindows unset. The Unix mode branch"""
    script = (REPO / "install.ps1").read_text(encoding="utf-8")
    assert "if ($PSVersionTable.PSVersion.Major -ge 6 -and -not $IsWindows)" in script


def test_install_ps1_aborts_when_digest_is_missing(tmp_path: Path) -> None:
    result, uv_log = _run_install_ps1(tmp_path, "")

    assert result.returncode != 0
    assert not uv_log.exists()


def test_install_ps1_aborts_when_digest_is_malformed(tmp_path: Path) -> None:
    result, uv_log = _run_install_ps1(tmp_path, 'digest = "sha256:not-hex"')

    assert result.returncode != 0
    assert not uv_log.exists()


def test_install_ps1_aborts_when_digest_does_not_match_downloaded_bytes(
    tmp_path: Path,
) -> None:
    result, uv_log = _run_install_ps1(tmp_path, f'digest = "{MISMATCHED_DIGEST}"')

    assert result.returncode != 0
    assert not uv_log.exists()


def test_install_ps1_aborts_when_digest_is_uppercase_hex(tmp_path: Path) -> None:
    # PowerShell's `-notmatch` is case-INSENSITIVE, so a naive regex check
    # would accept uppercase hex here even though install.sh's `grep` (case
    # sensitive) rejects it for the same bytes. The spec requires exactly 64
    # lowercase hex characters, and both installers must agree.
    uppercase_digest = f"sha256:{hashlib.sha256(FAKE_WHEEL_BYTES).hexdigest().upper()}"
    result, uv_log = _run_install_ps1(tmp_path, f'digest = "{uppercase_digest}"')

    assert result.returncode != 0
    assert not uv_log.exists()


def test_install_ps1_aborts_when_digest_has_surrounding_whitespace(tmp_path: Path) -> None:
    padded_digest = f" {FAKE_WHEEL_DIGEST} "
    result, uv_log = _run_install_ps1(tmp_path, f'digest = "{padded_digest}"')

    assert result.returncode != 0
    assert not uv_log.exists()


def test_install_ps1_aborts_when_digest_is_63_hex_chars(tmp_path: Path) -> None:
    truncated_digest = f"sha256:{hashlib.sha256(FAKE_WHEEL_BYTES).hexdigest()[:-1]}"
    result, uv_log = _run_install_ps1(tmp_path, f'digest = "{truncated_digest}"')

    assert result.returncode != 0
    assert not uv_log.exists()


def test_install_ps1_temp_dir_has_restrictive_permissions(tmp_path: Path) -> None:
    """MINOR C: New-Item's directory mode follows umask (could be as open as"""
    result, _uv_log, perm_log = _run_install_ps1_full(tmp_path, f'digest = "{FAKE_WHEEL_DIGEST}"', umask=0)
    assert result.returncode == 0, result.stderr + result.stdout
    assert perm_log.exists(), "fake uv never observed the wheel file's temp dir"
    assert perm_log.read_text(encoding="utf-8").strip() == "700"


def test_install_ps1_enables_tls12_before_any_web_request() -> None:
    """Windows PowerShell 5.1 may default to TLS versions GitHub refuses."""
    lines = (REPO / "install.ps1").read_text(encoding="utf-8").splitlines()
    code = [line.strip() for line in lines if not line.strip().startswith("#")]
    tls = next(i for i, line in enumerate(code) if "[Net.SecurityProtocolType]::Tls12" in line)
    web = next(i for i, line in enumerate(code) if "irm " in line or "Invoke-" in line)
    assert "-bor" in code[tls]
    assert tls < web


# Real uv output captured on 2026-11-13 from uv 0.11.26 against a local index
# that answered every request with HTTP 503. uv had already retried 3 times.
UV_TRANSIENT_FAILURE = """echo 'error: Request failed after 3 retries in 8.3s' >&2
echo '  Caused by: Failed to fetch: `https://pdomain.github.io/pdomain-index-pip/simple/markupsafe/`' >&2
echo '  Caused by: HTTP status server error (503 Service Unavailable)' >&2
exit 2"""

# Real uv output for a requirement no index can satisfy (exit code 1).
UV_PERMANENT_FAILURE = """echo '  x No solution found when resolving dependencies:' >&2
echo '  Because there is no version of markupsafe==0.0.1 we can conclude that your requirements are unsatisfiable.' >&2
exit 1"""


def _uv_calls(uv_log: Path) -> int:
    return uv_log.read_text(encoding="utf-8").count("--call--") + 1


def _sleeps(tmp_path: Path) -> list[str]:
    log = tmp_path / "sleep.log"
    return log.read_text(encoding="utf-8").split() if log.exists() else []


def test_install_ps1_fails_when_uv_fails(tmp_path: Path) -> None:
    """uv's exit code was ignored, so a failed install still printed Done."""
    result, uv_log, _perm = _run_install_ps1_full(
        tmp_path, f'digest = "{FAKE_WHEEL_DIGEST}"', uv_exit_logic=UV_PERMANENT_FAILURE
    )

    assert result.returncode != 0
    assert "Done" not in result.stdout
    assert "uv tool install failed with exit code 1" in result.stdout + result.stderr
    assert _uv_calls(uv_log) == 1
    assert _sleeps(tmp_path) == []
    # The finally block still removed the downloaded wheel's temp dir.
    wheel_arg = next(
        line for line in uv_log.read_text(encoding="utf-8").splitlines() if line.endswith(".whl")
    )
    assert not Path(wheel_arg).parent.exists()


def test_install_ps1_retries_uv_network_failure_then_succeeds(tmp_path: Path) -> None:
    logic = f'if [ "$n" -eq 1 ]; then\n{UV_TRANSIENT_FAILURE}\nfi\nexit 0'
    result, uv_log, _perm = _run_install_ps1_full(
        tmp_path, f'digest = "{FAKE_WHEEL_DIGEST}"', uv_exit_logic=logic
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert _uv_calls(uv_log) == 2
    assert _sleeps(tmp_path) == ["15"]
    assert "attempt 1 of 3" in result.stdout
    assert "Done!" in result.stdout


def test_install_ps1_stops_after_three_network_failures(tmp_path: Path) -> None:
    result, uv_log, _perm = _run_install_ps1_full(
        tmp_path, f'digest = "{FAKE_WHEEL_DIGEST}"', uv_exit_logic=UV_TRANSIENT_FAILURE
    )

    assert result.returncode != 0
    assert _uv_calls(uv_log) == 3
    assert _sleeps(tmp_path) == ["15", "45"]
    assert "after 3 attempts because of network errors" in result.stdout + result.stderr
    assert "Done" not in result.stdout


def test_install_ps1_does_not_retry_resolver_failure(tmp_path: Path) -> None:
    """A 401 index also ends in "No solution found": never retry that."""
    logic = (
        "echo 'error: Request failed after 3 retries' >&2\n"  # noise from one index
        + UV_PERMANENT_FAILURE
    )
    result, uv_log, _perm = _run_install_ps1_full(
        tmp_path, f'digest = "{FAKE_WHEEL_DIGEST}"', uv_exit_logic=logic
    )

    assert result.returncode != 0
    assert _uv_calls(uv_log) == 1
    assert _sleeps(tmp_path) == []


# What a uv without --torch-backend prints (clap's unknown-argument error).
UV_NO_TORCH_BACKEND = """echo "error: unexpected argument '--torch-backend' found" >&2
exit 2"""


def test_install_ps1_hints_uv_self_update_when_uv_lacks_torch_backend(tmp_path: Path) -> None:
    result, uv_log, _perm = _run_install_ps1_full(
        tmp_path, f'digest = "{FAKE_WHEEL_DIGEST}"', uv_exit_logic=UV_NO_TORCH_BACKEND
    )

    assert result.returncode != 0
    assert _uv_calls(uv_log) == 1
    assert _sleeps(tmp_path) == []
    assert "uv self update" in result.stdout + result.stderr
    assert "Done" not in result.stdout


def test_install_ps1_explicit_release_uses_tag_endpoint(tmp_path: Path) -> None:
    result, argv, _ = _run_install_ps1_full(
        tmp_path, f'digest = "{FAKE_WHEEL_DIGEST}"', release_version="0.5.7"
    )
    assert result.returncode == 0, result.stderr
    assert argv.exists()


def test_install_ps1_invalid_release_fails_before_network(tmp_path: Path) -> None:
    result, argv, _ = _run_install_ps1_full(
        tmp_path, f'digest = "{FAKE_WHEEL_DIGEST}"', release_version="latest/bad"
    )
    assert result.returncode != 0
    assert "PD_SIMPLE_GUI_INSTALL_VERSION" in result.stderr
    assert not argv.exists()
