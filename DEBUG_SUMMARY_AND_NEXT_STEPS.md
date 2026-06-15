# 66RPG Game Grab/Run Technical Debug Summary

## Scope

- Target platform reference: `https://www.66rpg.com`
- Target game page: `https://www.66rpg.com/game/1569947`
- Game name observed from runtime: `【区半挂件】美人客栈`
- Goal: verify whether a 66RPG game package and required runtime resources can be fetched, mirrored locally, and run inside our own local test page.
- Legal/commercial evaluation is intentionally out of scope for this technical validation document.

## Repository And Test Harness

- Test repo: `https://github.com/EdisonLinXxx/claw66rpg.git`
- Local working directory used for validation: `D:\remote\wuming\乙女恋爱物语\.tmp-claw66rpg`
- Source reference copied into the test repo: `PeaShooterR/fuck66rpg`
- Main local runner: `h5_runner_experiment.html`
- Mirror helper: `66rpgProjectDropper/prepare_runner_mirror.py`
- Full round-by-round raw log: `VERIFY_LOG.md`
- Local mirrored resources directory: `shareres/`
  - This directory is intentionally not committed.
  - It contains locally mirrored CDN resources needed by the runner.

## Game Package Facts

- Game id: `1569947`
- GUID: `0a235c54f16c431ab5736c92997edb47`
- Version: `364`
- Runtime package version observed by H5 player: `108`
- Runtime dimensions: `960x540`
- Main bin: `data/game.bin`
- Main bin size: `47,345,898` bytes
- Main bin MD5: `7b633df854b9742c1a653e134ee6f2d8`
- Main bin magic/header: starts with `ORGDAT`
- `Map.bin` resource map entries: `11112`

Current conclusion: downloading the game package and resolving mapped static resources is technically feasible.

## Public Runtime Facts

- Official game pages tested all point to the same public H5 player:
  - `https://c2.cgyouxi.com/website/hfplayer/v2/bin/main.min.js?v=20210202002`
- `main.min.js` query parameters are cache busters only.
- Tested `hfplayer/v1`, `hfplayer/v3`, debug paths, and common `main.js` candidates did not expose a usable alternate runtime.

Current conclusion: the available public runtime is a fixed old player. Compatibility must be handled by runner-side patches or by reimplementing enough parsing/runtime behavior.

## Parser Debug History

### Initial Failure

- Initial local runner could initialize the official H5 player.
- It failed in `readGameBin` with:
  - `getInt32 error - Out of bounds`
- The failure reproduced both from CDN resources and local mirrored resources.

Conclusion: the failure was not caused by CORS, CDN access, or local serving. It was a binary parser/runtime compatibility issue.

### DSystem Button Schema Mismatch

- Trace path:
  - `DMain -> DHeader -> DSystem`
- The public player reads a DSystem button count of `80`.
- Offline scanning showed the binary actually contains `453` button-shaped records.
- A one-byte pad exists before many button records.
- Skipping that pad allowed parsing to advance beyond the original failure.

Conclusion: this game uses a newer DSystem layout than the public player expects.

### Custom UI Layout Mismatch

- After fixing button parsing, the next mismatch was in `DCustomUIData`.
- New observed layout:
  - `UIInitSave`
  - `CuiCount=1000`
  - repeated custom UI blocks:
    - `DeclaredSize`
    - marker
    - load events
    - controls
    - show/mouse/key event sections
  - `MenuIndex`
- All `1000` custom UI blocks can be parsed with the patched layout.
- Patched parse reaches the end of `game.bin` at `pos=47345898`.

Current conclusion: the game binary can be parsed through `DMain` using runner-side schema patches.

## Local Runner Patches

The runner currently uses query flags to enable controlled patches and diagnostics.

Recommended validation URL:

```text
http://127.0.0.1:8765/h5_runner_experiment.html?localRes=1&patchNewDSystem=1&traceRuntime=1&traceTitle=1&traceNullPath=1&quietOafEvents=1&traceUiState=1&patchTitleClick=1&clearStorage=1&hideDebug=1
```

Important flags:

- `localRes=1`
  - serves mapped resources from local `shareres/`.
- `patchNewDSystem=1`
  - applies the patched DSystem/custom UI parser path.
