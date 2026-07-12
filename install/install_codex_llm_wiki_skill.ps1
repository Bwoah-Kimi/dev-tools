#Requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RemainingArgs
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$installer = Join-Path $repoRoot 'modules\llm-wiki-skill\install.ps1'

if (-not (Test-Path -LiteralPath $installer)) {
    Write-Error "llm-wiki submodule is not initialized: $installer`nRun: git submodule update --init --recursive"
    exit 1
}

$installerArgs = @('--platform', 'codex')
if ($RemainingArgs) {
    $installerArgs += $RemainingArgs
}

& $installer @installerArgs
$installExitCode = $LASTEXITCODE
if ($installExitCode -ne 0) {
    exit $installExitCode
}

if ($RemainingArgs -contains '--dry-run') {
    exit 0
}

$codexHome = if ($env:CODEX_HOME) {
    $env:CODEX_HOME
} else {
    Join-Path $env:USERPROFILE '.codex'
}
$skillDir = Join-Path $codexHome 'skills\llm-wiki'
$sourceDir = Join-Path $repoRoot 'modules\llm-wiki-skill'
$sourceMarker = Join-Path $skillDir '.llm-wiki-source'
$utf8WithoutBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($sourceMarker, $sourceDir + [Environment]::NewLine, $utf8WithoutBom)
Write-Host "[llm-wiki] Managed source recorded: $sourceDir" -ForegroundColor Green

exit 0
