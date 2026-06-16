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

- isolated click classification was completed for the stable first-scene `UI TARGETS`
- `(536,413)` is state-sensitive: in an isolated run it advanced into create-character resources rather than remaining a no-op
- `(632,417)` and `(775,429)` open/load save-file UI paths
- `(582,129)` opens/loads settings UI
- `(921,54)` opens the main menu overlay
- `(921,124)` reaches a platform/API boundary with malformed `get_game_info` JSONP URL
- the first `(921,54)` probe exposed a real menu/UI resource wave; `prepare_runner_mirror.py --mirror-log .http-server.err.log` mirrored the missing mapped assets
- after mirroring, repeating `(921,54)` returned the former menu `/shareres` requests as `200`
- only the known two `/null%20path` 404s remain in the retest window
- first-level main menu overlay classification is now complete
- resource-heavy menu subviews, including mall, backpack/items, welfare/event, gallery, pet/sign-in/wardrobe/image assets, were mirrored from the HTTP log
- representative retests for mall, backpack/items, and welfare/event targets no longer show real `/shareres/<md5>` 404s
- mall still emits `Script error. @ :0:0`, likely a platform/shop service boundary rather than a static asset problem
- second-level submenu probing is now complete for representative backpack/items, welfare/event, CG/gallery, and two-button submenu targets
- second-level retests after mirroring no longer show real `/shareres/<md5>` 404s; only known `/null%20path` requests remain
- deeper two-button submenu targets have been classified: `(432,478)` is confirm/transition-like, `(617,474)` is refresh/reopen-like, and `(925,503)` closes/returns
- two-button deeper probing exposed `称号4.jpg` and `称号2.jpg`; both are now mirrored and return `200`
- backpack deeper probing found `(925,496)` is close/return, while `(672,193)` and `(343,327)` did not hit effective buttons in the sampled states
- welfare/event right-side target `(956,65)` still exposes no further inner target set after a 9-second stabilization wait
- `UI TARGETS` now includes reliable `x/y` aliases, bounds, texture hints, listener lists, and `likelyInteractive`
- first-scene target output was revalidated after the trace enhancement and still returns the expected 7 clickable targets
- enhanced backpack reprobe showed the previous approximate point `(672,193)` is not an emitted clickable target in `bp.6`
- actual `bp.6` deeper/action targets include `(626,320)` and `(785,354)`; both emit `CLICK_SCUI_BUTTON` but keep the target set stable in the sample window
- `bp.6` bottom slots `(210,476)`, `(331,476)`, `(451,476)`, `(570,476)`, `(690,476)`, and `(810,476)` are all valid clickable targets; each emits `CLICK_SCUI_BUTTON`, keeps target count stable at 25, and exposes no new real `/shareres/<md5>` 404

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

## Latest Isolated Target Classification

| Target path | Coordinate | Behavior |
| --- | --- | --- |
| `stage.0.3.0.0` | `(536,413)` | dialogue/branch advance into create-character resources |
| `stage.0.3.0.1` | `(632,417)` | save-file UI |
| `stage.0.3.0.2` | `(775,429)` | save-file UI plus extra resource wave |
| `stage.0.3.0.3` | `(678,128)` | branch/menu transition; target set reduced |
| `stage.0.3.0.4` | `(582,129)` | settings UI |
| `stage.0.7.0` | `(921,54)` | main menu overlay; resource wave now mirrored |
| `stage.0.7.1` | `(921,124)` | platform/API boundary; malformed `get_game_info` JSONP |

## Latest Second-Level Findings

| Path | Tested targets | Current result |
| --- | --- | --- |
| Backpack/items | `(74,46)` through `(74,422)`, `(46,481)`, `(159,69)`, `(159,184)`, `(159,299)` | Category/page switching works; `(74,328)` exposed title/sign-in resources now mirrored; side/detail slots mostly emit `CLICK_SCUI_BUTTON` without meaningful target-set change. |
| Welfare/event | right-side targets around `x=956`, left target `(74,465)` | Right-side vertical menu targets emit `CLICK_SCUI_BUTTON` and keep the menu pattern; left target collapses/returns to the first-scene/right-button target set. |
| CG/gallery | `(536,413)`, `(632,417)`, `(775,429)` | Gallery item clicks emit `SHOW_CG_UI_ITEM_MSG` and `SHOW_CG_UI_ITEM`; no mapped resource miss. |
| Two-button submenu | `(124,182)`, `(124,221)` | Top option opens a deeper UI with targets near `(432,478)`, `(617,474)`, `(925,503)`; bottom option is mostly no-op/menu remains. |

Second-level resource-miss loop:

- newly mirrored mapped misses include title/label, sign-in button, locked-title, and `audio/se/error_1.mp3`
- representative retests for backpack `bp.6`, welfare `wf.0`, and welfare `wf.left` show no new real `/shareres/<md5>` `404`
- browser autoplay `NotAllowedError` during automated reloads is currently treated as noise, not a game-resource failure

