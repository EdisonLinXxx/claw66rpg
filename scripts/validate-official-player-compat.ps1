[CmdletBinding()]
param(
    [string]$Node = "node"
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

& (Join-Path $PSScriptRoot "build-official-player-compat.ps1") -Check
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$parserModule = Join-Path $repoRoot "official_player_compat_src\50-binary-parser.js"
$parserText = Get-Content -Raw -Encoding UTF8 $parserModule
if ($parserText -match "[0-9a-fA-F]{32}") {
    throw "Binary parser module contains a game GUID. Move matching rules into 05-game-profiles.js."
}

& $Node --check (Join-Path $repoRoot "official_player_compat.js")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $Node (Join-Path $repoRoot "66rpgProjectDropper\validate_official_compat_profiles.js")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "official player compatibility validation passed"
