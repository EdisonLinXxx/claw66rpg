<#
.SYNOPSIS
Runs the official-player local resource/API proxy.

.EXAMPLE
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\serve-official-proxy.ps1
#>

param(
    [string]$Python = "python",
    [string]$HostName = "127.0.0.1",
    [int]$Port = 8766,
    [switch]$PlatformUnlock,
    [switch]$NoPlatformUnlock,
    [switch]$DevFreeUnlock
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$server = Join-Path $repoRoot "official_player_proxy.py"

$argsList = @($server, "--host", $HostName, "--port", $Port, "--root", $repoRoot)
if ($NoPlatformUnlock) {
    $argsList += "--no-platform-unlock"
}
if ($PlatformUnlock -or $DevFreeUnlock) {
    $argsList += "--platform-unlock"
}

& $Python @argsList
