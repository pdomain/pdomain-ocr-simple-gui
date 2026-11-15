# Install pdomain-ocr-simple-gui as a standalone tool using uv.
#
# Usage (run in PowerShell):
#   irm https://raw.githubusercontent.com/pdomain/pdomain-ocr-simple-gui/master/install.ps1 | iex
#
# Manual CUDA override (if auto-detection fails):
#   $env:CUDA_VERSION = "13.0"   # replace with your version
#   irm https://raw.githubusercontent.com/pdomain/pdomain-ocr-simple-gui/master/install.ps1 | iex
#
# Python override:
#   $env:PD_SIMPLE_GUI_INSTALL_PYTHON = "3.12"
#   irm https://raw.githubusercontent.com/pdomain/pdomain-ocr-simple-gui/master/install.ps1 | iex

$ErrorActionPreference = "Stop"

# Windows PowerShell 5.1 can default to TLS versions GitHub refuses. -bor keeps
# whatever else the session already allows.
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

function Get-CudaVersion {
    if ($env:CUDA_VERSION) {
        return $env:CUDA_VERSION
    }

    if (-not (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) {
        return $null
    }

    try {
        $Query = & nvidia-smi -q 2>$null | Out-String
        if ($Query -match "CUDA (?:UMD )?Version\s*:\s*([0-9]+\.[0-9]+)") {
            return $Matches[1]
        }
    } catch {
    }

    try {
        $Plain = & nvidia-smi 2>$null | Out-String
        if ($Plain -match "CUDA (?:UMD )?Version:\s*([0-9]+\.[0-9]+)") {
            return $Matches[1]
        }
    } catch {
    }

    return $null
}

function Get-BookToolsExtras {
    param([Parameter(Mandatory = $true)][string]$CudaVer)
    try {
        $Version = [version]$CudaVer
    } catch {
        return ""
    }
    if ($Version.Major -ge 13) {
        return "[gpu]"
    }
    return ""
}

# The functions below have no side effects when defined. Tests load them from
# this file's syntax tree and replace the cmdlets they call with fakes.

function Test-IsWindowsHost {
    # Windows PowerShell 5.1 has no $IsWindows; it only runs on Windows.
    return ($PSVersionTable.PSVersion.Major -lt 6) -or [bool]$IsWindows
}

function Install-Uv {
    # Run astral's uv installer in a child PowerShell, the command uv's own
    # documentation gives for Windows. That installer calls `exit 1` when it
    # fails, and under `irm | iex` an exit in this window would close it.
    # `-ExecutionPolicy Bypass` applies to the child process only; the
    # user's saved policy is not changed.
    param([string]$ShellPath = (Get-Process -Id $PID).Path)
    $global:LASTEXITCODE = $null
    & $ShellPath -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    if ($LASTEXITCODE -ne 0) {
        throw "The uv installer failed (exit code $LASTEXITCODE); see its message above. If your organization sets the PowerShell execution policy, ask an administrator to install uv: https://docs.astral.sh/uv/getting-started/installation/"
    }
}

function Invoke-NativeCaptured {
    # Run a native command, echo its stdout and stderr as it runs, and return
    # the exit code with the combined text. Stderr lines must not become
    # terminating errors, so the error preference is relaxed for this call.
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$ArgumentList = @()
    )
    $Lines = New-Object System.Collections.Generic.List[string]
    $PreviousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    # A command that never starts leaves $LASTEXITCODE at the previous
    # command's value, often 0, so clear it first.
    $global:LASTEXITCODE = $null
    try {
        try {
            & $FilePath @ArgumentList 2>&1 | ForEach-Object {
                $Line = "$_"
                Write-Host $Line
                $Lines.Add($Line)
            }
        } catch {
            throw "Could not run '$FilePath': $($_.Exception.Message)"
        }
        $ExitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $PreviousPreference
    }
    if ($null -eq $ExitCode) {
        throw "'$FilePath' did not report an exit code, so it may not have run."
    }
    return [pscustomobject]@{
        ExitCode = $ExitCode
        Output = ($Lines -join "`n")
    }
}

