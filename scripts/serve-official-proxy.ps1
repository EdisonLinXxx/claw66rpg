<#
.SYNOPSIS
Runs the official-player local resource/API proxy.

.EXAMPLE
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\serve-official-proxy.ps1
#>

param(
    [string]$Python = "python",
    [string]$HostName = "127.0.0.1",
    [int]$Port = 8766
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$server = Join-Path $repoRoot "official_player_proxy.py"

& $Python $server --host $HostName --port $Port --root $repoRoot
