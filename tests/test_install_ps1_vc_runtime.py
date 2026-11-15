"""Real-pwsh tests for install.ps1's Windows-only helper functions."""

from __future__ import annotations

import struct
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

INSTALLER = Path(__file__).resolve().parents[1] / "install.ps1"

LOAD_FUNCTIONS = f"""
$ErrorActionPreference = "Stop"
$InstallerAst = [System.Management.Automation.Language.Parser]::ParseFile(
    '{INSTALLER}', [ref]$null, [ref]$null)
$Definitions = $InstallerAst.FindAll({{
    param($Node)
    $Node -is [System.Management.Automation.Language.FunctionDefinitionAst]
}}, $false)
foreach ($Definition in $Definitions) {{
    . ([scriptblock]::Create($Definition.Extent.Text))
}}
"""

# Root of the real vc_redist.x64.exe 14.52.37029 chain, read on 2026-11-13.
MICROSOFT_ROOT_2011 = "8F43288AD272F3103B6FB1428485EA3014C0BCFE"

MICROSOFT_SIGNER = "CN=Microsoft Corporation, O=Microsoft Corporation, L=Redmond, S=Washington, C=US"


def run_pwsh(body: str, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    script = tmp_path / "case.ps1"
    _ = script.write_text(LOAD_FUNCTIONS + body, encoding="utf-8")
    return subprocess.run(
        ["pwsh", "-NoProfile", "-NonInteractive", "-File", str(script)],
        capture_output=True,
        text=True,
        check=False,
        cwd=tmp_path,
    )


def _pe_bytes(major: int, minor: int) -> bytes:
    """Smallest file Get-PeLinkerVersion accepts: DOS stub, PE signature,"""
    data = bytearray(0x40 + 28)
    data[0:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 0x40)
    data[0x40:0x44] = b"PE\0\0"
    struct.pack_into("<H", data, 0x40 + 24, 0x20B)
    data[0x40 + 26] = major
    data[0x40 + 27] = minor
    return bytes(data)


def _fake_shell(tmp_path: Path, exit_code: int) -> Path:
    shell = tmp_path / "fake-powershell"
    _ = shell.write_text(
        f'#!/bin/sh\nprintf "%s\\n" "$@" > {tmp_path / "shell.log"}\nexit {exit_code}\n',
        encoding="utf-8",
    )
    shell.chmod(0o755)
    return shell


def test_uv_bootstrap_runs_in_a_child_shell_with_process_only_bypass(tmp_path: Path) -> None:
    """astral's installer calls `exit` on failure, which would close the"""
    shell = _fake_shell(tmp_path, 0)
    result = run_pwsh(f"Install-Uv -ShellPath '{shell}'\n'ok'", tmp_path)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "shell.log").read_text(encoding="utf-8").splitlines() == [
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        "irm https://astral.sh/uv/install.ps1 | iex",
    ]


def test_uv_bootstrap_failure_stops_the_installer(tmp_path: Path) -> None:
    shell = _fake_shell(tmp_path, 1)
    result = run_pwsh(f"$global:LASTEXITCODE = 0\nInstall-Uv -ShellPath '{shell}'\n'ok'", tmp_path)
    assert result.returncode != 0
    assert "The uv installer failed (exit code 1)" in result.stderr
    assert "ok" not in result.stdout


def test_native_runner_fails_when_command_cannot_start(tmp_path: Path) -> None:
    """A command that never starts must not inherit a stale exit code of 0."""
    result = run_pwsh(
        f"""
$global:LASTEXITCODE = 0
Invoke-NativeCaptured -FilePath '{tmp_path / "missing-uv"}' -ArgumentList @("tool", "install")
"returned"
""",
        tmp_path,
    )
    assert result.returncode != 0
    assert "Could not run" in result.stderr
    assert "returned" not in result.stdout


