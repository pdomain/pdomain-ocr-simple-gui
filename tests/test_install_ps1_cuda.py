"""Real-pwsh tests for scripts/install-cuda-detect.ps1."""

from __future__ import annotations

import subprocess
from pathlib import Path

LIB = Path(__file__).parents[1] / "scripts" / "install-cuda-detect.ps1"


def _pwsh(body: str) -> subprocess.CompletedProcess[str]:
    script = f". '{LIB}'\n{body}"
    return subprocess.run(
        ["pwsh", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        check=True,
    )


def test_get_book_tools_extras_gpu_at_cuda_13():
    assert _pwsh("Get-BookToolsExtras '13.0'").stdout.strip() == "[gpu]"
    assert _pwsh("Get-BookToolsExtras '13.1'").stdout.strip() == "[gpu]"


def test_get_book_tools_extras_empty_below_cuda_13():
    assert _pwsh("Get-BookToolsExtras '12.8'").stdout.strip() == ""
    assert _pwsh("Get-BookToolsExtras '12.4'").stdout.strip() == ""
    assert _pwsh("Get-BookToolsExtras '12.1'").stdout.strip() == ""


def test_get_cuda_version_env_override():
    assert _pwsh("$env:CUDA_VERSION='12.6'; Get-CudaVersion").stdout.strip() == "12.6"


def test_get_cuda_version_parses_smi_q_output():
    body = (
        "$env:CUDA_VERSION=$null\n"
        "function nvidia-smi { 'CUDA Version                          : 12.4' }\n"
        "Get-CudaVersion"
    )
    # The shadowed function ignores $args, so both the -q and plain calls return
    # the same string; the -q regex matches first and returns "12.4".
    assert _pwsh(body).stdout.strip() == "12.4"


def test_get_cuda_version_parses_plain_smi_header():
    body = (
        "$env:CUDA_VERSION=$null\n"
        "function nvidia-smi { if ($args -contains '-q') { '' } "
        "else { '| NVIDIA-SMI ... CUDA Version: 12.2   |' } }\n"
        "Get-CudaVersion"
    )
    # -q branch returns '' (no match); plain branch returns the header with 12.2.
    assert _pwsh(body).stdout.strip() == "12.2"


def test_get_cuda_version_null_when_smi_gives_nothing():
    body = "$env:CUDA_VERSION=$null\nfunction nvidia-smi { '' }\nGet-CudaVersion"
    # Both -q and plain branches get '' — neither regex matches — function returns
    # $null. PowerShell writes nothing to stdout for a $null return value.
    assert _pwsh(body).stdout.strip() == ""


# NVIDIA driver 615 prints "CUDA UMD Version" in the banner and marks the old
# "CUDA Version" field in `nvidia-smi -q` as deprecated, to be removed in CUDA 14.
UMD_BANNER = "| NVIDIA-SMI 615.78.08   KMD Version: 615.78.08     CUDA UMD Version: 13.4     |"


def test_get_cuda_version_parses_umd_banner():
    body = (
        "$env:CUDA_VERSION=$null\n"
        "function nvidia-smi { if ($args -contains '-q') { '' } "
        f"else {{ '{UMD_BANNER}' }} }}\n"
        "Get-CudaVersion"
    )
    assert _pwsh(body).stdout.strip() == "13.4"


def test_get_cuda_version_parses_umd_query_field():
    body = (
        "$env:CUDA_VERSION=$null\n"
        "function nvidia-smi { 'CUDA UMD Version                      : 14.0' }\n"
        "Get-CudaVersion"
    )
    assert _pwsh(body).stdout.strip() == "14.0"


def test_install_ps1_parses_umd_banner(tmp_path: Path) -> None:
    from tests.test_install_ps1_vc_runtime import run_pwsh as installer_pwsh

    body = (
        "$env:CUDA_VERSION=$null\n"
        "function nvidia-smi { if ($args -contains '-q') { '' } "
        f"else {{ '{UMD_BANNER}' }} }}\n"
        "Get-CudaVersion"
    )
    result = installer_pwsh(body, tmp_path)
    assert result.stdout.strip() == "13.4", result.stderr
