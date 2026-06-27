# 66RPG Game Grab/Run Technical Debug Summary

Last updated: 2026-06-26

Previous baseline: 2026-06-23

## Scope

- Target platform reference: `https://www.66rpg.com`
- Target game page: `https://www.66rpg.com/game/1569947`
- Game name observed from runtime: `【区半挂件】美人客栈`
- Local validation goal: verify whether a 66RPG game package, mapped resources, runtime patches, and platform API substitutes can support a playable H5 game inside our own local runner.
- MVP implication: this game is the first technical proof sample. The broader MVP direction is to support importing multiple interactive story games into a unified game library, not to limit the platform to this one game.

## Repository And Test Harness

- Test repo: `https://github.com/EdisonLinXxx/claw66rpg.git`
- Local working directory: `D:\remote\wuming\乙女恋爱物语\.tmp-claw66rpg`
- Source reference copied into the test repo: `PeaShooterR/fuck66rpg`
- Main local runner: `h5_runner_experiment.html`
- Mirror helper: `66rpgProjectDropper/prepare_runner_mirror.py`
- Local mirrored resource directory: `shareres/`
  - The directory is ignored by default.
  - Verified required resources are force-added case by case with `git add -f`.
- Latest local reports and screenshots are under:
  - `C:\tmp\claw_verify\`

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

- Official game pages tested point to the public H5 player:
  - `https://c2.cgyouxi.com/website/hfplayer/v2/bin/main.min.js?v=20210202002`
- `main.min.js` query parameters are cache busters only.
- Tested `hfplayer/v1`, `hfplayer/v3`, debug paths, and common `main.js` candidates did not expose a usable alternate runtime.

Current conclusion: the available public runtime is a fixed old player. Compatibility must be handled by runner-side patches, local stubs, or targeted reimplementation of missing host/platform behavior.

## Parser Debug History

### Initial Failure

- Initial local runner could initialize the official H5 player.
- It failed in `readGameBin` with:
  - `getInt32 error - Out of bounds`
- The failure reproduced from both CDN resources and local mirrored resources.

Conclusion: the failure was not caused by CORS, CDN access, or local serving. It was a binary parser/runtime compatibility issue.

### DSystem Button Schema Mismatch

- Trace path:
  - `DMain -> DHeader -> DSystem`
- The public player reads a DSystem button count of `80`.
- Offline scanning showed the binary contains `453` button-shaped records.
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

## Local Runner Patches And Flags

Recommended validation URL:

