param([string]$ManifestPath, [switch]$Yes)
$ErrorActionPreference = 'Stop'

function Assert-PlainPath {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (-not [IO.Path]::IsPathRooted($Path)) { throw "Expected an absolute path: $Path" }
    $Current = [IO.Path]::GetFullPath($Path)
    while ($Current) {
        if (Test-Path -LiteralPath $Current) {
            $Item = Get-Item -LiteralPath $Current -Force
            if (($Item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw "Refusing linked installation path: $Current" }
        }
        $Parent = [IO.Path]::GetDirectoryName($Current)
        if ($Parent -eq $Current) { break }
        $Current = $Parent
    }
}

function Assert-ExactPaths {
    param([object[]]$Actual, [string[]]$Expected)
    if ($Actual.Count -ne $Expected.Count) { throw 'Installation manifest has an unexpected file count.' }
    $Seen = @{}
    foreach ($Path in $Actual) {
        if ($Path -isnot [string]) { throw 'Installation manifest contains a non-string path.' }
        Assert-PlainPath -Path $Path
        $FullPath = [IO.Path]::GetFullPath($Path)
        if ($Expected -notcontains $FullPath -or $Seen.ContainsKey($FullPath)) { throw "Installation manifest contains an unowned path: $Path" }
        $Seen[$FullPath] = $true
    }
}

function Get-DesktopUninstallPlan {
    param(
        [Parameter(Mandatory = $true)][string]$ManifestPath,
        [Parameter(Mandatory = $true)][string]$InstallRoot,
        [Parameter(Mandatory = $true)][string]$ProgramsRoot
    )
    Assert-PlainPath -Path $InstallRoot
    Assert-PlainPath -Path $ManifestPath
    $Root = [IO.Path]::GetFullPath($InstallRoot)
    if ([IO.Path]::GetFullPath($ManifestPath) -ne (Join-Path $Root 'install-manifest.json')) { throw 'The uninstall manifest must be inside this application installation directory.' }
    $Manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
    if ($Manifest.schema_version -ne 1 -or $Manifest.app_id -cne 'pdomain-ocr-simple-gui' -or $Manifest.install_root -ne $Root) { throw 'The installation manifest identity is invalid.' }
    $ExpectedFiles = @('OCR-Simple-GUI.exe', 'uninstall.ps1', 'launch.json', 'install-manifest.json') | ForEach-Object { Join-Path $Root $_ }
    $Menu = Join-Path $ProgramsRoot 'OCR Simple GUI'
    $ExpectedShortcuts = @('OCR Simple GUI.lnk', 'Uninstall OCR Simple GUI.lnk') | ForEach-Object { Join-Path $Menu $_ }
    Assert-ExactPaths -Actual @($Manifest.owned_files) -Expected $ExpectedFiles
    Assert-ExactPaths -Actual @($Manifest.shortcut_paths) -Expected $ExpectedShortcuts
    Assert-PlainPath -Path $Manifest.tool_dir
    Assert-PlainPath -Path $Manifest.tool_bin
    if ((Split-Path -Leaf $Manifest.tool_dir) -cne 'pdomain-ocr-simple-gui') { throw 'The manifest tool environment has an unexpected name.' }
    Assert-PlainPath -Path (Join-Path $Manifest.tool_dir 'Scripts/python.exe')
    return $Manifest
}

function Remove-DesktopOwnedFiles {
    param([Parameter(Mandatory = $true)]$Plan)
    foreach ($Shortcut in $Plan.shortcut_paths) {
        if (Test-Path -LiteralPath $Shortcut) { Remove-Item -LiteralPath $Shortcut -Force }
    }
    foreach ($File in $Plan.owned_files) {
        if ((Split-Path -Leaf $File) -eq 'OCR-Simple-GUI.exe') { continue }
        if (Test-Path -LiteralPath $File) { Remove-Item -LiteralPath $File -Force }
    }
    $Menu = Split-Path -Parent $Plan.shortcut_paths[0]
    if ((Test-Path -LiteralPath $Menu) -and @(Get-ChildItem -LiteralPath $Menu -Force).Count -eq 0) { Remove-Item -LiteralPath $Menu }
}

function Get-DesktopInstallLocations {
    return @{
        InstallRoot = (Join-Path $env:LOCALAPPDATA 'Programs/pdomain-ocr-simple-gui')
        ProgramsRoot = [Environment]::GetFolderPath('Programs')
    }
}

function Invoke-DesktopPreparation {
    param([Parameter(Mandatory = $true)][string]$Python)
    $global:LASTEXITCODE = $null
    $Output = & $Python -m pdomain_ocr_simple_gui.uninstall_support --prepare --tool-dir $env:UV_TOOL_DIR --json
    if ($LASTEXITCODE -ne 0) { throw 'The application could not prepare for removal. Resolve the error above, then retry. Installation controls were kept.' }
    $Preparation = ($Output | Out-String) | ConvertFrom-Json
    if (-not $Preparation.prepared) { throw 'The application did not confirm that it is ready for removal.' }
    return $Preparation
}

function Save-DesktopRemovalState {
    param([string]$ManifestPath, $Plan, $Preparation)
    $Plan | Add-Member -NotePropertyName removal_state -NotePropertyValue $Preparation -Force
    $Staged = "$ManifestPath.$([Guid]::NewGuid().ToString('N')).tmp"
    try {
        $Plan | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $Staged -Encoding UTF8
        [IO.File]::Replace($Staged, $ManifestPath, [NullString]::Value)
    } finally {
        if (Test-Path -LiteralPath $Staged) { Remove-Item -LiteralPath $Staged }
    }
}

function Invoke-DesktopUninstall {
    param([Parameter(Mandatory = $true)][string]$ManifestPath, [switch]$Yes)
    $Locations = Get-DesktopInstallLocations
    $InstallRoot = $Locations.InstallRoot
    $ProgramsRoot = $Locations.ProgramsRoot
    if (-not $ProgramsRoot) { throw 'The Windows Start menu location is unavailable.' }
    $Plan = Get-DesktopUninstallPlan -ManifestPath $ManifestPath -InstallRoot $InstallRoot -ProgramsRoot $ProgramsRoot
    if (-not $Yes) {
        $Answer = Read-Host 'Remove OCR Simple GUI? Projects, scans, outputs, shared tools and model caches will be kept. Type REMOVE to continue'
        if ($Answer -cne 'REMOVE') { throw 'Uninstall cancelled. Nothing was removed.' }
    }
    $Python = Join-Path $Plan.tool_dir 'Scripts/python.exe'
    $Preparation = $Plan.removal_state
    if ($Preparation -or (Test-Path -LiteralPath $Plan.tool_dir)) {
        $OriginalToolDir = $env:UV_TOOL_DIR
        $OriginalToolBin = $env:UV_TOOL_BIN_DIR
        $OriginalPath = $env:PATH
        try {
            $env:UV_TOOL_DIR = Split-Path -Parent $Plan.tool_dir
            $env:UV_TOOL_BIN_DIR = $Plan.tool_bin
            $env:PATH = [Environment]::GetEnvironmentVariable('PATH', 'User') + ';' + $env:PATH
            if (-not $Preparation) {
                if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) { throw 'The tool environment exists but its Python is missing. Cannot verify a running instance; installation controls were kept.' }
                $Preparation = Invoke-DesktopPreparation -Python $Python
                Save-DesktopRemovalState -ManifestPath $ManifestPath -Plan $Plan -Preparation $Preparation
            }
            if (-not $Preparation.tool_removed -or (Test-Path -LiteralPath $Plan.tool_dir)) {
                if (Test-Path -LiteralPath $Plan.tool_dir) {
                    $global:LASTEXITCODE = $null
                    & uv tool uninstall pdomain-ocr-simple-gui
                    if ($LASTEXITCODE -ne 0) { throw "uv tool uninstall failed (exit $LASTEXITCODE). Installation controls were kept for Retry." }
                }
                if (Test-Path -LiteralPath $Plan.tool_dir) { throw 'The tool environment remains after uv removal. Installation controls were kept for Retry.' }
                $Preparation | Add-Member -NotePropertyName tool_removed -NotePropertyValue $true -Force
                Save-DesktopRemovalState -ManifestPath $ManifestPath -Plan $Plan -Preparation $Preparation
            }
            if ($Preparation.base_python -and $Preparation.finalize_script -and $Preparation.plan_path) {
                $global:LASTEXITCODE = $null
                $null = & $Preparation.base_python $Preparation.finalize_script --execute-plan $Preparation.plan_path --json
                if ($LASTEXITCODE -ne 0) { throw 'The app was removed but final cleanup failed. Use Retry to finish; installation controls were kept.' }
            }
        } finally {
            $env:UV_TOOL_DIR = $OriginalToolDir
            $env:UV_TOOL_BIN_DIR = $OriginalToolBin
            $env:PATH = $OriginalPath
        }
        foreach ($Retained in $Preparation.retained_paths) { Write-Output "Kept: $Retained" }
    } else {
        Write-Output 'The tool environment is already absent. Shared suite integration was kept because its ownership cannot be checked.'
    }
    Remove-DesktopOwnedFiles -Plan $Plan
    Write-Output 'OCR Simple GUI was removed. Projects, scans, outputs, model caches, uv, managed Python, Microsoft runtime and GPU drivers were kept.'
}

if ($MyInvocation.InvocationName -ne '.') {
    if (-not $ManifestPath) { $ManifestPath = Join-Path $env:LOCALAPPDATA 'Programs/pdomain-ocr-simple-gui/install-manifest.json' }
    Invoke-DesktopUninstall -ManifestPath $ManifestPath -Yes:$Yes
}
