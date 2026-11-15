param([Parameter(Mandatory = $true)][string]$BootstrapperPath)
$ErrorActionPreference = 'Stop'
$BundledWheel = @(Get-ChildItem -LiteralPath $PSScriptRoot -Filter '*.whl' -File)
if ($BundledWheel.Count -gt 1) { throw 'Setup contains multiple wheels.' }
if ($BundledWheel.Count -eq 1) { $env:PD_SIMPLE_GUI_INSTALL_WHEEL = $BundledWheel[0].FullName }
. (Join-Path $PSScriptRoot 'install.ps1')
& (Join-Path $PSScriptRoot 'integrate.ps1') -BootstrapperPath $BootstrapperPath
if ($RestartRequired) { exit 3010 }