```text
http://127.0.0.1:8765/h5_runner_experiment.html?localRes=1&patchNewDSystem=1&traceRuntime=1&traceTitle=1&traceBranchChoice=1&traceNullPath=1&quietOafEvents=1&traceUiState=1&patchTitleClick=1&patchFirstSceneLobbyButtons=1&clearStorage=1&hideDebug=1&traceStoryState=1&traceAutoNameChoice=1&autoStartTitle=1&stubCode214Name=1&stubCode214Birthday=1&stubInitialVitals=1&stubPropShop=1&autoFirstSceneChoice=0&autoCreateCharacterConfirm=1&autoNameChoice=1&autoInnNameChoice=1&runId=latest
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
- `traceBranchChoice=1`
  - logs branch choice decisions such as `BRANCH CHOICE ...`.
- `traceNullPath=1`
  - traces likely JS paths that might emit invalid path requests.
- `quietOafEvents=1`
  - suppresses repetitive OAF animation frame logs.
- `traceUiState=1`
  - logs current Laya stage nodes and likely clickable targets.
- `patchTitleClick=1`
  - shims local click/touch events to start from the title cover.
- `patchFirstSceneLobbyButtons=1`
  - applies local patches for early lobby/create-character/name/birthday/first-scene buttons and hit targets.
- `traceStoryState=1`
  - emits story id, position, event code, links, layers, and UI state.
- `stubCode214Name=1`
  - stubs the initial name input event where browser input bridging is unreliable.
- `stubCode214Birthday=1`
  - stubs birthday/custom UI confirmation.
- `stubInitialVitals=1`
  - initializes early player state needed by the opening story flow.
- `stubPropShop=1`
  - stubs local PropShop JSONP responses for mall/account state.
- `autoFirstSceneChoice=0`
  - chooses the first opening lobby branch for deterministic validation.
- `autoCreateCharacterConfirm=1`
  - advances the create-character confirmation event.
- `autoNameChoice=1`
  - advances the name choice event.
- `autoInnNameChoice=1`
  - advances the inn-name event.

## Current Runtime Progress

The local runner can currently:

- load the official public H5 player
- load local mirrored `game.bin`
- parse patched game data through `DMain`
- load the title UI
- patch title cover click
- enter the first story scene
- complete the early create-character/name/birthday/ability chain
- complete the newbie chest branch
- return from the chest reward into the real opening story (`storyId=44`)
- advance through the opening narrative
- reach the new-player tutorial choice at `storyId=44`, `pos=318`, `Code=101`
- click both `看` and `不看` choices
- enter the tutorial menu at `storyId=44`, `pos=324`, `Code=204`
- display 11 tutorial/gameplay menu buttons
- click the `经营` tutorial entry and advance to the follow-up `继续了解 / 都了解了` choice
- skip the tutorial and enter the inn main screen at `storyId=15`, `pos=648`, `Code=204`
- display the inn main screen background and visible main buttons
- patch inn main-screen button labels so each visible button matches its actual branch target:
  - `厨房 / 订单 / 概况 / 后院 / 经营 / 客房 / 升级 / 售卖 / 员工 / 外观 / 外出 / 分线`

Current technical conclusion: this is no longer limited to early title/first-scene validation. The sample game can now reach the main gameplay hub with no local resource miss in the latest validated path.

## Latest Verified Gameplay Chain

Validated path:

1. Title / auto title start
2. First scene lobby
3. Create-character confirmation
4. Name input/choice
5. Inn-name input/choice
6. Birthday and ability selection
7. Newbie chest screen
8. Left chest reward
9. Opening story `storyId=44`
10. New-player tutorial prompt `看 / 不看`
11. Tutorial menu `storyId=44 pos=324`
12. Tutorial `经营` branch
13. Skip-tutorial branch to inn main screen
14. Inn main screen `storyId=15 pos=648`

Latest important screenshots:

- `C:\tmp\claw_verify\verify_tutorial_menu_pos324.png`
  - shows tutorial/menu buttons visible.
- `C:\tmp\claw_verify\verify_menu_manage_stop.png`
  - shows `经营` tutorial branch follow-up choice visible.
- `C:\tmp\claw_verify\verify_main_screen_pos648.png`
  - shows inn main screen background and visible main buttons.

Latest important reports:

- `C:\tmp\claw_verify\verify_tutorial_menu_report.json`
- `C:\tmp\claw_verify\verify_menu_manage_report.json`
- `C:\tmp\claw_verify\verify_skip_tutorial_report.json`
- `C:\tmp\claw_verify\verify_main_screen_report.json`

Latest validation result:

- Tutorial menu reached: `storyId=44`, `pos=324`, `Code=204`
- Tutorial menu buttons found: `11`
  - `订单`
  - `概况`
  - `后院`
  - `经营`
  - `酒宴`
  - `升级`
  - `售卖`
  - `外出`
  - `————好感————`
  - `员工`
  - `外观`
- Inn main screen reached: `storyId=15`, `pos=648`, `Code=204`
- Runtime main-screen buttons found: `12`
  - same 11 visible buttons above
  - `支线开启`, condition-gated by `主线剧情1 >= 143`
- 2026-06-26 update:
  - commit `5103e6b` aligned the first-scene lobby links with the engine `jumList` order.
  - commit `7baf809` fixed the inn main-screen button-label mismatch.
  - Before `7baf809`, inn main-screen labels were one branch off, for example `概况` opened the order menu and `后院` opened the overview menu.
  - After `7baf809`, runtime assertion verified all 12 visible inn main buttons match their branch labels:
    - `厨房 -> 650`
    - `订单 -> 657`
    - `概况 -> 665`
    - `后院 -> 675`
    - `经营 -> 677`
    - `客房 -> 767`
    - `升级 -> 774`
    - `售卖 -> 1088`
    - `员工 -> 1090`
    - `外观 -> 1110`
    - `外出 -> 1112`
    - `分线 -> 1114`
- Latest main-screen local HTTP errors:
  - `[]`
- Latest request failures:
  - `[]`
- Recurring page warnings:
  - audio play interruption warnings, currently non-blocking.
- 2026-06-26 UI readability follow-up:
  - User screenshots showed branch-choice and custom UI text rendering as repeated unreadable/black bitmap glyphs.
  - Root cause: the sample package's bitmap-font path is not compatible with the old public H5 player in this runner; `StringUtil.getAnalysisText` was producing per-character bitmap sprites that all resolved to the same unusable glyph resource.
  - Added runner flag/default `patchReadableText=1`.
  - Superseded on 2026-06-27: the temporary `StringUtil.getAnalysisText` replacement made engine control codes visible and changed text styling. Do not reintroduce that wrapper.
  - Current `patchReadableText` is a manual fallback only: when explicitly enabled it disables the incompatible `fontBitmapData.isUserBitMap` path, but it does not set font family, font size, bold, stroke, or replace the engine parser.
  - Superseded on 2026-06-27: `patchReadableText` is no longer enabled by default because it changes the official bitmap-font path.
  - Verified order-branch readability:
    - `C:\tmp\claw_ui_fix_verify\order_readable_text.png`
    - `C:\tmp\claw_ui_fix_verify\order_readable_text_summary.json`
  - Regression pass:
    - `C:\tmp\claw_ui_fix_main_order\main_buttons_summary.json`
    - result: button `1` / order `status=ok`, `local404Count=0`, `missingMd5s=[]`

## Mirrored Resource Status

Known mirrored categories now include:

- main `game.bin`
- startup/title/font/UI assets
- title cover image
- first scene background/audio/UI assets
- create-character assets
- dynamic standing `OAF/OAF2` resources and frame images
- early menu/save/settings/mall/backpack/welfare assets
- create-character, name, birthday, ability, and newbie-chest assets
- opening story backgrounds, BGM, sound effects, CGs, character portraits, text panel assets
- tutorial/gameplay menu button assets
- inn main screen background and side-branch button assets

Recent resource commits:

- `c594fa6 Fix birthday confirm button display`
- `26b6864 Restore creation flow event chain`
- `bea9335 Mirror left chest reward resources`
- `f91220d Expand newbie chest click targets`
- `76bc080 Fix ability selection confirm button`
- `c9a2069 Stabilize newbie chest branch resources`
- `06a134d Mirror street scene resource`
- `58f8d7f Mirror opening portrait expression`
- `d311219 Mirror opening tutorial assets`
- `5f578db Mirror tutorial branch assets`
- `1241169 Mirror inn tutorial menu buttons`
- `d381672 Mirror inn main screen assets`

Current resource conclusion:

- The latest verified path to `storyId=15 pos=648` has no local `/shareres/<md5>` 404.
- Resource mirroring is an effective loop: collect unique md5 404s, resolve via `api/oapi_map.php`, mirror with `prepare_runner_mirror.py`, force-add only validated files, retest the same path.

## Known Non-Blocking Issues

### Platform API Boundaries

Observed platform/API boundaries include:

- account/login
- cloud archive
- PropShop/mall/account-money state
- reporting/telemetry
- investigate/light text endpoints
- malformed platform URLs in the old runtime such as `http://https//...`

