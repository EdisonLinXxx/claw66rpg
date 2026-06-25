<#
.SYNOPSIS
Runs multiple story autoplay policies and merges coverage evidence.

.EXAMPLE
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\collect-story-coverage.ps1 -DurationSeconds 120

.EXAMPLE
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\collect-story-coverage.ps1 -Policies "round-robin,first,last" -Out C:\tmp\claw_story_coverage
#>

param(
    [string]$Python = "python",
    [int]$DurationSeconds = 120,
    [int]$MaxSteps = 120,
    [int]$TimeoutSeconds = 0,
    [string]$Out = $(if ($IsWindows -or $env:OS -eq "Windows_NT") { "C:\tmp\claw_story_coverage" } else { "/tmp/claw_story_coverage" }),
    [string]$Policies = "round-robin,first,last",
    [string]$MainButtons = "0,1,2,3,4,5,6,7,9,10,11",
    [int]$StartPort = 8895,
    [int]$PortStep = 10,
    [switch]$Headed,
    [switch]$MirrorMissing
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$collector = Join-Path $repoRoot "66rpgProjectDropper\collect_story_coverage.py"

$arguments = @(
    $collector,
    "--root", $repoRoot,
    "--out", $Out,
    "--python", $Python,
    "--duration-seconds", [string]$DurationSeconds,
    "--max-steps", [string]$MaxSteps,
    "--timeout-seconds", [string]$TimeoutSeconds,
    "--policies", $Policies,
    "--main-buttons", $MainButtons,
    "--start-port", [string]$StartPort,
    "--port-step", [string]$PortStep
)

if ($Headed) {
    $arguments += "--headed"
}

if ($MirrorMissing) {
    $arguments += "--mirror-missing"
}

& $Python @arguments
exit $LASTEXITCODE