function Test-UvLacksTorchBackend {
    # A uv older than the --torch-backend option rejects it, for example
    # "unexpected argument '--torch-backend' found". Updating uv is the fix;
    # retrying cannot help.
    param([string]$Output)
    return $Output -match "torch-backend"
}

function Test-UvTransientFailure {
    # uv retries network errors itself and reports "Request failed after N
    # retries" once it gives up; that is the only failure worth retrying.
    # A resolver failure ("No solution found"), including one caused by a
    # 401/403 index, a hash mismatch or an incompatible Python, is permanent.
    param([string]$Output)
    if ($Output -match "No solution found") {
        return $false
    }
    return $Output -match "Request failed after \d+ retr"
}

function Invoke-UvToolInstall {
    # Run `uv tool install`, retrying only uv-reported network failures. uv
    # already retried each request three times; the extra attempts wait
    # longer, for an index that is down for a minute rather than a moment.
    param(
        [Parameter(Mandatory = $true)][string[]]$UvArgs,
        [int[]]$RetryDelaysSeconds = @(15, 45)
    )
    $MaxAttempts = $RetryDelaysSeconds.Count + 1
    for ($Attempt = 1; $Attempt -le $MaxAttempts; $Attempt++) {
        $Result = Invoke-NativeCaptured -FilePath "uv" -ArgumentList $UvArgs
        if ($Result.ExitCode -eq 0) {
            return
        }
        if (Test-UvLacksTorchBackend $Result.Output) {
            throw "uv tool install failed with exit code $($Result.ExitCode). pdomain-ocr-simple-gui was not installed. This uv is too old for the --torch-backend option, which picks the PyTorch CUDA build. Run: uv self update (or update uv with the package manager that installed it). Then run the installer again."
        }
        $Transient = Test-UvTransientFailure $Result.Output
        if (-not $Transient) {
            throw "uv tool install failed with exit code $($Result.ExitCode). pdomain-ocr-simple-gui was not installed. See the uv error above."
        }
        if ($Attempt -eq $MaxAttempts) {
            throw "uv tool install failed with exit code $($Result.ExitCode) after $MaxAttempts attempts because of network errors. pdomain-ocr-simple-gui was not installed. Check your connection, then run the installer again."
        }
        $Delay = $RetryDelaysSeconds[$Attempt - 1]
        Write-Host ""
        Write-Host "uv could not reach a package index (attempt $Attempt of $MaxAttempts). Trying again in $Delay seconds..."
        Start-Sleep -Seconds $Delay
    }
}

function Get-PeLinkerVersion {
    # Return the linker version in a PE file's optional header, or $null when
    # the file is not a PE image. MSVC's linker version equals its toolset
    # version, for example 14.42 for Visual Studio 2022 17.12.
    param([Parameter(Mandatory = $true)][string]$Path)
    $Stream = [System.IO.File]::OpenRead($Path)
    try {
        $Reader = New-Object System.IO.BinaryReader($Stream)
        if ($Stream.Length -lt 0x40 -or $Reader.ReadUInt16() -ne 0x5A4D) {
            return $null
        }
        $Stream.Position = 0x3C
        $PeOffset = $Reader.ReadInt32()
        if ($PeOffset -lt 0x40 -or ($PeOffset + 28) -gt $Stream.Length) {
            return $null
        }
        $Stream.Position = $PeOffset
        if ($Reader.ReadUInt32() -ne 0x00004550) {
            return $null
        }
        # Signature (4) + COFF header (20) + optional-header magic (2).
        $Stream.Position = $PeOffset + 26
        $Major = [int]$Reader.ReadByte()
        $Minor = [int]$Reader.ReadByte()
        return New-Object System.Version($Major, $Minor)
    } finally {
        $Stream.Dispose()
    }
}

