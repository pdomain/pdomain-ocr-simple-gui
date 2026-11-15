$ErrorActionPreference = 'Stop'
$Repo = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$Tokens = $null
$Errors = $null
$Ast = [Management.Automation.Language.Parser]::ParseFile((Join-Path $Repo 'uninstall.ps1'), [ref]$Tokens, [ref]$Errors)
if ($Errors.Count) { throw 'Uninstall script does not parse.' }
$Function = $Ast.Find({ param($Node) $Node -is [Management.Automation.Language.FunctionDefinitionAst] -and $Node.Name -eq 'Invoke-DesktopPreparation' }, $true)
. ([scriptblock]::Create($Function.Extent.Text))
function Fake-ToolPython {
    $script:Observed = @($args)
    $global:LASTEXITCODE = 0
    '{"prepared":true}'
}
$Previous = $env:UV_TOOL_DIR
try {
    $env:UV_TOOL_DIR = 'C:\isolated tools'
    $null = Invoke-DesktopPreparation -Python 'Fake-ToolPython'
    $Index = [Array]::IndexOf($script:Observed, '--tool-dir')
    if ($Index -lt 0 -or $script:Observed[$Index + 1] -ne $env:UV_TOOL_DIR) { throw 'Preparation did not receive the exact tool inventory directory.' }
    Write-Output 'Preparation CLI inventory contract passed.'
} finally { $env:UV_TOOL_DIR = $Previous }