Current interpretation:

- These are not blocking the validated local story/tutorial/main-screen flow.
- MVP should replace only the minimum required subset:
  - local user identity
  - single-game unlock state
  - local/cloud save replacement
  - basic resource/report logging

### Audio Warnings

Observed warnings:

- `The play() request was interrupted by a new load request`
- occasional browser autoplay-related messages

Current interpretation:

- These are currently non-blocking.
- They should be monitored but not prioritized ahead of gameplay path validation.

### `/null path`

Earlier builds emitted `/null%20path` requests.

Current status:

- A transparent-image fallback now normalizes known null image paths.
- It is no longer the main blocker in the latest validated flows.
- Revisit only if a future game path shows visible missing content tied to null-path behavior.

### Screenshot Capture

- Direct screenshot capture can be unreliable in animated scenes.
- Current validation works better with:
  - Playwright screenshots at known stable stops
  - console logs
  - story state snapshots
  - resource 404 collection
  - runtime button tables

## How To Reproduce Current Validation

From repo root:

```powershell
python -m http.server 8765 --bind 127.0.0.1
```

Open:

```text
http://127.0.0.1:8765/h5_runner_experiment.html?localRes=1&patchNewDSystem=1&traceRuntime=1&traceTitle=1&traceBranchChoice=1&traceNullPath=1&quietOafEvents=1&traceUiState=1&patchTitleClick=1&patchFirstSceneLobbyButtons=1&clearStorage=1&hideDebug=1&traceStoryState=1&traceAutoNameChoice=1&autoStartTitle=1&stubCode214Name=1&stubCode214Birthday=1&stubInitialVitals=1&stubPropShop=1&autoFirstSceneChoice=0&autoCreateCharacterConfirm=1&autoNameChoice=1&autoInnNameChoice=1&runId=latest
```

