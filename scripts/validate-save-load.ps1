<#
.SYNOPSIS
Validates save, reload, restore, and continue-play behavior for the h5 runner.

.EXAMPLE
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-save-load.ps1

.EXAMPLE
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-save-load.ps1 -SaveAfterSteps 24 -AdvanceSteps 8 -ContinueSteps 5 -Out C:\tmp\claw_save_load
#>

param(
    [string]$Python = "python",
    [string]$Out = $(if ($IsWindows -or $env:OS -eq "Windows_NT") { "C:\tmp\claw_save_load" } else { "/tmp/claw_save_load" }),
    [int]$Port = 8765,
    [int]$Slot = 0,
    [int]$SaveAfterSteps = 24,
    [int]$AdvanceSteps = 8,
    [int]$ContinueSteps = 5,
    [int]$MaxNoStateSteps = 60,
    [ValidateSet("round-robin", "first", "last")]
    [string]$ChoicePolicy = "round-robin",
    [string]$MainButtons = "0,1,2,3,4,5,6,7,9,10,11",
    [switch]$Headed,
    [switch]$MirrorMissing
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$validator = Join-Path $repoRoot "66rpgProjectDropper\validate_save_load.py"

$arguments = @(
    $validator,
    "--root", $repoRoot,
    "--out", $Out,
    "--port", [string]$Port,
    "--slot", [string]$Slot,
    "--save-after-steps", [string]$SaveAfterSteps,
    "--advance-steps", [string]$AdvanceSteps,
    "--continue-steps", [string]$ContinueSteps,
    "--max-no-state-steps", [string]$MaxNoStateSteps,
    "--choice-policy", $ChoicePolicy,
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
