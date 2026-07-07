<#
.SYNOPSIS
Runs the primary local play server.

.EXAMPLE
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\serve-play.ps1
#>

param(
    [string]$Python = "python",
    [string]$HostName = "127.0.0.1",
    [int]$Port = 8766
)

$ErrorActionPreference = "Stop"

$script = Join-Path $PSScriptRoot "serve-official-proxy.ps1"

& powershell -NoProfile -ExecutionPolicy Bypass -File $script -Python $Python -HostName $HostName -Port $Port