Expected path for manual checking:

1. Wait until the game reaches the newbie chest flow.
2. Click left chest.
3. Click the top-left return button on the reward screen.
4. Advance opening story until the `看 / 不看` choice.
5. Click:
   - top diamond around `(480,235)` for `看`
   - bottom diamond around `(480,315)` for `不看`
6. If `看`:
   - expect tutorial menu at `storyId=44 pos=324`
   - expect 11 visible tutorial/gameplay buttons
7. If `不看`:
   - expect inn main screen at `storyId=15 pos=648`
   - expect main inn background and visible buttons
8. Check console/logs for:
   - new real `/shareres/<md5>` 404
   - page crash
   - script errors
   - story state not changing after repeated clicks

## Next Debug Direction

### Priority 1: Re-test Inn Main Screen Buttons After `7baf809`

The immediate next step is a short manual plus automated regression pass for the inn main-screen buttons. Use the current playable URL:

```text
http://127.0.0.1:8899/h5_runner_experiment.html?localRes=1&patchNewDSystem=1&patchTitleClick=1&autoStartTitle=1&hideDebug=1&_cb=innmain7baf809
```

Expected inn main-screen visible buttons:

- `厨房`
- `订单`
- `概况`
- `后院`
- `经营`
- `客房`
- `升级`
- `售卖`
- `员工`
- `外观`
- `外出`
- `分线`

Do this next:

1. Reload the playable URL with a fresh `_cb` value.
2. Enter the inn main screen through `继续经营`.
3. Confirm the button labels show the expected 12-button list above.
4. Click each button once from a clean main-screen state and record:
   - button name/index
   - target link
   - resulting `storyId`
   - resulting `pos`
   - resulting `Code`
   - visible UI state
   - local `/shareres/<md5>` 404s
   - page errors
   - screenshot path
5. If a button opens content that still does not match its label, inspect the target branch label around `storyId=15` before changing links.
6. If new resource 404s appear:
   - resolve md5 in `api/oapi_map.php`
   - mirror with `prepare_runner_mirror.py`
   - force-add only the needed `shareres/<prefix>/<md5>` files
   - commit and push
   - rerun the same button path

Known harness issue:

- `scripts/validate-main-buttons.ps1 -RouteMode debug-jump` previously hung during the first button click stage.
- Before trusting the full validation report, fix or bypass that click wait by using a short per-button timeout and always writing a partial JSON report.

Acceptance for this priority:

- all 12 button labels match branch labels
- all 12 buttons visibly leave or intentionally update the main screen
- no new real local resource 404 remains unresolved
- no blocker console error is introduced

2026-06-26 follow-up result:

- Added page event/request failure capture and per-button `targetLink` output to `66rpgProjectDropper/validate_main_buttons.py`.
- Fixed `debugJumpMain` visual desync by closing the title view before the debug jump.
- Verified real-click main-button coverage with:
  - `C:\tmp\claw_verify_main_debug_jump_click_v3\main_buttons_summary.json`
- All 12 visible inn main buttons reported `status=ok`.
- Button/link mapping verified:
  - `厨房 -> 650`
  - `订单 -> 657`
  - `概况 -> 665`
  - `后院 -> 675`
  - `经营 -> 677`
  - `客房 -> 767`
  - `升级 -> 774`
  - `售卖 -> 1088`
  - `员工 -> 1090`
  - `外观 -> 1110`
  - `外出 -> 1112`
  - `分线 -> 1114`