- `traceRuntime=1`
  - logs runtime stage state and key runtime calls.
- `traceTitle=1`
  - logs title screen configuration and title button data.
- `patchTitleClick=1`
  - shims local click/touch events to start the story from the title cover.
- `traceNullPath=1`
  - traces likely JS paths that might emit `null path` requests.
- `quietOafEvents=1`
  - suppresses repetitive OAF animation frame `LOAD_IMAGE_COMPLETE` logs.
- `traceUiState=1`
  - logs current Laya stage nodes and likely clickable `UI TARGETS`.

## Runtime Progress Achieved

The local runner can currently:

- load the official public H5 player
- load local mirrored `game.bin`
- parse patched game data through `DMain`
- load the title UI
- patch title cover click
- enter the first story scene
- load first scene background resources
- load first scene UI resources
- load create-character related resources
- load dynamic standing/OAF animation frames
- continue at least one step after the first scene after mirroring `audio/se/move_1.mp3`

Current technical conclusion: local operation is possible through early gameplay, but full game flow still needs iterative resource and interaction probing.

## Mirrored Resource Status

Known mirrored resources include:

- main `game.bin`
- startup/title/font/UI assets
- title cover image
- first scene background/audio/UI assets
- create-character assets
- dynamic standing `OAF/OAF2` resources and frame images
- `audio/se/move_1.mp3`
  - MD5: `0839375b26561183ca0bd747ed0dccc3`
  - local size verified: `32641`

Current validation status:

- No new real `/shareres/<md5>` 404 was observed in the latest round.
- Existing local resource requests generally return `200` or `304`.
- The only recurring local 404s are the two known `/null%20path` requests.

## Known Non-Blocking Issues

### `/null path`

- The runtime requests `/null%20path` twice during the first-scene/OAF loading window.
- `traceNullPath=1` wrapped:
  - `XMLHttpRequest.open`
  - `fetch`
  - image/media/source `src`
  - `ORG.loader.load`
  - `Laya.loader.load`
  - `Laya.loader.create`
- None of those wrappers identified the source stack.

Current interpretation:

- This is likely emitted inside Laya's internal path normalization/loading path or another lower-level runtime path.
- It has not blocked title entry, story start, first scene loading, or OAF frame playback.
- Treat it as low priority unless later gameplay becomes blocked by it.

### External Platform API Errors

Observed recurring errors:

- `get_home_gray` JSONP request failure/403
- malformed PropShop URLs such as:
  - `http://https//www.66rpg.com/PropShop/...`
- browser audio autoplay warning:
  - `NotAllowedError: play() failed because the user didn't interact with the document first`

Current interpretation:

- These are platform/account/payment/telemetry related.
- They are not currently blocking the local first-scene resource path.
- They may become important later if save, account, payment, inventory, or platform-specific features are required.

### Screenshot Capture

- Browser screenshot capture often times out during animated runtime scenes.
- Current validation relies on:
  - debug text
  - console events
  - local HTTP status logs
  - `UI STATE` / `UI TARGETS`

## Current UI Target Trace

The latest `traceUiState=1` patch now propagates parent visibility:

- hidden title children are no longer included as click targets
- hidden loading text is no longer included as a click target
- targets are filtered to centers inside the `960x540` stage

Stable first-scene `UI TARGETS` after title click:

| Path | Center | Size | Notes |
| --- | --- | --- | --- |
| `stage.0.3.0.0` | `(536,413)` | `132x50` | clicked once; no target-set change after 4s |
| `stage.0.3.0.1` | `(632,417)` | `54x58` | not yet isolated |
| `stage.0.3.0.2` | `(775,429)` | `69x82` | not yet isolated |
| `stage.0.3.0.3` | `(678,128)` | `45x55` | not yet isolated |
| `stage.0.3.0.4` | `(582,129)` | `54x58` | not yet isolated |
| `stage.0.7.0` | `(921,54)` | `42x52` | not yet isolated |
| `stage.0.7.1` | `(921,124)` | `42x52` | not yet isolated |

## Latest Round Result

Latest pushed commit before this document:

- `122b206 Filter visible UI targets for gameplay probing`

Latest verified behavior:

- title click emits `PATCH TITLE CLICK START`
- first-scene target extraction is clean
- click `(536,413)` did not visibly change the target set
- `LOAD_UI_RESOURCE_COMPLETE` stayed at `1`
- `NULL PATH` stayed at `2`
- no new real `/shareres/<md5>` 404 appeared

## How To Reproduce The Current Validation

From repo root:

```powershell
python -m http.server 8765 --bind 127.0.0.1
```

Open:

```text
http://127.0.0.1:8765/h5_runner_experiment.html?localRes=1&patchNewDSystem=1&traceRuntime=1&traceTitle=1&traceNullPath=1&quietOafEvents=1&traceUiState=1&patchTitleClick=1&clearStorage=1&hideDebug=1
```

Expected manual flow:

1. Wait for the title screen to finish loading.
2. Click the title cover around `(480,270)`.
3. Wait for first scene resources to load.
4. Inspect debug log for latest `UI TARGETS`.
5. Click one target coordinate.
6. Check:
   - whether `UI TARGETS` changed
   - whether `LOAD_UI_RESOURCE_COMPLETE` count changed
   - whether new `/shareres/<md5>` 404 appears in local server logs
   - whether only known `/null%20path` 404 remains

## Next Debug Direction

### Priority 1: Isolated Click Classification

For each stable first-scene target, run an isolated test:

1. reload page with `clearStorage=1`
2. click title cover `(480,270)`
3. wait until first-scene `UI TARGETS` stabilizes
4. click exactly one target
5. wait 3-5 seconds
6. record:
   - target path
   - coordinate
   - before/after `UI TARGETS`
   - before/after event counts
   - new `/shareres/<md5>` 404s
   - new platform/API errors
   - whether it appears to open menu, advance dialogue, or do nothing

Targets to test:

- `(632,417)`
- `(775,429)`
- `(678,128)`
- `(582,129)`
- `(921,54)`
- `(921,124)`
- repeat `(536,413)` only if later evidence suggests it is state-sensitive

Expected output:

- a table mapping each target to behavior:
  - `no-op`
  - `dialogue advance`
  - `menu/settings`
  - `resource wave`
  - `blocked by missing asset`
  - `blocked by platform API`

### Priority 2: Automate Resource-Miss Loop

If a target triggers a new real `/shareres/<md5>` 404:

1. use `Map.bin` to resolve MD5 to original asset path
2. mirror that MD5 locally with `prepare_runner_mirror.py`
3. reload and repeat the same click path
4. commit/push each verification round

Example mirror command:

```powershell
python 66rpgProjectDropper\prepare_runner_mirror.py 1569947 --version 364 --root . --mirror-md5 <md5> --mirror-log .http-server.err.log
```

### Priority 3: Better Runtime State Trace

If isolated clicks do not clearly classify behavior, add trace hooks for:

- mouse/touch event dispatch on Laya display nodes
- current story id / chapter id / command pointer if discoverable
- selected menu/custom UI id
- dialogue text state
- save/global variable state changes

Goal:

- detect gameplay progress even when visual targets do not visibly change.

### Priority 4: Deeper `/null path` Source

Only pursue this if it becomes blocking.

Potential hooks:

- `Laya.URL.formatURL`
- Laya internal loader URL normalization
- resource manager path conversion functions
- image texture creation from empty path

Goal:

- determine whether `/null path` is harmless empty-image behavior or a real missing asset reference.

### Priority 5: Platform Feature Boundary

Later validation should identify which features require 66RPG platform services:

- account/login
- save sync
- inventory/props
- payment/flowers
- ranking/comment/community APIs

Goal:

- define the minimum MVP-compatible subset for our own site.

## MVP Implication For Our Site

Based on current technical validation, the simplest MVP direction is:

- host a local/static game runner page
- mirror only the resources needed for selected games
- support basic start/play flow
- initially ignore or stub platform APIs that are not needed for core story playback
- add resource-miss collection tooling for each imported game
- add a simple game detail page and play button, not a full 66RPG platform clone

Current feasibility assessment:

- Static package acquisition: feasible.
- Local resource mirroring: feasible.
- Early H5 runtime execution: feasible with patches.
- Full-game reliable operation: not verified yet.
- Platform feature replacement: not started.
- Next decisive test: isolated target-click classification and continued resource-miss mirroring.