function Get-MsvcToolsetFloor {
    # The Visual C++ runtime must be at least as new as the newest MSVC
    # toolset that built any installed binary. Microsoft documents this rule:
    # https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist
    # Read it from the installed files instead of fixing a version here:
    # torch 2.15.0, for example, was linked with toolset 14.42.
    param([Parameter(Mandatory = $true)][string]$EnvironmentPath)
    $RuntimeNames = @("msvcp140", "vcruntime140", "concrt140", "vccorlib140")
    $Floor = $null
    $Newest = $null
    if (-not (Test-Path -LiteralPath $EnvironmentPath -PathType Container)) {
        return [pscustomobject]@{ Version = $null; File = $null; Found = $false }
    }
    Get-ChildItem -Path $EnvironmentPath -Recurse -File -Include "*.dll", "*.pyd" -ErrorAction SilentlyContinue |
        ForEach-Object {
            $Base = $_.BaseName.ToLowerInvariant()
            $IsRuntimeCopy = $false
            foreach ($Name in $RuntimeNames) {
                if ($Base.StartsWith($Name)) { $IsRuntimeCopy = $true }
            }
            if (-not $IsRuntimeCopy) {
                $Linker = $null
                try {
                    $Linker = Get-PeLinkerVersion -Path $_.FullName
                } catch {
                    # A locked or unreadable file cannot raise the floor.
                }
                if ($Linker -and $Linker.Major -eq 14 -and (-not $Floor -or $Linker -gt $Floor)) {
                    $Floor = $Linker
                    $Newest = $_.FullName
                }
            }
        }
    return [pscustomobject]@{ Version = $Floor; File = $Newest; Found = $true }
}

function Get-VcRuntimeFileVersions {
    # File versions of the x64 runtime DLLs that PyTorch loads from the
    # system directory. A missing DLL maps to $null.
    $SystemDir = Join-Path $env:SystemRoot "System32"
    if (-not [Environment]::Is64BitProcess) {
        # A 32-bit PowerShell sees SysWOW64 as System32; Sysnative is the
        # real 64-bit directory.
        $SystemDir = Join-Path $env:SystemRoot "Sysnative"
    }
    $Versions = [ordered]@{}
    foreach ($Name in @("msvcp140.dll", "vcruntime140.dll", "vcruntime140_1.dll")) {
        $Path = Join-Path $SystemDir $Name
        if (Test-Path -LiteralPath $Path) {
            $Info = (Get-Item -LiteralPath $Path).VersionInfo
            $Versions[$Name] = New-Object System.Version($Info.FileMajorPart, $Info.FileMinorPart)
        } else {
            $Versions[$Name] = $null
        }
    }
    return $Versions
}

function Get-VcRuntimeStatus {
    # Decide whether the installed x64 runtime satisfies $Minimum (a
    # major.minor version, or $null to require only that the DLLs exist).
    param([System.Version]$Minimum)
    $Versions = Get-VcRuntimeFileVersions
    $Missing = @($Versions.Keys | Where-Object { -not $Versions[$_] })
    $Oldest = $null
    foreach ($Name in $Versions.Keys) {
        $Version = $Versions[$Name]
        if ($Version -and (-not $Oldest -or $Version -lt $Oldest)) { $Oldest = $Version }
    }
    $Adequate = ($Missing.Count -eq 0) -and ((-not $Minimum) -or ($Oldest -ge $Minimum))
    return [pscustomobject]@{
        Adequate = $Adequate
        Missing = $Missing
        Installed = $Oldest
        Minimum = $Minimum
    }
}

function Get-CertificateOrganizations {
    # Every O= value in a certificate subject, one per relative name. A
    # quoted value that contains ", O=..." stays inside its own field.
    param([Parameter(Mandatory = $true)]$Certificate)
    $Fields = $Certificate.SubjectName.Format($true) -split "`r?`n"
    foreach ($Field in $Fields) {
        $Clean = $Field.Trim().TrimEnd(",").Trim()
        if ($Clean.StartsWith("O=")) {
            $Clean.Substring(2)
        }
    }
}