- Latest main-button local 404s: `[]`
- Latest main-button missing MD5s: `[]`
- Cross-check: full-route real click for `订单` passed with no local 404:
  - `C:\tmp\claw_verify_main_full_click_order\main_buttons_summary.json`
- Known report noise remains non-blocking:
  - public platform request failures such as `Login.js` 403/CORS/report URL failures
  - occasional audio/play interruption page errors
  - screenshot timeouts on some animated branch transitions

### Priority 2: Resume Final Three-Strategy Merged Collection

After Priority 1 passes, resume the final merged story collection. Use the existing collector with the three policies already configured:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\collect-story-coverage.ps1 -Policies "round-robin,first,last" -Out C:\tmp\claw_story_coverage_final_after_innmain -DurationSeconds 120 -MaxSteps 120
```

Confirm in the merged report:

- `round-robin`, `first`, and `last` all produce usable summaries
- no unresolved `missingMd5s`
- the merged report includes inn main-screen branches after the `7baf809` label fix
- the final report clearly states whether all three strategies are ok

If the collector still skips button `8` from the previous wrong `好感` assumption, include it again in `MainButtons` after confirming `员工` is stable.

2026-06-26 follow-up result:

- `MainButtons` defaults were updated to include button `8`/`员工`:
  - `scripts/collect-story-coverage.ps1`
  - `66rpgProjectDropper/collect_story_coverage.py`
  - `66rpgProjectDropper/auto_play_story.py`
- Initial merged run found `round-robin` blocked at newbie chest state:
  - `storyId=1`, `pos=2101`, `Code=204`
  - no missing MD5s
  - cause: autoplay clicked while a cover/visual layer could still obscure the real button hit path
- `auto_play_story.py` now prefers `showEvent.finish(choice)` for `storyId=1,pos=2101`.
- Re-test `round-robin` alone passed:
  - `C:\tmp\claw_story_coverage_round_robin_after_chest_fix\story_coverage_summary.json`
  - status: `ok`
  - trace: `50`
  - unique states: `47`
  - missing MD5s: `[]`
- Final merged three-policy coverage passed:
  - `C:\tmp\claw_story_coverage_final_after_innmain_v3\story_coverage_summary.json`
  - `C:\tmp\claw_story_coverage_final_after_innmain_v3\story_coverage_report.md`
  - overall status: `ok`
  - `round-robin`: `duration_reached`, ok, trace `49`, unique states `43`, missing `0`
  - `first`: `duration_reached`, ok, trace `48`, unique states `46`, missing `0`
  - `last`: `duration_reached`, ok, trace `50`, unique states `46`, missing `0`
  - merged trace entries: `147`
  - merged unique story states: `68`
  - merged missing MD5s: `[]`

Current next priority:

- Priority 3: formalize/reduce ad hoc validation harness behavior.
- Priority 4: focused save/load validation from inn main screen.

### Historical Note: Pre-`7baf809` Inn Main Button Plan

Current highest-value next step is no longer title/first-scene probing. Start from `storyId=15 pos=648` and validate each visible main-screen entry:

- `订单`
- `概况`
- `后院`
- `经营`
- `酒宴`
- `升级`
- `售卖`
- `外出`
- `————好感————`
- `员工`
- `外观`

For each button:

1. start from a clean run or a saved main-screen state
2. click the exact runtime button coordinate
3. record:
   - target button name/index
   - resulting `storyId`
   - resulting `pos`
   - resulting `Code`
   - visible UI state
   - local resource 404s
   - page errors
   - screenshots
4. if new resource 404s appear:
   - resolve md5 in `api/oapi_map.php`
   - mirror with `prepare_runner_mirror.py`
   - force-add only the needed `shareres/<prefix>/<md5>` files
   - commit and push
   - rerun the same button path

### Priority 3: Formalize Auto Validation Scripts

The current scripts are useful but ad hoc. After the manual main-button pass, update the reusable validation harness:

- reusable browser launch
- stage-to-screen coordinate conversion
- story state extractor
- local 404 collector
- screenshot capture at named checkpoints
- route helpers:
  - clean start
  - reach newbie chest
  - reach opening story
  - reach tutorial menu
  - reach inn main screen
- JSON report output per route/button

Goal:

- each imported game should produce a comparable validation report.

### Priority 4: Save/Load Validation From Main Screen

Earlier auto-save persistence was proven through `localStorage` reads/writes, but manual save/load behavior still needs a focused validation pass.

Next validation:

1. reach inn main screen
2. trigger manual save UI
3. identify save slot write target
4. write a manual save
5. reload without `clearStorage=1`
6. verify restoration to the expected story/main-screen state
7. document storage keys and save format evidence

MVP reason:

- long-form games need reliable continue play.

2026-06-26 follow-up result:

- Focused main-screen save/load pass now succeeds with:
  - `C:\tmp\claw_save_load_main_v5\save_load_summary.json`
  - `C:\tmp\claw_save_load_main_v5\save_load_trace.jsonl`
  - `C:\tmp\claw_save_load_main_v5\saved_page.png`
  - `C:\tmp\claw_save_load_main_v5\restored_page.png`
- Validation starts from the inn main screen via debug jump:
  - saved state: `storyId=15`, `pos=648`, `Code=204`
  - advanced state after clicking main button `1` / order: `storyId=15`, `pos=657`, `Code=101`
  - restored state: `storyId=15`, `pos=648`, `Code=204`
  - continued state after restore: `storyId=15`, `pos=657`, `Code=101`
- `restoredMatchesSaved=true`; restore match confirms same story, near saved position, and rollback from the advanced state.
- No local resource 404s remained:
  - `local404=[]`
  - `missingMd5s=[]`
- The official runtime `gd.snap(slot)` path blocks on this route while collecting the full screen snapshot. The MVP-bounded replacement is now `runner-local-save-v1`, stored under:
  - `runnerLocalSave:0a235c54f16c431ab5736c92997edb47:v364:slot:0`
- `runner-local-save-v1` stores the minimal state needed for continue play:
  - guid/version/slot
  - story id/name
  - story position
  - current event code
  - current branch links
  - visible event-button count
- Restore uses the existing runtime story hooks (`jumpStoryCallBack` + `jumpToIndex`). For `Code=204` main-screen menu states it intentionally avoids calling `eventFinish()` after restore; calling it immediately re-enters the branch-selection conflict path around `storyId=15,pos=649`.
- New resources mirrored during this pass:
  - `13d21fe85e4a4854f9a98ca7bde57142`
  - `7eb2c1576726eb3e3babf58202a0dc70`
  - `cf07aec6e8b3502d6aa4924a5c2db753`
  - `db09cf0848632ba2671897f840a88525`

Current conclusion for Priority 4:

- Main-screen save/load is validated for MVP continue-play purposes.
- This is not a full clone of the official 66RPG archive format; it is a bounded local replacement around the minimum state required by the current runner.
- A future production save system should persist this payload through the site account/game library backend instead of raw browser-only `localStorage`.

### Priority 5: Platform Replacement Boundary

Identify the minimal host/platform APIs required for MVP:

- local user identity
- per-game unlock state
- save/load state
- resource reporting
- basic order confirmation

Do not attempt to fully clone 66RPG platform behavior. Stub or replace only what blocks local play.

### Priority 6: Multi-Game Import Feasibility

After this sample game's main hub is stable, test at least two additional games from different categories:

- one female-oriented/romance game
- one male-oriented or non-romance interactive story game

For each:

1. fetch package and map
2. parse with existing `patchNewDSystem`
3. measure whether the same parser patches work
4. mirror minimum startup resources
5. reach title/first scene
6. identify whether new binary/runtime schemas appear

Goal:

- determine whether the adapter is game-specific or reusable across a 20-game MVP library.

## Resource-Miss Loop

If a target triggers a new real `/shareres/<md5>` 404:

1. resolve MD5 to original asset path:

```powershell
$env:PYTHONIOENCODING='utf-8'
@'
import json
md5='<md5>'
d=json.load(open('api/oapi_map.php',encoding='utf-8'))
print([x for x in d['data'] if len(x)>2 and str(x[2]).lower()==md5])
'@ | python -
```

2. mirror that MD5 locally:

```powershell
$env:PYTHONIOENCODING='utf-8'
python 66rpgProjectDropper\prepare_runner_mirror.py 1569947 --version 364 --root . --mirror-md5 <md5>
```

3. force-add only the needed file:

```powershell
git add -f shareres\<prefix>\<md5>
```

4. commit/push each verification round.

5. rerun the same click path and confirm:

- local 404 is gone
- visible UI is fixed
- no new script/page error appeared

## MVP Implication For Our Site

Based on current technical validation, the practical MVP direction is:

- build a game library front end, not a full 66RPG clone
- import games through a repeatable grab/parse/mirror/validate pipeline
- keep the original H5 runtime where possible
- use runner-side patches and host API stubs only where needed
- sell each paid game as one-time unlock
- provide 3-5 free games for acquisition and trust
- maintain per-game validation reports before public listing
- add AI as an enhancement layer:
  - game summary
  - character summary
  - tags
  - 攻略/提示
  - recommendations

Current feasibility assessment:

- Static package acquisition: feasible.
- Local resource mirroring: feasible.
- Patched H5 runtime execution: feasible.
- Opening story and tutorial flow: feasible.
- Inn main hub entry: feasible.
- Main-screen button label/branch alignment: validated after `7baf809`.
- Main-screen real-click coverage: validated for all 12 inn main buttons.
- Three-strategy merged coverage after inn-main fix: validated with no missing MD5s.
- Save/load replacement: validated from the inn main screen with `runner-local-save-v1`; official `gd.snap` remains a platform/runtime boundary.
- Readable runtime text: default play keeps the official bitmap-font path; `patchReadableText=1` is only a manual fallback.
- Platform feature replacement: bounded and should be minimal.
- Multi-game scalability: not verified yet; next decisive MVP test after this sample stabilizes.

## 2026-06-27 Official Choice UI Follow-up

User supplied official UI references showing that branch choices should use wide translucent horizontal bars and thin text, not the previous bold/stroked fallback.

Changes:

- Added default runner flag `patchOfficialChoiceUi=1` for playable runs.
- Corrected `System.MessageBox.ChoiceButtonIndex` from the parsed bad value `20` (`商城_一键领取2.png`, 54x57 diamond) to official button index `19` (`选择框1/2.png`, 612x53 horizontal bar).
- Patched `textChoice.TextDifUI` so `showDifUI/update/updateEx/updateEx2` refresh the cached choice skin from the current event resources. The engine cached the old skin during `TextDifUI.init`, so changing `ChoiceButtonIndex` alone was insufficient.
- Superseded the temporary native text wrapper. `patchReadableText` no longer sets `bold`, `stroke`, font family, or font size.

Verification:

- Runtime choice UI: `C:\tmp\claw_choice_ui_verify_runtime2\summary.json`
  - order branch at `storyId=15,pos=657,code=101`
  - `choiceIndex=19`
  - three visible choice buttons at `x=174`, width `612`, height `53`
  - text glyphs report `bold=false`, `stroke=0`
- Canvas visual: `C:\tmp\claw_choice_ui_canvas\order_canvas.png`
- Save/load regression: `C:\tmp\claw_save_load_after_choice_ui_v2\save_load_summary.json`, status `ok`
- Main button regression for order/overview: `C:\tmp\claw_main_buttons_after_choice_ui_v2\main_buttons_summary.json`, status `ok`, no local 404

Note:

- The `debugJumpMain` path still skips some preceding visual setup, so its background/portrait can differ from the official full-route screenshots. Use it for branch/button mechanics; use full-route/manual play for final visual comparison.

## 2026-06-27 Default Play Link Compatibility

The runner now supports short playable URLs without carrying the long query string.

Default playable entries:

- `http://127.0.0.1:8765/h5_runner_experiment.html`
- `http://127.0.0.1:8765/h5_runner_experiment.html?runId=play`
- `http://127.0.0.1:8765/h5_runner_experiment.html?play=1`

