param([Parameter(Mandatory = $true)][string]$BootstrapperPath)
$ErrorActionPreference = 'Stop'
$ToolRoot = (& uv tool dir | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or -not $ToolRoot) { throw 'Cannot find uv tool directory.' }
$ToolBin = (& uv tool dir --bin | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or -not $ToolBin) { throw 'Cannot find uv tool bin directory.' }
$ToolDir = Join-Path $ToolRoot 'pdomain-ocr-simple-gui'
$Desktop = Join-Path $ToolDir 'Scripts/pdomain-ocr-simple-gui-desktop.exe'
$Pythonw = Join-Path $ToolDir 'Scripts/pythonw.exe'
foreach ($Required in @($Desktop, $Pythonw)) {
    if (-not (Test-Path -LiteralPath $Required -PathType Leaf)) { throw "Installed desktop entrypoint missing: $Required. Build or select a wheel containing the desktop feature." }
}
$Root = Join-Path $env:LOCALAPPDATA 'Programs/pdomain-ocr-simple-gui'
$Menu = Join-Path ([Environment]::GetFolderPath('Programs')) 'OCR Simple GUI'
$null = New-Item -ItemType Directory -Force -Path $Root, $Menu
$Exe = Join-Path $Root 'OCR-Simple-GUI.exe'
Copy-Item -LiteralPath $BootstrapperPath -Destination $Exe -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'uninstall.ps1') -Destination (Join-Path $Root 'uninstall.ps1') -Force
$Launch = Join-Path $Root 'launch.json'
@{ desktop_executable = $Desktop; pythonw = $Pythonw } | ConvertTo-Json | Set-Content -LiteralPath $Launch -Encoding UTF8
$Shortcuts = @((Join-Path $Menu 'OCR Simple GUI.lnk'), (Join-Path $Menu 'Uninstall OCR Simple GUI.lnk'))
$Shell = New-Object -ComObject WScript.Shell
for ($Index = 0; $Index -lt $Shortcuts.Count; $Index++) {
    $Shortcut = $Shell.CreateShortcut($Shortcuts[$Index])
    $Shortcut.TargetPath = $Exe
    $Shortcut.Arguments = if ($Index -eq 0) { '--launch' } else { '--uninstall' }
    $Shortcut.WorkingDirectory = $Root
    $Shortcut.IconLocation = "$Exe,0"
    $Shortcut.Save()
    if (-not (Test-Path -LiteralPath $Shortcuts[$Index])) { throw 'Start menu shortcut was not created.' }
}
$Manifest = Join-Path $Root 'install-manifest.json'
@{
    schema_version = 1; app_id = 'pdomain-ocr-simple-gui'; install_root = $Root
    tool_dir = $ToolDir; tool_bin = $ToolBin; desktop_executable = $Desktop; pythonw = $Pythonw
    owned_files = @($Exe, (Join-Path $Root 'uninstall.ps1'), $Launch, $Manifest)
    shortcut_paths = $Shortcuts
} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $Manifest -Encoding UTF8
Write-Output "Desktop installation complete: $Root"
