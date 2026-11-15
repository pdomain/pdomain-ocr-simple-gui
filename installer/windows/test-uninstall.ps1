$ErrorActionPreference = 'Stop'
$Repo = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
. (Join-Path $Repo 'uninstall.ps1')
$Scratch = Join-Path ([IO.Path]::GetTempPath()) ('pdomain-uninstall-test-' + [Guid]::NewGuid().ToString('N'))
$null = New-Item -ItemType Directory -Path $Scratch
Set-Content -LiteralPath (Join-Path $Scratch '.nobackup') -Value ''
$InstallRoot = Join-Path $Scratch 'Programs/pdomain-ocr-simple-gui'
$ProgramsRoot = Join-Path $Scratch 'Menu'
$null = New-Item -ItemType Directory -Path $InstallRoot, $ProgramsRoot
$ManifestPath = Join-Path $InstallRoot 'install-manifest.json'
$ToolDir = Join-Path $Scratch 'tools/pdomain-ocr-simple-gui'
$Manifest = @{
    schema_version = 1; app_id = 'pdomain-ocr-simple-gui'; install_root = $InstallRoot
    tool_dir = $ToolDir; tool_bin = (Join-Path $Scratch 'bin')
    owned_files = @('OCR-Simple-GUI.exe', 'uninstall.ps1', 'launch.json', 'install-manifest.json') | ForEach-Object { Join-Path $InstallRoot $_ }
    shortcut_paths = @('OCR Simple GUI.lnk', 'Uninstall OCR Simple GUI.lnk') | ForEach-Object { Join-Path (Join-Path $ProgramsRoot 'OCR Simple GUI') $_ }
}
try {
    $Manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $ManifestPath
    $Plan = Get-DesktopUninstallPlan -ManifestPath $ManifestPath -InstallRoot $InstallRoot -ProgramsRoot $ProgramsRoot
    if ($Plan.owned_files.Count -ne 4) { throw 'Valid manifest rejected.' }
    $Manifest.owned_files += (Join-Path $Scratch 'unrelated.txt')
    $Manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $ManifestPath
    $Rejected = $false
    try { $null = Get-DesktopUninstallPlan -ManifestPath $ManifestPath -InstallRoot $InstallRoot -ProgramsRoot $ProgramsRoot } catch { $Rejected = $true }
    if (-not $Rejected) { throw 'Arbitrary owned path accepted.' }
    $Manifest.owned_files = @($Manifest.owned_files | Select-Object -First 4)
    $Manifest.shortcut_paths[0] = Join-Path $ProgramsRoot 'unrelated.lnk'
    $Manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $ManifestPath
    $Rejected = $false
    try { $null = Get-DesktopUninstallPlan -ManifestPath $ManifestPath -InstallRoot $InstallRoot -ProgramsRoot $ProgramsRoot } catch { $Rejected = $true }
    if (-not $Rejected) { throw 'Arbitrary shortcut path accepted.' }
    $Manifest.shortcut_paths = @('OCR Simple GUI.lnk', 'Uninstall OCR Simple GUI.lnk') | ForEach-Object { Join-Path (Join-Path $ProgramsRoot 'OCR Simple GUI') $_ }
    $Manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $ManifestPath
    foreach ($File in @($Manifest.owned_files | Where-Object { $_ -ne $ManifestPath })) { Set-Content -LiteralPath $File -Value 'owned' }
    $Unrelated = Join-Path $InstallRoot 'keep-my-file.txt'
    Set-Content -LiteralPath $Unrelated -Value 'unrelated'
    function Get-DesktopInstallLocations { return @{ InstallRoot = $InstallRoot; ProgramsRoot = $ProgramsRoot } }
    function Read-Host { return 'cancel' }
    $Rejected = $false
    try { Invoke-DesktopUninstall -ManifestPath $ManifestPath } catch { $Rejected = $true }
    if (-not $Rejected -or -not (Test-Path -LiteralPath $ManifestPath)) { throw 'Cancellation changed the installation.' }
    $null = New-Item -ItemType Directory -Path (Join-Path $ToolDir 'Scripts') -Force
    Set-Content -LiteralPath (Join-Path $ToolDir 'Scripts/python.exe') -Value 'placeholder'
    function Invoke-DesktopPreparation { throw 'Active work must refuse removal.' }
    $Rejected = $false
    try { Invoke-DesktopUninstall -ManifestPath $ManifestPath -Yes } catch { $Rejected = $true }
    if (-not $Rejected -or -not (Test-Path -LiteralPath $ManifestPath)) { throw 'Preparation refusal removed installation controls.' }
    $global:PreparationSawToolDirs = $false
    function Invoke-DesktopPreparation {
        if ($env:UV_TOOL_DIR -ne (Split-Path -Parent $ToolDir) -or $env:UV_TOOL_BIN_DIR -ne $Manifest.tool_bin) { throw 'Preparation inventoried the wrong environment.' }
        $global:PreparationSawToolDirs = $true
        return [pscustomobject]@{ prepared = $true; retained_paths = @('original-scans') }
    }
    function uv {
        if ($env:UV_TOOL_DIR -ne (Split-Path -Parent $ToolDir) -or $env:UV_TOOL_BIN_DIR -ne $Manifest.tool_bin) { throw 'uv targeted the wrong environment.' }
        $global:LASTEXITCODE = 17
    }
    $Rejected = $false
    try { Invoke-DesktopUninstall -ManifestPath $ManifestPath -Yes } catch { $Rejected = $true }
    if (-not $Rejected -or -not (Test-Path -LiteralPath $ManifestPath) -or -not (Test-Path -LiteralPath (Join-Path $InstallRoot 'uninstall.ps1'))) { throw 'uv failure removed retry controls.' }
    if (-not $global:PreparationSawToolDirs) { throw 'Preparation did not receive the manifest tool inventory.' }
    function uv { $global:LASTEXITCODE = 0 }
    $Rejected = $false
    try { Invoke-DesktopUninstall -ManifestPath $ManifestPath -Yes } catch { $Rejected = $true }
    if (-not $Rejected -or -not (Test-Path -LiteralPath $ManifestPath) -or -not (Test-Path -LiteralPath $ToolDir)) { throw 'False uv success discarded recovery controls while the tool remained.' }
    Remove-Item -LiteralPath $ToolDir -Recurse -Force
    Invoke-DesktopUninstall -ManifestPath $ManifestPath -Yes
    if ((Test-Path -LiteralPath $ManifestPath) -or -not (Test-Path -LiteralPath $Unrelated) -or -not (Test-Path -LiteralPath (Join-Path $InstallRoot 'OCR-Simple-GUI.exe'))) { throw 'Already-removed cleanup did not preserve unrelated files and the executing wrapper.' }
    $null = New-Item -ItemType Directory -Force -Path (Join-Path $ToolDir 'Scripts')
    Set-Content -LiteralPath (Join-Path $ToolDir 'Scripts/python.exe') -Value ''
    $Manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $ManifestPath
    $script:PreparationCalls = 0
    $script:FinalizerCalls = 0
    $script:FailFinalization = $true
    function Invoke-DesktopPreparation {
        param([string]$Python)
        $script:PreparationCalls++
        return [pscustomobject]@{prepared=$true; base_python='Fake-BasePython'; finalize_script='ignored.py'; plan_path='ignored.plan'; retained_paths=@()}
    }
    function Fake-BasePython {
        $script:FinalizerCalls++
        Write-Output '{"operation_token":"private-finalization-token"}'
        $global:LASTEXITCODE = if ($script:FailFinalization) { 1 } else { 0 }
    }
    function uv {
        Remove-Item -LiteralPath $ToolDir -Recurse -Force
        $global:LASTEXITCODE = 0
    }
    $Rejected = $false
    try { Invoke-DesktopUninstall -ManifestPath $ManifestPath -Yes } catch { $Rejected = $true }
    if (-not $Rejected -or -not (Test-Path -LiteralPath $ManifestPath)) { throw 'Finalizer failure discarded retry controls.' }
    $script:FailFinalization = $false
    $Messages = Invoke-DesktopUninstall -ManifestPath $ManifestPath -Yes
    if (($Messages | Out-String).Contains('private-finalization-token')) { throw 'Private finalizer details leaked into user-facing output.' }
    if ($script:PreparationCalls -ne 1 -or $script:FinalizerCalls -ne 2 -or (Test-Path -LiteralPath $ManifestPath)) { throw 'Retry did not resume finalization after tool removal.' }
    Write-Output 'Uninstall ownership, cancellation, preparation refusal, uv failure, finalizer retry and already-removed tests passed.'
} finally { Remove-Item -LiteralPath $Scratch -Recurse -Force }