Default play mode auto-enables the required runtime flags unless a flag is explicitly set in the URL:

- `localRes`
- `patchNewDSystem`
- `patchTitleClick`
- `patchFirstSceneLobbyButtons`
- `patchInnMainButtons`
- `autoStartTitle`
- `hideDebug`
- `quietOafEvents`
- `stubPropShop`
- `stubCode214Name`
- `stubCode214Birthday`
- `stubInitialVitals`
- `autoCreateCharacterConfirm`
- `autoNameChoice`
- `autoInnNameChoice`
- `patchOfficialChoiceUi`

Verification:

- Default URL smoke: `C:\tmp\claw_default_play_line_verify\summary.json`
  - plain `/h5_runner_experiment.html`: required flags true, `ChoiceButtonIndex=19`, entered `storyId=1,pos=7,code=204`
  - `/h5_runner_experiment.html?runId=play`: same result
  - explicit override check: `patchNewDSystem=0` remains false when specified
- Save/load regression after default mode change: `C:\tmp\claw_save_load_after_default_play\save_load_summary.json`, status `ok`

## 2026-06-27 Font Parser Restore

User screenshots showed two regressions from the temporary text fallback:

- Engine control tags such as `\c[0,0,0]` were rendered as visible dialogue text.
- Dialogue/choice text styling no longer matched the original runtime font path.