function Get-CertificateRootThumbprint {
    # Thumbprint of the root at the end of the certificate's chain. Windows
    # already checked revocation for Get-AuthenticodeSignature.
    param([Parameter(Mandatory = $true)]$Certificate)
    $Chain = New-Object System.Security.Cryptography.X509Certificates.X509Chain
    try {
        $Chain.ChainPolicy.RevocationMode = [System.Security.Cryptography.X509Certificates.X509RevocationMode]::NoCheck
        $null = $Chain.Build($Certificate)
        $Elements = $Chain.ChainElements
        return $Elements[$Elements.Count - 1].Certificate.Thumbprint
    } finally {
        $Chain.Dispose()
    }
}

function Assert-MicrosoftSignature {
    # Require a valid Authenticode signature whose signer's only
    # organization is exactly "Microsoft Corporation" and whose chain ends at
    # Microsoft Root Certificate Authority 2011. That root signed
    # vc_redist.x64.exe 14.52.37029 on 2026-11-13. A root a user added to
    # their own store cannot pass this check.
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [string[]]$TrustedRoots = @("8F43288AD272F3103B6FB1428485EA3014C0BCFE")
    )
    $Signature = Get-AuthenticodeSignature -FilePath $Path
    $Certificate = $Signature.SignerCertificate
    if ("$($Signature.Status)" -ne "Valid" -or -not $Certificate) {
        throw "The downloaded Visual C++ Redistributable is not validly signed (status '$($Signature.Status)'). It was not run."
    }
    $Organizations = @(Get-CertificateOrganizations -Certificate $Certificate)
    if ($Organizations.Count -ne 1 -or $Organizations[0] -cne "Microsoft Corporation") {
        throw "The downloaded Visual C++ Redistributable is signed by '$($Certificate.Subject)', not Microsoft Corporation. It was not run."
    }
    $Root = Get-CertificateRootThumbprint -Certificate $Certificate
    if ($TrustedRoots -notcontains $Root) {
        throw "The downloaded Visual C++ Redistributable's signature chains to root '$Root', not Microsoft Root Certificate Authority 2011. It was not run."
    }
    Write-Host "Signature verified: $($Certificate.Subject)"
}

function Start-ElevatedInstaller {
    # Start a program with the "runas" verb, wait, and return its exit code.
    # Process.Start is used instead of Start-Process: Windows PowerShell 5.1's
    # Start-Process turns a cancelled UAC prompt into an InvalidOperationException
    # without the Windows error code, while Process.Start raises a
    # Win32Exception carrying 1223 (seen on Windows 11, 2026-11-13).
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string]$Arguments
    )
    $Info = New-Object System.Diagnostics.ProcessStartInfo
    $Info.FileName = $FilePath
    $Info.Arguments = $Arguments
    $Info.Verb = "runas"
    $Info.UseShellExecute = $true
    $Process = [System.Diagnostics.Process]::Start($Info)
    try {
        $Process.WaitForExit()
        return $Process.ExitCode
    } finally {
        $Process.Dispose()
    }
}

function Test-UacCancelled {
    # True when any exception in the chain is Windows error 1223, "the
    # operation was cancelled by the user".
    param($Exception)
    for ($Current = $Exception; $Current; $Current = $Current.InnerException) {
        $Native = $Current -as [System.ComponentModel.Win32Exception]
        if ($Native -and $Native.NativeErrorCode -eq 1223) {
            return $true
        }
    }
    return $false
}

