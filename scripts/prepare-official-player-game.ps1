<#
.SYNOPSIS
Prepares a game-specific resource bundle for official_player_proxy.html.

.EXAMPLE
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\prepare-official-player-game.ps1 -GameUrl https://www.66rpg.com/game/1692785
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$GameUrl,

    [string]$Downloads = ".dry-run-downloads",
    [string[]]$CdnHost = @("https://dlcdn1.cgyouxi.com", "https://c2.cgyouxi.com", "https://c3.cgyouxi.com", "https://c4.cgyouxi.com")
)

$ErrorActionPreference = "Stop"

function Resolve-RepoRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function Get-GameInfo {
    param([string]$Url)

    $html = (Invoke-WebRequest -UseBasicParsing -Uri $Url -Headers @{
        "User-Agent" = "Mozilla/5.0 OfficialPlayerProxyPrep/1.0"
        "Accept-Language" = "zh-CN,zh;q=0.9"
    } -TimeoutSec 30).Content

    $match = [regex]::Match($html, "window\.GAME_INFO_DATA\s*=\s*(\{[\s\S]*?\});")
    if (-not $match.Success) {
        throw "GAME_INFO_DATA not found in $Url"
    }

    return $match.Groups[1].Value | ConvertFrom-Json
}

function Save-FirstAvailable {
    param(
        [string[]]$Hosts,
        [string]$RelativePath,
        [string]$Target
    )

    $lastError = $null
    foreach ($hostName in $Hosts) {
        $url = $hostName.TrimEnd("/") + "/" + $RelativePath.TrimStart("/")
        try {
            Invoke-WebRequest -UseBasicParsing -Uri $url -Headers @{
                "User-Agent" = "Mozilla/5.0 OfficialPlayerProxyPrep/1.0"
                "Referer" = "https://www.66rpg.com/"
            } -OutFile $Target -TimeoutSec 60
            return $url
        } catch {
            $lastError = $_.Exception.Message
        }
    }
    throw "Failed to download $RelativePath. Last error: $lastError"
}

$repoRoot = Resolve-RepoRoot
$info = Get-GameInfo -Url $GameUrl
$gameId = [string]$info.gindex
$guid = [string]$info.guid
$version = [string]$info.cur_version
if (-not $version) {
    $version = [string]$info.version
}
if (-not $gameId -or -not $guid -or -not $version) {
    throw "Missing game metadata: gameId=$gameId guid=$guid version=$version"
}

$bundleDir = Join-Path $repoRoot (Join-Path $Downloads (Join-Path "games" (Join-Path $guid $version)))
New-Item -ItemType Directory -Path $bundleDir -Force | Out-Null

$mapTarget = Join-Path $bundleDir "Map_32.bin"
$miniTarget = Join-Path $bundleDir "Game_mini.bin"
$basePath = "web/$guid/$version"
$mapUrl = Save-FirstAvailable -Hosts $CdnHost -RelativePath "$basePath/Map_32.bin" -Target $mapTarget
$miniUrl = Save-FirstAvailable -Hosts $CdnHost -RelativePath "$basePath/Game_mini.bin" -Target $miniTarget

Write-Host "gameId=$gameId"
Write-Host "title=$($info.gname)"
Write-Host "author=$($info.author_uname)"
Write-Host "guid=$guid"
Write-Host "version=$version"
Write-Host "bundle=$bundleDir"
Write-Host "map=$mapTarget"
Write-Host "map_url=$mapUrl"
Write-Host "game_mini=$miniTarget"
Write-Host "game_mini_url=$miniUrl"
Write-Host "entry=/play-proxy/official_player_proxy.html?gameId=$gameId&guid=$guid&version=$version"
