<#
.SYNOPSIS
Runs the h5 runner story autoplay harness.

.EXAMPLE
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\autoplay-story.ps1 -DurationSeconds 60

.EXAMPLE
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\autoplay-story.ps1 -DurationSeconds 180 -Out C:\tmp\claw_autoplay_180s
#>

param(
    [string]$Python = "python",
    [int]$DurationSeconds = 300,
    [int]$MaxSteps = 250,
    [string]$Out = $(if ($IsWindows -or $env:OS -eq "Windows_NT") { "C:\tmp\claw_autoplay" } else { "/tmp/claw_autoplay" }),
    [int]$Port = 8865,
    [ValidateSet("round-robin", "first", "last")]
    [string]$ChoicePolicy = "round-robin",
    [int]$ChoiceLoopEscapeAfter = 4,
    [string]$MainButtons = "0,1,2,3,4,5,6,7,9,10,11",
    [switch]$Headed,
    [switch]$MirrorMissing
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$autoplay = Join-Path $repoRoot "66rpgProjectDropper\auto_play_story.py"

$arguments = @(
    $autoplay,
    "--root", $repoRoot,
    "--out", $Out,
    "--port", [string]$Port,
    "--duration-seconds", [string]$DurationSeconds,
    "--max-steps", [string]$MaxSteps,
    "--choice-policy", $ChoicePolicy,
    "--choice-loop-escape-after", [string]$ChoiceLoopEscapeAfter,
    "--main-buttons", $MainButtons
)

if ($Headed) {
    $arguments += "--headed"
}

if ($MirrorMissing) {
    $arguments += "--mirror-missing"
}

& $Python @arguments
exit $LASTEXITCODE