function Install-VcRuntime {
    # Download Microsoft's x64 Visual C++ Redistributable, check that
    # Microsoft signed it, and run it elevated. Only this step asks for
    # administrator rights. Returns "installed" or "restart-required"; throws
    # on any other outcome. Never restarts Windows.
    param(
        [Parameter(Mandatory = $true)][string]$WorkDir,
        [string]$Url = "https://aka.ms/vc14/vc_redist.x64.exe"
    )
    $Installer = Join-Path $WorkDir "vc_redist.x64.exe"
    Write-Host "Downloading the Microsoft Visual C++ Redistributable (x64) from $Url ..."
    $PreviousProgress = $ProgressPreference
    $ProgressPreference = "SilentlyContinue"
    try {
        Invoke-WebRequest -Uri $Url -OutFile $Installer -UseBasicParsing
    } finally {
        $ProgressPreference = $PreviousProgress
    }

    # Hold the file open, readable but not writable, from the signature check
    # until the installer exits, so nothing can replace it in between.
    $Lock = [System.IO.File]::Open($Installer, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::Read)
    try {
        Assert-MicrosoftSignature -Path $Installer

        Write-Host ""
        Write-Host "Windows will ask for administrator permission to install the Visual C++ runtime."
        Write-Host "Only this step needs it; pdomain-ocr-simple-gui itself is installed for your user account."
        try {
            $Code = Start-ElevatedInstaller -FilePath $Installer -Arguments "/install /passive /norestart"
        } catch {
            if (Test-UacCancelled $_.Exception) {
                throw "The Visual C++ runtime was not installed: the administrator prompt was cancelled."
            }
            throw "The Visual C++ runtime installer could not be started: $($_.Exception.Message)"
        }
    } finally {
        $Lock.Dispose()
    }

    if ($null -eq $Code) {
        throw "The Visual C++ runtime installer did not report an exit code."
    }
    switch ($Code) {
        0 { return "installed" }
        1638 { return "installed" } # this or a newer version is already installed
        3010 { return "restart-required" }
        1641 { return "restart-required" }
        1602 { throw "The Visual C++ runtime installation was cancelled (exit code 1602)." }
        # Seen on Windows 11 with UAC turned off: a standard user's RunAs
        # start is not elevated, and the installer is denied.
        5 { throw "The Visual C++ runtime installer was denied access (exit code 5): it needs an administrator account." }
        default { throw "The Visual C++ runtime installer failed with exit code $Code." }
    }
}

function Write-VcRuntimeHelp {
    Write-Host ""
    Write-Host "pdomain-ocr-simple-gui needs the Microsoft Visual C++ Redistributable (x64). Without it,"
    Write-Host "OCR fails with 'WinError 126' while loading torch\lib\c10.dll."
    Write-Host "To install it yourself, or to ask an administrator to:"
    Write-Host "  1. Download https://aka.ms/vc14/vc_redist.x64.exe"
    Write-Host "  2. Run: vc_redist.x64.exe /install /passive /norestart"
    Write-Host "  3. Run pdomain-ocr-simple-gui again. No reinstall of pdomain-ocr-simple-gui is needed."
    Write-Host "Microsoft's page: https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist"
}

function Confirm-VcRuntime {
    # Make sure the installed tool's native libraries can load. Returns
    # $true when Windows must be restarted before OCR can run.
    param(
        [Parameter(Mandatory = $true)][string]$EnvironmentPath,
        [Parameter(Mandatory = $true)][string]$WorkDir
    )
    $Floor = Get-MsvcToolsetFloor -EnvironmentPath $EnvironmentPath
    if (-not $Floor.Found) {
        Write-Host "WARNING: $EnvironmentPath was not found, so only the runtime DLLs' presence is checked."
    }
    $Status = Get-VcRuntimeStatus -Minimum $Floor.Version
    $Needed = if ($Floor.Version) { "$($Floor.Version) or newer" } else { "any version" }
    if ($Status.Adequate) {
        Write-Host "Visual C++ runtime $($Status.Installed) found; pdomain-ocr-simple-gui needs $Needed."
        return $false
    }

    if ($Status.Missing.Count -gt 0) {
        Write-Host "The Microsoft Visual C++ runtime (x64) is missing: $($Status.Missing -join ', ') not found."
    } else {
        Write-Host "Visual C++ runtime $($Status.Installed) is older than $($Floor.Version), which $($Floor.File) needs."
    }

    if ($env:PD_SIMPLE_GUI_SKIP_VC_RUNTIME -eq "1") {
        Write-VcRuntimeHelp
        throw "PD_SIMPLE_GUI_SKIP_VC_RUNTIME=1 is set, so the runtime was not installed. pdomain-ocr-simple-gui is installed but cannot run OCR until the runtime is."
    }

    try {
        $Outcome = Install-VcRuntime -WorkDir $WorkDir
    } catch {
        Write-VcRuntimeHelp
        throw "pdomain-ocr-simple-gui is installed, but OCR cannot run yet. $($_.Exception.Message)"
    }
    if ($Outcome -eq "restart-required") {
        return $true
    }

    $After = Get-VcRuntimeStatus -Minimum $Floor.Version
    if ($After.Missing.Count -gt 0) {
        Write-VcRuntimeHelp
        throw "The Visual C++ runtime installer finished, but $($After.Missing -join ', ') is still missing."
    }
    if (-not $After.Adequate) {
        # Microsoft's newest runtime is now installed, so nothing more can be
        # done here. Some binary claims a newer toolset; OCR usually works.
        Write-Host "WARNING: Visual C++ runtime $($After.Installed) is the newest Microsoft offers, but"
        Write-Host "         $($Floor.File) was built with toolset $($Floor.Version)."
        Write-Host "         If pdomain-ocr-simple-gui fails to load a DLL, install a newer runtime when one is released."
        return $false
    }
    Write-Host "Visual C++ runtime $($After.Installed) installed."
    return $false
}

