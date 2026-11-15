$ErrorActionPreference = 'Stop'
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$Source = Get-Content (Join-Path $PSScriptRoot 'Bootstrapper.cs') -Raw
foreach ($Contract in @('CreateNoWindow = true', 'UseShellExecute = false', 'BeginOutputReadLine', 'BeginErrorReadLine', 'Retry', '--launch', '--uninstall', 'payload.zip')) {
    if (-not $Source.Contains($Contract)) { throw "Missing bootstrapper contract: $Contract" }
}
$Install = Get-Content (Join-Path $Root 'install.ps1') -Raw
if (-not $Install.Contains('PD_SIMPLE_GUI_INSTALL_WHEEL')) { throw 'Local wheel input missing' }
$Integration = Get-Content (Join-Path $PSScriptRoot 'integrate.ps1') -Raw
foreach ($Contract in @('pythonw.exe', 'pdomain-ocr-simple-gui-desktop.exe', 'install-manifest.json', 'CreateShortcut', 'owned_files')) {
    if (-not $Integration.Contains($Contract)) { throw "Missing integration contract: $Contract" }
}
Write-Output 'Windows installer source contracts passed.'