Fix:

- Removed the runner wrapper around `StringUtil.getAnalysisText`.
- Removed runner-side `OText` creation and all forced font styling (`font`, `fontSize`, `bold`, `stroke`, `sysFontSize`, `sysFontDifY`).
- Kept the bounded bitmap compatibility switch (`gd.fontBitmapData.isUserBitMap = false`) only behind explicit `patchReadableText=1`.
- Default playable URLs no longer enable `patchReadableText`, so normal play keeps the official bitmap-font path.

Verification:

- Parser hook restore: `C:\tmp\claw_font_restore_verify\summary.json`
  - `StringUtil.__runnerReadableTextWrapped` is false.
  - `fontBitmapData.isUserBitMap` is false.
- Full-route first story text smoke: `C:\tmp\claw_font_story_text_verify\summary.json`
  - no visible `\c[...]` text was found in runtime text nodes.
- Default short-link smoke after default font restore: `C:\tmp\claw_default_font_restore_smoke\summary.json`, status `ok`
  - `/h5_runner_experiment.html` still enables the default playable path without the long query string.
  - `choiceIndex=19`, `StringUtil.__runnerReadableTextWrapped=false`, `fontBitmapData.isUserBitMap=true`.
- Main save/load regression: `C:\tmp\claw_save_load_final_font_restore_v2\save_load_summary.json`, status `ok`
- Main order button regression: `C:\tmp\claw_main_buttons_final_font_restore\main_buttons_summary.json`, status `ok`
- Official choice UI regression: `C:\tmp\claw_choice_ui_after_font_restore\summary.json`
  - `choiceIndex=19`
  - three choice buttons at `x=174`, width `612`, height `53`
  - `StringUtil.__runnerReadableTextWrapped` is false.

