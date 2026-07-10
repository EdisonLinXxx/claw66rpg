<#
.SYNOPSIS
Runs the independent modern 66RPG local player.

.EXAMPLE
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\serve-modern-player.ps1
#>

param(
    [string]$Python = "python",
    [string]$HostName = "127.0.0.1",
    [int]$Port = 8788
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$server = Join-Path $repoRoot "modern_player_server.py"

& $Python $server --host $HostName --port $Port --root $repoRoot
exit $LASTEXITCODE
