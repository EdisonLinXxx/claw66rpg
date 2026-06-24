<#
.SYNOPSIS
Runs the h5 runner main-button validation harness.

.EXAMPLE
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-main-buttons.ps1

.EXAMPLE
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-main-buttons.ps1 -Buttons 8 -Out C:\tmp\claw_verify_button8
#>

param(
    [string]$Python = "python",
    [string]$Buttons = "",
    [string]$Out = $(if ($IsWindows -or $env:OS -eq "Windows_NT") { "C:\tmp\claw_verify_main_full" } else { "/tmp/claw_verify_main_full" }),
    [ValidateSet("full", "debug-jump")]
    [string]$RouteMode = "full",
    [int]$Port = 8765,
    [switch]$Headed,
    [switch]$MirrorMissing
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$validator = Join-Path $repoRoot "66rpgProjectDropper\validate_main_buttons.py"

$arguments = @(
    $validator,
    "--root", $repoRoot,
    "--out", $Out,
    "--port", [string]$Port,
    "--route-mode", $RouteMode
)

if ($Buttons.Trim()) {
    $arguments += @("--buttons", $Buttons)
}

if ($Headed) {
    $arguments += "--headed"
}

if ($MirrorMissing) {
    $arguments += "--mirror-missing"
}

& $Python @arguments
exit $LASTEXITCODE
