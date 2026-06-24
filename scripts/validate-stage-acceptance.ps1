<#
.SYNOPSIS
Runs first-game stage acceptance checks and writes a combined report.

.EXAMPLE
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-stage-acceptance.ps1

.EXAMPLE
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-stage-acceptance.ps1 -Buttons 0 -AutoplayDurationSeconds 60 -AutoplayMaxSteps 80 -Out C:\tmp\claw_stage_acceptance_smoke

.EXAMPLE
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-stage-acceptance.ps1 -SkipMainButtons:$false
#>

param(
    [string]$Python = "python",
    [string]$Out = $(if ($IsWindows -or $env:OS -eq "Windows_NT") { "C:\tmp\claw_stage_acceptance" } else { "/tmp/claw_stage_acceptance" }),
    [string]$Buttons = "",
    [ValidateSet("full", "debug-jump")]
    [string]$RouteMode = "debug-jump",
    [int]$MainPort = 8765,
    [int]$AutoplayPort = 8865,
    [int]$SaveLoadPort = 8765,
    [int]$AutoplayDurationSeconds = 300,
    [int]$AutoplayMaxSteps = 250,
    [ValidateSet("round-robin", "first", "last")]
    [string]$ChoicePolicy = "round-robin",
    [string]$MainButtons = "0,1,2,3,4,5,6,7,9,10,11",
    [int]$Slot = 0,
    [int]$SaveAfterSteps = 24,
    [int]$AdvanceSteps = 8,
    [int]$ContinueSteps = 5,
    [int]$DebugJumpStoryId = 44,
    [int]$DebugJumpIndex = 5,
    [int]$RestoreSettleSteps = 8,
    [int]$MaxNoStateSteps = 60,
    [bool]$SkipMainButtons = $false,
    [switch]$SkipAutoplay,
    [switch]$SkipSaveLoad,
    [switch]$Headed,
    [switch]$MirrorMissing
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$validator = Join-Path $repoRoot "66rpgProjectDropper\validate_stage_acceptance.py"
$saveLoadScript = Join-Path $PSScriptRoot "validate-save-load.ps1"
$mainButtonsScript = Join-Path $PSScriptRoot "validate-main-buttons.ps1"
$autoplayScript = Join-Path $PSScriptRoot "autoplay-story.ps1"

New-Item -ItemType Directory -Force -Path $Out | Out-Null
$failed = 0

if (-not $SkipSaveLoad) {
    $saveArgs = @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $saveLoadScript,
        "-Python", $Python,
        "-Out", (Join-Path $Out "save_load"),
        "-Port", [string]$SaveLoadPort,
        "-Slot", [string]$Slot,
        "-SaveAfterSteps", [string]$SaveAfterSteps,
        "-AdvanceSteps", [string]$AdvanceSteps,
        "-ContinueSteps", [string]$ContinueSteps,
        "-DebugJumpStoryId", [string]$DebugJumpStoryId,
        "-DebugJumpIndex", [string]$DebugJumpIndex,
        "-RestoreSettleSteps", [string]$RestoreSettleSteps,
        "-MaxNoStateSteps", [string]$MaxNoStateSteps,
        "-ChoicePolicy", $ChoicePolicy,
        "-MainButtons", $MainButtons
    )
    if ($Headed) { $saveArgs += "-Headed" }
    if ($MirrorMissing) { $saveArgs += "-MirrorMissing" }
    & powershell @saveArgs
    if ($LASTEXITCODE -ne 0) { $failed = 1 }
}

if (-not $SkipMainButtons) {
    $mainArgs = @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $mainButtonsScript,
        "-Python", $Python,
        "-Out", (Join-Path $Out "main_buttons"),
        "-Port", [string]$MainPort,
        "-RouteMode", $RouteMode
    )
    if ($Buttons.Trim()) { $mainArgs += @("-Buttons", $Buttons) }
    if ($Headed) { $mainArgs += "-Headed" }
    if ($MirrorMissing) { $mainArgs += "-MirrorMissing" }
    & powershell @mainArgs
    if ($LASTEXITCODE -ne 0) { $failed = 1 }
}

if (-not $SkipAutoplay) {
    $autoplayArgs = @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $autoplayScript,
        "-Python", $Python,
        "-Out", (Join-Path $Out "story_autoplay"),
        "-Port", [string]$AutoplayPort,
        "-DurationSeconds", [string]$AutoplayDurationSeconds,
        "-MaxSteps", [string]$AutoplayMaxSteps,
        "-ChoicePolicy", $ChoicePolicy,
        "-MainButtons", $MainButtons
    )
    if ($Headed) { $autoplayArgs += "-Headed" }
    if ($MirrorMissing) { $autoplayArgs += "-MirrorMissing" }
    & powershell @autoplayArgs
    if ($LASTEXITCODE -ne 0) { $failed = 1 }
}

$summaryArgs = @(
    $validator,
    "--root", $repoRoot,
    "--out", $Out,
    "--route-mode", $RouteMode,
    "--main-port", [string]$MainPort,
    "--autoplay-port", [string]$AutoplayPort,
    "--save-load-port", [string]$SaveLoadPort,
    "--autoplay-duration-seconds", [string]$AutoplayDurationSeconds,
    "--autoplay-max-steps", [string]$AutoplayMaxSteps,
    "--choice-policy", $ChoicePolicy,
    "--main-buttons", $MainButtons,
    "--slot", [string]$Slot,
    "--save-after-steps", [string]$SaveAfterSteps,
    "--advance-steps", [string]$AdvanceSteps,
    "--continue-steps", [string]$ContinueSteps,
    "--debug-jump-story-id", [string]$DebugJumpStoryId,
    "--debug-jump-index", [string]$DebugJumpIndex,
    "--restore-settle-steps", [string]$RestoreSettleSteps,
    "--max-no-state-steps", [string]$MaxNoStateSteps,
    "--summarize-only"
)

if ($Buttons.Trim()) { $summaryArgs += @("--buttons", $Buttons) }
if ($SkipSaveLoad) { $summaryArgs += "--skip-save-load" }
if ($SkipMainButtons) { $summaryArgs += "--skip-main-buttons" }
if ($SkipAutoplay) { $summaryArgs += "--skip-autoplay" }
if ($Headed) { $summaryArgs += "--headed" }
if ($MirrorMissing) { $summaryArgs += "--mirror-missing" }

& $Python @summaryArgs
if ($LASTEXITCODE -ne 0) { $failed = 1 }

exit $failed