function Complete-WindowsInstall {
    # Check the Visual C++ runtime for the installed tool. Returns $true when
    # Windows must restart before OCR can run.
    param([Parameter(Mandatory = $true)][string]$WorkDir)
    $global:LASTEXITCODE = $null
    $ToolDir = (& uv tool dir | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $ToolDir) {
        throw "'uv tool dir' failed with exit code $LASTEXITCODE; cannot check the Visual C++ runtime."
    }
    $EnvironmentPath = Join-Path $ToolDir "pdomain-ocr-simple-gui"
    foreach ($Required in @("Scripts/python.exe", "Scripts/pdomain-ocr-simple-gui.exe")) {
        if (-not (Test-Path -LiteralPath (Join-Path $EnvironmentPath $Required) -PathType Leaf)) {
            throw "The tool install is incomplete: $Required is missing from $EnvironmentPath. The GUI is not ready; rerun the installer."
        }
    }
    $global:LASTEXITCODE = $null
    $ToolBin = (& uv tool dir --bin | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $ToolBin -or -not (Test-Path -LiteralPath (Join-Path $ToolBin "pdomain-ocr-simple-gui.exe") -PathType Leaf)) {
        throw "The GUI launch command is missing from uv's tool bin directory. The install is incomplete; rerun the installer."
    }
    return Confirm-VcRuntime -EnvironmentPath $EnvironmentPath -WorkDir $WorkDir
}

function Write-InstallSummary {
    param([bool]$RestartRequired)
    Write-Host ""
    if ($RestartRequired) {
        Write-Host "Done, but Windows must restart before OCR can run: the Visual C++ runtime"
        Write-Host "installer asked for a restart. This installer never restarts Windows itself."
        Write-Host "After restarting, run: pdomain-ocr-simple-gui"
    } else {
        Write-Host "Done! Run: pdomain-ocr-simple-gui"
    }
    Write-Host "If 'pdomain-ocr-simple-gui' is not found, ensure uv's tool bin is on your PATH."
    Write-Host "  uv tool update-shell"
}

$HelperPath = $null
if ($PSScriptRoot) {
    $HelperPath = Join-Path $PSScriptRoot "scripts/install-cuda-detect.ps1"
}
if ($HelperPath -and (Test-Path $HelperPath)) {
    . $HelperPath
}

$Repo = "pdomain/pdomain-ocr-simple-gui"
$PdIndexUrl = "https://pdomain.github.io/pdomain-index-pip/simple/"
$PythonVersion = if ($env:PD_SIMPLE_GUI_INSTALL_PYTHON) { $env:PD_SIMPLE_GUI_INSTALL_PYTHON } else { "3.13" }

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "uv not found -- installing uv..."
    if (Test-IsWindowsHost) {
        Install-Uv
    } else {
        irm https://astral.sh/uv/install.ps1 | iex
    }
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "User") + ";" + $env:PATH
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        throw "The uv installer finished, but 'uv' is still not on PATH. Open a new PowerShell window and run this installer again."
    }
}