## 2026-06-27 Default Font Restore

User reported that the main UI still felt visually wrong after the parser restore.

Finding:

- The remaining visual mismatch came from default `patchReadableText`: even without wrapping `StringUtil.getAnalysisText`, it still disabled `fontBitmapData.isUserBitMap`, so normal play used native/browser text instead of the official bitmap-font path.
- Runtime comparison showed the order menu remains readable with the official bitmap path:
  - `C:\tmp\claw_order_bitmap_original\summary.json`
  - `fontBitmapData.isUserBitMap=true`
  - `choiceIndex=19`
  - visible order choices are `每日订单 / 酒宴订单 / 返回`

Fix:

- Removed `patchReadableText` from default short-link and `autoStartTitle=1` playable defaults.
- Kept `patchReadableText=1` available as an explicit manual fallback only.

Verification:

- Default short-link smoke: `C:\tmp\claw_default_font_restore_smoke\summary.json`, status `ok`
  - `fontBitmapData.isUserBitMap=true`
  - `choiceIndex=19`
  - `StringUtil.__runnerReadableTextWrapped=false`
- Main order button regression: `C:\tmp\claw_main_button_after_default_font_restore\main_buttons_summary.json`, status `ok`
- Save/load regression: `C:\tmp\claw_save_load_after_default_font_restore\save_load_summary.json`, status `ok`