## Latest Deeper UI Findings

| Path | Tested targets | Current result |
| --- | --- | --- |
| Two-button deeper UI | `(432,478)`, `(617,474)`, `(925,503)` | `(432,478)` triggers a transition/resource load and reduces the target set; `(617,474)` reloads/keeps the deeper UI; `(925,503)` closes back to first-scene/right-button targets. |
| Backpack deeper pages | `(925,496)`, `(672,193)`, `(343,327)` | `(925,496)` is a reliable close/return target; the other two sampled coordinates did not trigger effective button events in their sampled states. |
| Welfare/event longer wait | `(956,65)` plus 9s wait | Target set stayed at 14 and no deeper inner target set appeared. |
| Backpack enhanced reprobe | `bp.6` exact targets `(626,320)`, `(785,354)` | Both are real emitted targets with click listeners and emit `CLICK_SCUI_BUTTON`; target set remains stable and no new resource wave appears. |
| Backpack `bp.6` bottom slots | `(210,476)`, `(331,476)`, `(451,476)`, `(570,476)`, `(690,476)`, `(810,476)` | All are real emitted targets and emit `CLICK_SCUI_BUTTON`; target set remains 25; only `(331,476)` onward show one image-load event; no script error and no new resource miss. |

Latest resource-miss loop:

- newly mirrored mapped misses from two-button deeper UI:
  - `c5be296d8fc3dfb5ac20bbbbb180b4a1` -> `graphics/other/称号/称号/称号4.jpg`
  - `87d0fc55a07cda95560a418edefb542a` -> `graphics/other/称号/称号/称号2.jpg`
- after retest, both returned `200`
- no new real `/shareres/<md5>` 404 was observed during the backpack deeper and welfare long-wait checks

## Latest Target Trace Improvements

`traceUiState=1` now emits richer target metadata:

- center aliases: `x`, `y`, `cx`, `cy`
- visible/click bounds: `left`, `top`, `right`, `bottom`, `w`, `h`
- event metadata: `listeners`, `mouseEnabled`, `likelyInteractive`
- resource hints: inherited single-child `texture`
- coordinate source: `boundsSource`

Validation after a cache-busted reload:

- first-scene target count: 7
- known centers preserved: `(536,413)`, `(632,417)`, `(775,429)`, `(678,128)`, `(582,129)`, `(921,54)`, `(921,124)`
- main-menu target output retains known target centers while adding listener and bounds metadata

## Next Debug Direction

### Priority 1: Platform/Service Boundary

- static assets are now mirrored
- remaining `Script error. @ :0:0` likely needs platform/shop API stubs or deeper runtime hooks

Treat `stage.0.6.0.2` / mall as the next platform-service target:

1. Capture the exact stack around `LOAD_UI_RESOURCE_COMPLETE:NEW_MALLUI_TYPE`.
2. Stub or intercept the shop/platform service calls needed after `data/mallnew.bin`.
3. Distinguish malformed URL bugs from missing platform response data.
4. Retest mall after stubbing to see whether the `Script error. @ :0:0` disappears.

### Priority 2: Runtime State Trace For Silent Backpack Clicks

The exact `bp.6` clickable targets are now classified at the UI/resource level. If backpack behavior still matters, the next useful step is not more coordinate probing; it is state tracing:

1. hook variable/save mutations around `CLICK_SCUI_BUTTON`
2. capture selected category/page/item ids
3. compare before/after snapshots for `(626,320)`, `(785,354)`, and bottom slots
4. decide whether these controls are intentionally silent, locked, or waiting on game state

### Priority 3: Continue Resource-Miss Loop

If a target triggers a new real `/shareres/<md5>` 404:

1. use `Map.bin` to resolve MD5 to original asset path
2. mirror that MD5 locally with `prepare_runner_mirror.py`
3. reload and repeat the same click path
4. commit/push each verification round

Example mirror command:

```powershell
python 66rpgProjectDropper\prepare_runner_mirror.py 1569947 --version 364 --root . --mirror-md5 <md5> --mirror-log .http-server.err.log
```

### Priority 4: Better Runtime State Trace

If isolated clicks do not clearly classify behavior, add trace hooks for:

- mouse/touch event dispatch on Laya display nodes
- current story id / chapter id / command pointer if discoverable
- selected menu/custom UI id
- dialogue text state
- save/global variable state changes

Goal:

- detect gameplay progress even when visual targets do not visibly change.

### Priority 5: Deeper `/null path` Source

Only pursue this if it becomes blocking.

Potential hooks:

- `Laya.URL.formatURL`
- Laya internal loader URL normalization
- resource manager path conversion functions
- image texture creation from empty path

Goal:

- determine whether `/null path` is harmless empty-image behavior or a real missing asset reference.

### Priority 6: Platform Feature Boundary

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
