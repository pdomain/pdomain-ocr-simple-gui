param([string]$WheelPath, [string]$OutputDirectory)
$ErrorActionPreference = 'Stop'
$Repo = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
if (-not $OutputDirectory) { $OutputDirectory = Join-Path $Repo 'dist/windows' }
$null = New-Item -ItemType Directory -Force -Path $OutputDirectory
$OutputDirectory = (Resolve-Path -LiteralPath $OutputDirectory).ProviderPath
Set-Content -LiteralPath (Join-Path $OutputDirectory '.nobackup') -Value ''
$Stage = Join-Path ([IO.Path]::GetTempPath()) ('pdomain-build-' + [Guid]::NewGuid().ToString('N'))
$null = New-Item -ItemType Directory -Path $Stage
Set-Content -LiteralPath (Join-Path $Stage '.nobackup') -Value ''
try {
    foreach ($Name in @('install.ps1', 'uninstall.ps1')) { Copy-Item -LiteralPath (Join-Path $Repo $Name) -Destination $Stage }
    foreach ($Name in @('install-desktop.ps1', 'integrate.ps1')) { Copy-Item -LiteralPath (Join-Path $PSScriptRoot $Name) -Destination $Stage }
    $null = New-Item -ItemType Directory -Path (Join-Path $Stage 'scripts')
    Copy-Item -LiteralPath (Join-Path $Repo 'scripts/install-cuda-detect.ps1') -Destination (Join-Path $Stage 'scripts')
    if ($WheelPath) {
        $Wheel = Get-Item -LiteralPath $WheelPath
        if ($Wheel.Extension -ne '.whl') { throw 'WheelPath must name a built wheel.' }
        Copy-Item -LiteralPath $Wheel.FullName -Destination $Stage
    }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $Zip = Join-Path $OutputDirectory 'payload.zip'
    if (Test-Path -LiteralPath $Zip) { Remove-Item -LiteralPath $Zip }
    [IO.Compression.ZipFile]::CreateFromDirectory($Stage, $Zip)
    $Compiler = Join-Path $env:WINDIR 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
    if (-not (Test-Path -LiteralPath $Compiler)) { throw 'The Windows .NET Framework C# compiler is required.' }
    $Exe = Join-Path $OutputDirectory 'OCR-Simple-GUI-Setup.exe'
    & $Compiler /nologo /target:winexe /platform:x64 /optimize+ /warnaserror+ /reference:System.Windows.Forms.dll /reference:System.Drawing.dll /reference:System.Web.Extensions.dll /reference:System.IO.Compression.dll /reference:System.IO.Compression.FileSystem.dll "/resource:$Zip,payload.zip" "/out:$Exe" (Join-Path $PSScriptRoot 'Bootstrapper.cs')
    if ($LASTEXITCODE -ne 0) { throw "Compiler failed: $LASTEXITCODE" }
    Write-Output $Exe
} finally { Remove-Item -LiteralPath $Stage -Recurse -Force }
