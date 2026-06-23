# 66RPG Game Grab/Run Technical Debug Summary

更新时间：2026-06-23

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
- Latest main-screen local HTTP errors:
  - `[]`
- Latest request failures:
  - `[]`
- Recurring page warnings:
  - audio play interruption warnings, currently non-blocking.

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

### Priority 1: Validate Inn Main Screen Buttons

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

### Priority 2: Formalize Auto Validation Scripts

The current scripts are useful but ad hoc. Next step should create a reusable validation harness:

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

### Priority 3: Save/Load Validation From Main Screen

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

### Priority 4: Platform Replacement Boundary

Identify the minimal host/platform APIs required for MVP:

- local user identity
- per-game unlock state
- save/load state
- resource reporting
- basic order confirmation

Do not attempt to fully clone 66RPG platform behavior. Stub or replace only what blocks local play.

### Priority 5: Multi-Game Import Feasibility

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
- Main-screen button coverage: partially validated, next priority.
- Save/load replacement: partially validated, needs main-screen pass.
- Platform feature replacement: bounded and should be minimal.
- Multi-game scalability: not verified yet; next decisive MVP test after this sample stabilizes.