def test_uv_failure_classification(tmp_path: Path) -> None:
    # Texts are real uv 0.11.26 output (see tests/test_install_ps1.py).
    result = run_pwsh(
        """
$Http503 = "error: Request failed after 3 retries in 8.3s`n  Caused by: HTTP status server error (503 Service Unavailable)"
$Refused = "error: Request failed after 3 retries in 8.0s`n  Caused by: Connection refused (os error 111)"
$Auth401 = "  x No solution found when resolving dependencies:`nhint: An index URL could not be queried due to a lack of valid authentication credentials (401 Unauthorized)"
$NoVersion = "  x No solution found when resolving dependencies:`n  Because there is no version of markupsafe==0.0.1"
"{0} {1} {2} {3}" -f (Test-UvTransientFailure $Http503), (Test-UvTransientFailure $Refused),
    (Test-UvTransientFailure $Auth401), (Test-UvTransientFailure $NoVersion)
""",
        tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == ["True", "True", "False", "False"]


def test_pe_linker_version_reads_header_and_rejects_other_files(tmp_path: Path) -> None:
    _ = (tmp_path / "c10.dll").write_bytes(_pe_bytes(14, 42))
    _ = (tmp_path / "notes.dll").write_bytes(b"not a PE image at all, just text" * 4)
    result = run_pwsh(
        f"""
"$(Get-PeLinkerVersion -Path '{tmp_path / "c10.dll"}')"
"[$(Get-PeLinkerVersion -Path '{tmp_path / "notes.dll"}')]"
""",
        tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == ["14.42", "[]"]


def test_toolset_floor_is_newest_msvc_binary_except_runtime_copies(tmp_path: Path) -> None:
    env = tmp_path / "env"
    (env / "Lib" / "site-packages" / "torch" / "lib").mkdir(parents=True)
    lib = env / "Lib" / "site-packages" / "torch" / "lib"
    _ = (lib / "c10.dll").write_bytes(_pe_bytes(14, 42))
    _ = (lib / "libiomp5md.dll").write_bytes(_pe_bytes(14, 29))
    # A bundled runtime copy and a non-MSVC linker must not raise the floor.
    _ = (lib / "msvcp140.dll").write_bytes(_pe_bytes(14, 50))
    _ = (lib / "vcruntime140_1.dll").write_bytes(_pe_bytes(14, 50))
    _ = (env / "Lib" / "site-packages" / "mingw.pyd").write_bytes(_pe_bytes(2, 40))
    _ = (env / "Lib" / "site-packages" / "readme.txt").write_bytes(_pe_bytes(14, 99))
    result = run_pwsh(
        f"""
$Floor = Get-MsvcToolsetFloor -EnvironmentPath '{env}'
"$($Floor.Version)"
Split-Path -Leaf $Floor.File
""",
        tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == ["14.42", "c10.dll"]


def test_toolset_floor_reports_missing_environment(tmp_path: Path) -> None:
    result = run_pwsh(
        f"""
$Floor = Get-MsvcToolsetFloor -EnvironmentPath '{tmp_path / "absent"}'
"[$($Floor.Version)] $($Floor.Found)"
""",
        tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "[] False"


def test_toolset_floor_skips_unreadable_files(tmp_path: Path) -> None:
    env = tmp_path / "env"
    env.mkdir()
    _ = (env / "good.pyd").write_bytes(_pe_bytes(14, 44))
    locked = env / "locked.dll"
    _ = locked.write_bytes(_pe_bytes(14, 99))
    locked.chmod(0o000)
    try:
        result = run_pwsh(
            f"""
$Floor = Get-MsvcToolsetFloor -EnvironmentPath '{env}'
"$($Floor.Version)"
""",
            tmp_path,
        )
    finally:
        locked.chmod(0o644)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "14.44"


def test_toolset_floor_is_empty_without_msvc_binaries(tmp_path: Path) -> None:
    (tmp_path / "env").mkdir()
    result = run_pwsh(
        f"""
$Floor = Get-MsvcToolsetFloor -EnvironmentPath '{tmp_path / "env"}'
"[$($Floor.Version)]"
""",
        tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "[]"


def _status(tmp_path: Path, versions: Mapping[str, str | None], minimum: str) -> list[str]:
    entries = "; ".join(
        f"'{name}' = " + (f"[version]'{v}'" if v else "$null") for name, v in versions.items()
    )
    result = run_pwsh(
        f"""
function Get-VcRuntimeFileVersions {{ [ordered]@{{ {entries} }} }}
$Minimum = {f"[version]'{minimum}'" if minimum else "$null"}
$S = Get-VcRuntimeStatus -Minimum $Minimum
"$($S.Adequate)|$($S.Installed)|$($S.Missing -join ',')"
""",
        tmp_path,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip().split("|")


ALL_14_44 = {"msvcp140.dll": "14.44", "vcruntime140.dll": "14.44", "vcruntime140_1.dll": "14.44"}


def test_status_adequate_when_all_dlls_meet_floor(tmp_path: Path) -> None:
    assert _status(tmp_path, ALL_14_44, "14.42") == ["True", "14.44", ""]


def test_status_inadequate_when_a_dll_is_missing(tmp_path: Path) -> None:
    versions = {**ALL_14_44, "msvcp140.dll": None}
    assert _status(tmp_path, versions, "14.42") == ["False", "14.44", "msvcp140.dll"]


def test_status_inadequate_when_oldest_dll_is_below_floor(tmp_path: Path) -> None:
    versions = {**ALL_14_44, "msvcp140.dll": "14.29"}
    assert _status(tmp_path, versions, "14.42") == ["False", "14.29", ""]


def test_status_without_floor_only_needs_the_dlls(tmp_path: Path) -> None:
    versions = dict.fromkeys(ALL_14_44, "14.0")
    assert _status(tmp_path, versions, "") == ["True", "14.0", ""]


def _install(
    tmp_path: Path,
    *,
    exit_code: str = "0",
    status: str = "Valid",
    organizations: str = "'Microsoft Corporation'",
    root: str = MICROSOFT_ROOT_2011,
    start_error: str = "",
) -> subprocess.CompletedProcess[str]:
    start_body = start_error or exit_code
    return run_pwsh(
        f"""
function Invoke-WebRequest {{
    param([string]$Uri, [string]$OutFile, [switch]$UseBasicParsing)
    Add-Content -Path calls.log -Value "download $Uri basic=$UseBasicParsing"
    Set-Content -Path $OutFile -Value "fake exe"
}}
function Get-AuthenticodeSignature {{
    param([string]$FilePath)
    [pscustomobject]@{{
        Status = "{status}"
        SignerCertificate = [pscustomobject]@{{ Subject = "{MICROSOFT_SIGNER}" }}
    }}
}}
function Get-CertificateOrganizations {{ param($Certificate) @({organizations}) }}
function Get-CertificateRootThumbprint {{ param($Certificate) "{root}" }}
function Start-ElevatedInstaller {{
    param([string]$FilePath, [string]$Arguments)
    Add-Content -Path calls.log -Value "start $(Split-Path -Leaf $FilePath) $Arguments"
    {start_body}
}}
$Outcome = Install-VcRuntime -WorkDir '{tmp_path}'
"outcome=$Outcome"
""",
        tmp_path,
    )


def _calls(tmp_path: Path) -> list[str]:
    log = tmp_path / "calls.log"
    return log.read_text(encoding="utf-8").splitlines() if log.exists() else []


def test_install_runs_signed_official_redistributable_elevated(tmp_path: Path) -> None:
    result = _install(tmp_path)
    assert result.returncode == 0, result.stderr
    assert "outcome=installed" in result.stdout
    assert _calls(tmp_path) == [
        "download https://aka.ms/vc14/vc_redist.x64.exe basic=True",
        "start vc_redist.x64.exe /install /passive /norestart",
    ]


def test_install_reports_restart_without_restarting(tmp_path: Path) -> None:
    result = _install(tmp_path, exit_code="3010")
    assert result.returncode == 0, result.stderr
    assert "outcome=restart-required" in result.stdout


def test_install_treats_already_installed_as_installed(tmp_path: Path) -> None:
    result = _install(tmp_path, exit_code="1638")
    assert result.returncode == 0, result.stderr
    assert "outcome=installed" in result.stdout


def test_install_fails_on_installer_cancel_and_error_codes(tmp_path: Path) -> None:
    cancelled_dir = tmp_path / "a"
    cancelled_dir.mkdir()
    cancelled = _install(cancelled_dir, exit_code="1602")
    assert cancelled.returncode != 0
    assert "cancelled (exit code 1602)" in cancelled.stderr
    failed_dir = tmp_path / "b"
    failed_dir.mkdir()
    failed = _install(failed_dir, exit_code="1603")
    assert failed.returncode != 0
    assert "failed with exit code 1603" in failed.stderr


def test_install_explains_access_denied_for_standard_user(tmp_path: Path) -> None:
    """Real result on Windows 11 with UAC off: a standard user gets exit 5."""
    result = _install(tmp_path, exit_code="5")
    assert result.returncode != 0
    assert "denied access (exit code 5)" in result.stderr
    assert "administrator account" in result.stderr


def test_install_reports_cancelled_uac_prompt(tmp_path: Path) -> None:
    result = _install(
        tmp_path,
        # Process.Start called from PowerShell surfaces as a
        # MethodInvocationException wrapping the Win32Exception.
        start_error=(
            "throw [System.Management.Automation.MethodInvocationException]::new("
            '"Exception calling Start", [System.ComponentModel.Win32Exception]::new(1223))'
        ),
    )
    assert result.returncode != 0
    assert "administrator prompt was cancelled" in result.stderr


def test_install_reports_other_start_failures_as_such(tmp_path: Path) -> None:
    result = _install(tmp_path, start_error='throw "file vanished"')
    assert result.returncode != 0
    assert "could not be started: file vanished" in result.stderr


def test_install_fails_without_exit_code(tmp_path: Path) -> None:
    result = _install(tmp_path, exit_code="$null")
    assert result.returncode != 0
    assert "did not report an exit code" in result.stderr


def test_install_never_runs_an_unsigned_download(tmp_path: Path) -> None:
    result = _install(tmp_path, status="NotSigned")
    assert result.returncode != 0
    assert "not validly signed" in result.stderr
    assert not any(c.startswith("start ") for c in _calls(tmp_path))


def test_install_never_runs_a_download_signed_by_someone_else(tmp_path: Path) -> None:
    for name, organizations in [
        ("other", "'Evil Corp'"),
        ("lower", "'microsoft corporation'"),
        ("two", "'Microsoft Corporation', 'Evil Corp'"),
        ("none", ""),
    ]:
        case = tmp_path / name
        case.mkdir()
        result = _install(case, organizations=organizations)
        assert result.returncode != 0, name
        assert "not Microsoft Corporation" in result.stderr, name
        assert not any(c.startswith("start ") for c in _calls(case)), name


def test_install_never_runs_a_download_from_another_root(tmp_path: Path) -> None:
    result = _install(tmp_path, root="0000000000000000000000000000000000000000")
    assert result.returncode != 0
    assert "not Microsoft Root Certificate Authority 2011" in result.stderr
    assert not any(c.startswith("start ") for c in _calls(tmp_path))


def _real_cert(subject: str) -> str:
    """PowerShell that builds a real self-signed certificate as $Cert."""
    return f"""
$Key = [System.Security.Cryptography.RSA]::Create(2048)
$Request = [System.Security.Cryptography.X509Certificates.CertificateRequest]::new(
    '{subject}', $Key, [System.Security.Cryptography.HashAlgorithmName]::SHA256,
    [System.Security.Cryptography.RSASignaturePadding]::Pkcs1)
$Cert = $Request.CreateSelfSigned([DateTimeOffset]::Now.AddDays(-1), [DateTimeOffset]::Now.AddDays(1))
"""


def test_certificate_organizations_reads_real_subject_fields(tmp_path: Path) -> None:
    result = run_pwsh(
        _real_cert("CN=Microsoft Corporation, O=Microsoft Corporation, L=Redmond, C=US")
        + "(Get-CertificateOrganizations -Certificate $Cert) -join '|'",
        tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "Microsoft Corporation"


def test_certificate_organizations_ignores_o_inside_quoted_values(tmp_path: Path) -> None:
    result = run_pwsh(
        _real_cert('CN="x, O=Microsoft Corporation, y", O=Evil Corp, C=US')
        + "(Get-CertificateOrganizations -Certificate $Cert) -join '|'",
        tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "Evil Corp"


def test_root_thumbprint_of_self_signed_certificate_is_its_own(tmp_path: Path) -> None:
    result = run_pwsh(
        _real_cert("CN=Test Root, O=Test")
        + "(Get-CertificateRootThumbprint -Certificate $Cert) -eq $Cert.Thumbprint",
        tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "True"


def _confirm(
    tmp_path: Path, statuses: list[str], install_result: str = "installed", skip: bool = False
) -> subprocess.CompletedProcess[str]:
    """`statuses` are successive Get-VcRuntimeStatus answers, as"""
    answers = ", ".join(f"'{s}'" for s in statuses)
    install_body = f'"{install_result}"' if install_result != "throw" else 'throw "prompt refused"'
    skip_line = (
        '$env:PD_SIMPLE_GUI_SKIP_VC_RUNTIME = "1"' if skip else "$env:PD_SIMPLE_GUI_SKIP_VC_RUNTIME = $null"
    )
    return run_pwsh(
        f"""
{skip_line}
$script:Answers = @({answers})
$script:Asked = 0
function Get-MsvcToolsetFloor {{
    param([string]$EnvironmentPath)
    [pscustomobject]@{{ Version = [version]'14.42'; File = 'C:\\env\\torch\\lib\\c10.dll'; Found = $true }}
}}
function Get-VcRuntimeStatus {{
    param([version]$Minimum)
    $Parts = $script:Answers[$script:Asked].Split('|')
    $script:Asked++
    [pscustomobject]@{{
        Adequate = [bool]::Parse($Parts[0])
        Installed = $(if ($Parts[1]) {{ [version]$Parts[1] }} else {{ $null }})
        Missing = @($Parts[2].Split(',') | Where-Object {{ $_ }})
        Minimum = $Minimum
    }}
}}
function Install-VcRuntime {{
    param([string]$WorkDir)
    Add-Content -Path calls.log -Value "install"
    {install_body}
}}
$Restart = Confirm-VcRuntime -EnvironmentPath 'C:\\env' -WorkDir '{tmp_path}'
"restart=$Restart"
""",
        tmp_path,
    )


def test_confirm_skips_install_when_runtime_is_adequate(tmp_path: Path) -> None:
    result = _confirm(tmp_path, ["True|14.44|"])
    assert result.returncode == 0, result.stderr
    assert "restart=False" in result.stdout
    assert "14.42 or newer" in result.stdout
    assert _calls(tmp_path) == []


def test_confirm_installs_missing_runtime_and_rechecks(tmp_path: Path) -> None:
    result = _confirm(tmp_path, ["False||msvcp140.dll", "True|14.50|"])
    assert result.returncode == 0, result.stderr
    assert "msvcp140.dll not found" in result.stdout
    assert "restart=False" in result.stdout
    assert _calls(tmp_path) == ["install"]


def test_confirm_installs_when_runtime_is_older_than_floor(tmp_path: Path) -> None:
    result = _confirm(tmp_path, ["False|14.29|", "True|14.50|"])
    assert result.returncode == 0, result.stderr
    assert "older than 14.42" in result.stdout
    assert "c10.dll" in result.stdout


def test_confirm_reports_restart_required(tmp_path: Path) -> None:
    result = _confirm(tmp_path, ["False||msvcp140.dll"], install_result="restart-required")
    assert result.returncode == 0, result.stderr
    assert "restart=True" in result.stdout


def test_confirm_fails_with_manual_steps_when_install_is_refused(tmp_path: Path) -> None:
    result = _confirm(tmp_path, ["False||msvcp140.dll"], install_result="throw")
    assert result.returncode != 0
    assert "https://aka.ms/vc14/vc_redist.x64.exe" in result.stdout
    assert "/install /passive /norestart" in result.stdout
    assert "pdomain-ocr-simple-gui is installed, but OCR cannot run yet" in result.stderr


def test_confirm_fails_when_a_dll_is_still_missing_after_install(tmp_path: Path) -> None:
    result = _confirm(tmp_path, ["False||msvcp140.dll", "False||msvcp140.dll"])
    assert result.returncode != 0
    assert "msvcp140.dll is still missing" in result.stderr


def test_confirm_warns_when_newest_runtime_is_older_than_floor(tmp_path: Path) -> None:
    """Warn when the newest runtime cannot meet the installed toolset floor."""
    result = _confirm(tmp_path, ["False|14.29|", "False|14.50|"])
    assert result.returncode == 0, result.stderr
    assert "WARNING: Visual C++ runtime 14.50 is the newest" in result.stdout
    assert "restart=False" in result.stdout


def test_confirm_honours_skip_variable_without_installing(tmp_path: Path) -> None:
    result = _confirm(tmp_path, ["False||msvcp140.dll"], skip=True)
    assert result.returncode != 0
    assert "PD_SIMPLE_GUI_SKIP_VC_RUNTIME=1" in result.stderr
    assert _calls(tmp_path) == []


def _fake_uv_tool_dir(tmp_path: Path, exit_code: int) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    uv = bin_dir / "uv"
    _ = uv.write_text(f"#!/bin/sh\necho '{tmp_path / 'tools'}'\nexit {exit_code}\n")
    uv.chmod(0o755)


def _complete(tmp_path: Path, exit_code: int, *, linked: bool = True) -> subprocess.CompletedProcess[str]:
    _fake_uv_tool_dir(tmp_path, exit_code)
    scripts = tmp_path / "tools" / "pdomain-ocr-simple-gui" / "Scripts"
    scripts.mkdir(parents=True)
    (scripts / "python.exe").touch()
    (scripts / "pdomain-ocr-simple-gui.exe").touch()
    if linked:
        (tmp_path / "tools" / "pdomain-ocr-simple-gui.exe").touch()
    return run_pwsh(
        f"""
$env:PATH = '{tmp_path / "bin"}' + [IO.Path]::PathSeparator + $env:PATH
function Confirm-VcRuntime {{
    param([string]$EnvironmentPath, [string]$WorkDir)
    Add-Content -Path checked.log -Value $EnvironmentPath
    $true
}}
$Restart = Complete-WindowsInstall -WorkDir '{tmp_path}'
"restart=$Restart"
""",
        tmp_path,
    )


def test_windows_step_checks_the_pdomain_tool_environment(tmp_path: Path) -> None:
    result = _complete(tmp_path, 0)
    assert result.returncode == 0, result.stderr
    checked = (tmp_path / "checked.log").read_text(encoding="utf-8").strip()
    assert checked == str(tmp_path / "tools" / "pdomain-ocr-simple-gui")
    assert "restart=True" in result.stdout


def test_windows_step_fails_when_uv_tool_dir_fails(tmp_path: Path) -> None:
    result = _complete(tmp_path, 2)
    assert result.returncode != 0
    assert "'uv tool dir' failed with exit code 2" in result.stderr


def test_summary_tells_user_to_restart_without_restarting(tmp_path: Path) -> None:
    result = run_pwsh(
        "Write-InstallSummary -RestartRequired $true\nWrite-InstallSummary -RestartRequired $false",
        tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert "Done, but Windows must restart before OCR can run" in result.stdout
    assert "never restarts Windows" in result.stdout
    assert result.stdout.count("Done!") == 1


def test_elevated_start_uses_process_start_with_runas() -> None:
    """Start-ElevatedInstaller must use Process.Start, which keeps the 1223"""
    script = INSTALLER.read_text(encoding="utf-8")
    body = script[script.index("function Start-ElevatedInstaller") :]
    body = body[: body.index("\nfunction ")]
    assert "[System.Diagnostics.Process]::Start($Info)" in body
    assert '$Info.Verb = "runas"' in body


def test_uac_cancel_detection_walks_the_exception_chain(tmp_path: Path) -> None:
    result = run_pwsh(
        """
$Inner = [System.ComponentModel.Win32Exception]::new(1223)
$Wrapped = [System.Management.Automation.MethodInvocationException]::new("x", $Inner)
$Deep = [System.InvalidOperationException]::new("y", $Wrapped)
$Other = [System.ComponentModel.Win32Exception]::new(2)
"{0} {1} {2}" -f (Test-UacCancelled $Wrapped), (Test-UacCancelled $Deep), (Test-UacCancelled $Other)
""",
        tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == ["True", "True", "False"]


def test_windows_step_rejects_incomplete_tool_install(tmp_path: Path) -> None:
    _fake_uv_tool_dir(tmp_path, 0)
    result = run_pwsh(
        f"$env:PATH='{tmp_path / 'bin'}' + [IO.Path]::PathSeparator + $env:PATH; Complete-WindowsInstall -WorkDir '{tmp_path}'",
        tmp_path,
    )
    assert result.returncode != 0
    assert "incomplete" in result.stderr.lower()


def test_windows_step_rejects_missing_launch_command(tmp_path: Path) -> None:
    result = _complete(tmp_path, 0, linked=False)
    assert result.returncode != 0
    assert "launch command" in result.stderr.lower()
