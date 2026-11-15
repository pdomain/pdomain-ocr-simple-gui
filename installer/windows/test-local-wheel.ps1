$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -lt 6 -or $IsWindows) { throw 'Run this network-free installer branch test under PowerShell on Linux.' }
$Repo = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$Scratch = Join-Path ([IO.Path]::GetTempPath()) ('pdomain-wheel-test-' + [Guid]::NewGuid().ToString('N'))
$null = New-Item -ItemType Directory -Path $Scratch
Set-Content -LiteralPath (Join-Path $Scratch '.nobackup') -Value ''
$OriginalWheel = $env:PD_SIMPLE_GUI_INSTALL_WHEEL
$OriginalCuda = $env:CUDA_VERSION
$global:ObservedUvArguments = $null
function uv {
    $global:ObservedUvArguments = $args
    if ($args[0] -ne 'tool' -or $args[1] -ne 'install') { throw 'Unexpected uv command.' }
    $Candidate = @($args | Where-Object { "$_" -like '*.whl' })
    if ($Candidate.Count -ne 1 -or (Get-Content -LiteralPath $Candidate[0] -Raw) -ne 'exact source artifact') { throw 'The explicit wheel bytes did not reach uv.' }
    $global:LASTEXITCODE = 0
}
function nvidia-smi { '' }
function Invoke-RestMethod { throw 'A bundled wheel must not query the release API.' }
function Invoke-WebRequest { throw 'A bundled wheel must not download the released wheel.' }
try {
    $env:CUDA_VERSION = ''
    $env:PD_SIMPLE_GUI_INSTALL_WHEEL = Join-Path $Scratch 'artifact with spaces.whl'
    Set-Content -LiteralPath $env:PD_SIMPLE_GUI_INSTALL_WHEEL -Value 'exact source artifact' -NoNewline
    & (Join-Path $Repo 'install.ps1')
    if (-not $global:ObservedUvArguments) { throw 'uv did not receive the bundled wheel.' }
    if ($global:ObservedUvArguments -notcontains 'pdomain=https://pdomain.github.io/pdomain-index-pip/simple/') { throw 'The package index binding was lost.' }
    $env:PD_SIMPLE_GUI_INSTALL_WHEEL = Join-Path $Scratch 'missing.whl'
    $Failed = $false
    try { & (Join-Path $Repo 'install.ps1') } catch { $Failed = $true }
    if (-not $Failed) { throw 'A missing wheel must fail.' }
    Write-Output 'Exact local wheel installation and missing-wheel failure passed.'
} finally {
    $env:PD_SIMPLE_GUI_INSTALL_WHEEL = $OriginalWheel
    $env:CUDA_VERSION = $OriginalCuda
    Remove-Item -LiteralPath $Scratch -Recurse -Force
}
