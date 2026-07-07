<#
.SYNOPSIS
Runs the primary official-player proxy page validation harness.

.EXAMPLE
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-official-proxy-pages.ps1

.EXAMPLE
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-official-proxy-pages.ps1 -Out C:\tmp\official_proxy_main_pages_smoke -Headed
#>

param(
    [string]$Python = "python",
    [string]$HostName = "127.0.0.1",
    [int]$Port = 8766,
    [string]$Out = $(if ($IsWindows -or $env:OS -eq "Windows_NT") { "C:\tmp\official_proxy_main_pages" } else { "/tmp/official_proxy_main_pages" }),
    [switch]$NoStartServer,
    [switch]$Headed
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$validator = Join-Path $repoRoot "66rpgProjectDropper\validate_official_proxy_pages.py"

$arguments = @(
    $validator,
    "--root", $repoRoot,
    "--out", $Out,
    "--host", $HostName,
    "--port", [string]$Port,
    "--python", $Python
)

if ($NoStartServer) {
    $arguments += "--no-start-server"
}

if ($Headed) {
    $arguments += "--headed"
}

& $Python @arguments
exit $LASTEXITCODE