$TorchBackend = ""
$BookToolsExtras = ""

if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
    $CudaVer = Get-CudaVersion

    if ($CudaVer) {
        # uv picks the PyTorch CUDA build that matches the driver. PyPI's
        # Windows torch wheels are CPU-only, so this matters on Windows too.
        # Do not add download.pytorch.org/whl/cuXXX as an --index instead:
        # it also serves old copies of common packages (packaging 24.1 at
        # most), and under first-index uv then takes `packaging` from it
        # alone, so the resolve fails (pdomain-ops needs packaging>=26).
        $TorchBackend = "auto"
        Write-Host "Detected CUDA $CudaVer -- uv will pick the matching PyTorch CUDA build."

        $BookToolsExtras = Get-BookToolsExtras $CudaVer
        if ($BookToolsExtras -eq "[gpu]") {
            Write-Host "CUDA $CudaVer >= 13 -- enabling pdomain-book-tools[gpu] (cupy-cuda13x)."
        } else {
            Write-Host "CUDA $CudaVer < 13 -- installing CPU-only book-tools (cupy-cuda13x needs CUDA 13)."
        }
    } else {
        Write-Host ""
        Write-Host "WARNING: NVIDIA GPU detected but CUDA version could not be determined."
        Write-Host "         Installing CPU-only build of pdomain-ocr-simple-gui."
        Write-Host ""
        Write-Host "         To install the GPU build instead, re-run with a manual override:"
        Write-Host "           `$env:CUDA_VERSION = `"13.0`"   # replace with your CUDA version"
        Write-Host "           irm https://raw.githubusercontent.com/pdomain/pdomain-ocr-simple-gui/master/install.ps1 | iex"
        Write-Host ""
        Write-Host "         Find your CUDA version by running:  nvidia-smi"
        Write-Host "         and looking for the 'CUDA Version' field in the output."
        Write-Host ""
    }
} else {
    Write-Host "No GPU detected -- installing CPU-only PyTorch."
}

$ReleaseEndpoint = "latest"
if ($env:PD_SIMPLE_GUI_INSTALL_VERSION) {
    if ($env:PD_SIMPLE_GUI_INSTALL_VERSION -notmatch '^v?\d+\.\d+\.\d+$') {
        throw "PD_SIMPLE_GUI_INSTALL_VERSION must be a release version such as 0.5.7."
    }
    $ReleaseEndpoint = "tags/v" + $env:PD_SIMPLE_GUI_INSTALL_VERSION.TrimStart("v")
}
$ReleaseUrl = "https://api.github.com/repos/$Repo/releases/$ReleaseEndpoint"
Write-Host "Resolving release via GitHub API..."
$Release = Invoke-RestMethod -Uri $ReleaseUrl
$ReleaseTag = $Release.tag_name
$WheelAsset = $Release.assets |
    Where-Object { $_.name -like "*.whl" -or $_.browser_download_url -like "*.whl" } |
    Select-Object -First 1

if (-not $WheelAsset) {
    throw "Latest release $ReleaseTag has no wheel asset attached."
}

$WheelUrl = $WheelAsset.browser_download_url
$WheelName = if ($WheelAsset.name) {
    $WheelAsset.name
} else {
    Split-Path -Leaf ([Uri]$WheelUrl).AbsolutePath
}

# Fail closed on any missing or malformed digest, before downloading. A
# digest that is absent or not a well-formed sha256 means we cannot verify
# the wheel we're about to fetch, so refuse rather than install unverified.
# Use the case-SENSITIVE -cnotmatch: plain -notmatch is case-insensitive in
# PowerShell, which would accept uppercase hex here while install.sh (grep,
# case-sensitive by default) rejects it — the spec requires lowercase only,
# and both installers must agree on what they accept.
$WheelDigest = $WheelAsset.digest
if (-not $WheelDigest -or $WheelDigest -cnotmatch '^sha256:[0-9a-f]{64}$') {
    throw "Latest release $ReleaseTag wheel asset '$WheelName' has no verifiable sha256 digest (got: '$WheelDigest'). Refusing to install an unverified wheel."
}
$WheelDigestHex = $WheelDigest.Substring(7)

Write-Host "Latest release: $ReleaseTag"
Write-Host "Wheel asset:    $WheelUrl"
Write-Host "Wheel digest:   $WheelDigest"
Write-Host "pdomain-index-pip:       $PdIndexUrl"

$TempDir = Join-Path ([System.IO.Path]::GetTempPath()) ("pdomain-ocr-install-" + [guid]::NewGuid().ToString("N"))
$TempDirItem = New-Item -ItemType Directory -Path $TempDir
# Windows PowerShell 5.1 has no $IsWindows. An unset variable is falsy, so
# `-not $IsWindows` alone enters this branch and aborts on UnixFileMode
# before the download. UnixFileMode exists only on PowerShell 6+ off Windows.
if ($PSVersionTable.PSVersion.Major -ge 6 -and -not $IsWindows) {
    # New-Item's directory mode follows umask (e.g. 0777 at umask 0) — unlike
    # `mktemp -d`, which is always 0700. Without this, another local user
    # could replace the downloaded wheel between the Get-FileHash check below
    # and the `uv tool install` call, defeating digest verification.
    $TempDirItem.UnixFileMode = [System.IO.UnixFileMode]::UserRead -bor
        [System.IO.UnixFileMode]::UserWrite -bor
        [System.IO.UnixFileMode]::UserExecute
}

try {
    $WheelFile = Join-Path $TempDir $WheelName
    Write-Host "Downloading wheel..."
    Invoke-WebRequest -Uri $WheelUrl -OutFile $WheelFile -UseBasicParsing

    # Verify the downloaded wheel against the digest GitHub reported for it,
    # BEFORE calling `uv tool install`. A digest that doesn't match the bytes
    # we actually fetched means the download was tampered with or corrupted;
    # either way, installing it would be worse than failing here.
    $WheelActualHex = (Get-FileHash -Algorithm SHA256 -Path $WheelFile).Hash.ToLowerInvariant()
    if ($WheelActualHex -ne $WheelDigestHex) {
        throw "Wheel digest mismatch for $WheelFile.`n  expected: sha256:$WheelDigestHex`n  actual:   sha256:$WheelActualHex"
    }
    Write-Host "Digest verified: sha256:$WheelActualHex"

    Write-Host "Installing pdomain-ocr-simple-gui $ReleaseTag from $WheelName..."
    # "first-index" makes uv stop looking once a package name resolves on an
    # index, in index-URL order. The pdomain index is bound via a named
    # `--index` (not the deprecated `--extra-index-url`): uv ranks
    # --index/UV_INDEX strictly above --extra-index-url, and passing --index
    # explicitly on the CLI replaces (rather than merges with) any UV_INDEX
    # the environment supplies. Verified against real uv 0.11.32 with local
    # decoy indexes: a hostile UV_INDEX env var beats --extra-index-url but
    # cannot beat this --index binding. When CUDA was detected,
    # --torch-backend auto lets uv choose the PyTorch CUDA build.
    $UvArgs = @(
        "tool", "install", "--python", $PythonVersion, "--reinstall", $WheelFile,
        "--index-strategy", "first-index", "--index", "pdomain=$PdIndexUrl"
    )
    if ($BookToolsExtras) {
        $UvArgs += @("--with", "pdomain-book-tools$BookToolsExtras")
    }
    if ($TorchBackend) {
        $UvArgs += @("--torch-backend", $TorchBackend)
    }
    Invoke-UvToolInstall -UvArgs $UvArgs

    $RestartRequired = $false
    if (Test-IsWindowsHost) {
        $RestartRequired = Complete-WindowsInstall -WorkDir $TempDir
    }
} finally {
    Remove-Item -Recurse -Force $TempDir -ErrorAction SilentlyContinue
}

Write-InstallSummary -RestartRequired $RestartRequired
