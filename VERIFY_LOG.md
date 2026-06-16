# 66RPG Technical Verification Log

## Round 1: Resource Discovery And H5 Runner Probe

- Game: `1569947`
- GUID: `0a235c54f16c431ab5736c92997edb47`
- Version: `364`
- `Map.bin` parsed successfully with `11112` entries.
- First 50 mapped resources returned HTTP 200 from CDN.
- Main `data/game.bin` was downloadable and starts with `ORGDAT`.
- H5 runner could initialize the 66RPG player and request mapped resources, but failed in `readGameBin` with `getInt32 error - Out of bounds`.

## Round 2: Local Mirror And Parser Trace

- Added a local mirror preparation script: `66rpgProjectDropper/prepare_runner_mirror.py`.
- Added `h5_runner_experiment.html?localRes=1` to force mapped resources through local `http://127.0.0.1:8765/shareres/...`.
- Local mirror confirmed that `data/game.bin` is served locally with the expected size:
  - original `Map.bin` main bin: `47345898` bytes
  - H5 `Map_32.bin` main bin: `47345882` bytes
- The same `readGameBin` failure occurs when the resource is served locally, so the failure is not caused by CDN, CORS, or protocol differences.
- Added `traceReads=1` to instrument `GameByte` reads.
- Trace shows parsing reaches `pos=11622`, then reads a malformed string length and jumps to EOF:
  - error position: `pos=47345898` or `pos=47345882`
  - recent suspicious read: `readStringE` from `pos=11622` to EOF
- Added `fixEndian=1` to set `GameByte.endian = OByteArray.LITTLE_ENDIAN` in the main bin loader, but this did not resolve the mismatch.

Current technical conclusion: asset acquisition is feasible, but this player/runtime path is not yet enough for complete execution. The remaining blocker is parser compatibility or a missing runtime transform/initialization step before `readGameBin`.

## Round 3: Public Player Version Probe

- Added `66rpgProjectDropper/probe_player_assets.py` to extract official H5 player asset URLs across multiple game pages.
- Tested accessible H5 pages including `1077671`, `1091342`, `1187730`, `1331133`, `1478834`, `1526802`, `1562209`, `1569945`, `1569947`, `1678415`, and `1690428`.
- All tested official H5 pages referenced the same public player entry:
  - `https://c2.cgyouxi.com/website/hfplayer/v2/bin/main.min.js?v=20210202002`
- Added `66rpgProjectDropper/probe_cdn_player_candidates.py` to test common CDN candidates.
- CDN candidate results:
  - `hfplayer/v1/...` paths returned `404`
  - `hfplayer/v3/...` paths returned `404`
  - `hfplayer/v2/bin/main.js`, debug paths, and `bin/js/main*.js` returned `404`
  - `hfplayer/v2/bin/main.min.js` exists on `c1` through `c4`, all with the same MD5: `dea2b3b0e0e3afa96e4d326d6b349721`
- Query parameters on `main.min.js` are only cache busters:
  - no query, `?v=20210202002`, `?v=20190101`, `?v=20240101`, and `?v=random` all returned the same MD5.

Current technical conclusion: there is no alternate public H5 player version exposed through the tested official pages or common CDN paths. The remaining path is to investigate parser/runtime assumptions inside the current player, especially why `GameByte` parsing becomes offset by one byte around the first complex UI/string block.

## Round 4: DSystem Button Schema Trace

- Added `traceStructs=1` to `h5_runner_experiment.html` to wrap key `org_data` constructors and log parser enter/exit/error positions.
- Added `skipButtonPad=1` as a controlled experiment for `DButton` records that appear to have a single leading zero byte before the expected int/name layout.
- Added `66rpgProjectDropper/probe_bin_offsets.py` to inspect raw `game.bin` offsets around the first parser failure.
- Added `66rpgProjectDropper/probe_dsystem_buttons.py` to parse consecutive `DSystem` `DButton` records offline from the extracted `data/game.bin`.
- Structure trace narrowed the original failure path:
  - `DMain -> DHeader -> DSystem`
  - first `DButton` parsed from `pos=9950` to `pos=10070`
  - second `DButton` failed because its first field at `pos=10070` was shifted by one byte
- Raw offset inspection showed that starting the second `DButton` at `pos=10071` produces sane string and image filename fields.
- With `skipButtonPad=1`, the browser runner passed the original `pos=11622` EOF jump and advanced through many button records.
- The next browser failure became `DCustomUIData pos=16637 message=Invalid array length`, which means the current public player stopped reading buttons too early and entered the next structure at the wrong offset.
- Offline parsing from `pos=9950` with the same single-byte pad rule successfully parsed `453` consecutive button records:
  - last valid button: index `452`, start `48241`, end `48318`, name `卖百份`, images `卖百份1.png` / `卖百份2.png`
  - next bytes at `pos=48318` no longer look like a `DButton`
- The public player appears to read the `DSystem` button count as `80`, but the binary stream contains `453` button records.

Current technical conclusion: grabbing the game package and static assets is technically feasible, but directly reusing the public H5 player is blocked by a `DSystem` schema/version mismatch for this game. The next validation should derive or patch the correct `DSystem` layout, especially the field that decides the button count and any version-specific padding before `DButton` records.

## Round 5: DSystem Tail Layout Probe

- Added `66rpgProjectDropper/probe_dsystem_tail.py` to inspect the bytes immediately after the extended button table.
- Rechecked the start of the button table:
  - `pos=9946` is the public player's declared `Buttons` count: `80`
  - `pos=9950` is also `80`, but this is the first `DButton` marker
  - offline button scanning still parses through `453` button-shaped records, ending at `pos=48318`
- Probed the bytes after `pos=48318`:
  - `48318`: `ui_init_save=0`
  - `48322`: `1000`
  - `48326`: `3486`
  - `48330`: `0`
  - `48334`: `5`
- Interpretation: after the expanded button table, the binary appears to contain three extra `DSystem` tail fields before a `5` count-like value.
- Attempted to parse from `48338` using the public player's old `DCustomUIData` schema. It fails immediately:
  - `cui[0] failed at 48362: bad event argc 943009848 at 48358`
- Raw inspection after `48338` shows values and strings that look like event/debug payloads, for example `8058`, `8059`, and Chinese text such as `数值：[8059：支线开启/关闭] = 0`, but the field ordering does not match the old `DEvent` / `DCustomUIData` constructors exposed in `main.min.js`.

Current technical conclusion: the compatibility blocker is broader than the `Buttons` count. This game package uses a newer or different `DSystem` tail/UI/event schema than the public H5 player knows. A minimal runner patch must handle both the extended button table and the new tail/event layout; simply forcing `Buttons=453` is not enough.

## Round 6: New Custom UI Event Layout Probe

- Added `66rpgProjectDropper/probe_token_stream.py` to print loose int/string token streams from suspicious binary regions.
- Updated `66rpgProjectDropper/probe_dsystem_tail.py` with a `--no-after-events` variant for the candidate newer `DCustomUIData` layout.
- Reinterpreted the `DSystem` tail:
  - `48318`: `UIInitSave=0`
  - `48322`: extra field `1000`
  - `48326`: extra field `3486`
  - `48330`: first custom UI marker `0`
  - `48334`: first custom UI `loadEvent` count `5`
- Verified that `48338` begins valid event-list entries, not a `DCustomUIData` object:
  - event item marker `85`, code `200`, indent `0`, argc `6`
  - args include `8058`, `0`, `0`, `0`, `1`, and debug text `数值：[8059：支线开启/关闭] = 0`
- The newer custom UI layout appears to omit the old `afterEvent` list:
  - old public player layout: `marker -> loadEvents -> afterEvents -> controls -> show/mouse/key`
  - observed newer layout: `marker -> loadEvents -> controls -> show/mouse/key`
- With the `--no-after-events` parser:
  - CUI #0 parses from `48330` to `51816`: `load=5`, `controls=20`, `show=0`, `mouse=1`, `key=1`
  - CUI #1 parses from `51820` to `78996`: `load=31`, `controls=102`, `show=0`, `mouse=1`, `key=1`
  - each parsed CUI is followed by an extra 4-byte field before the next CUI marker
  - CUI #2 starts at `79000` and parses `load=19`, `controls=15`, but fails inside `control[12]` at `100330` with `bad control.event count 1508`
- Interpretation: the main new CUI schema difference is now identified, but at least one `DCustomUIItem` / control branch has additional fields or a type-specific layout that the old public player does not support.

Current technical conclusion: a minimal parser patch is becoming plausible, but it must handle three differences: extended button table, missing `afterEvent` list in newer CUI blocks, and at least one newer control-item branch. The next validation should focus on `control[12]` in CUI #2 and derive its type-specific field layout.

## Round 7: Chained Custom UI Table Probe

- Raised the event-list safety limit in `probe_dsystem_tail.py` from `1000` to `10000`.
- Added `--chain-extra` to parse consecutive newer CUI blocks by skipping the 4-byte size/extra field that appears between blocks.
- Corrected the Round 5/6 interpretation:
  - `48334` is not a CUI table count
  - it is the first CUI block's `loadEvent` count
  - the CUI table begins at `48330`
- Rechecked the previous CUI #2 `control[12]` failure:
  - `100322`: control marker/extra field
  - `100326`: event count `1508`
  - `100330`: first event record
  - parsing `1508` event records succeeds through `238230`
- With the higher event limit, CUI #2 parses completely:
  - `start=79000`, `end=238459`
  - `load=19`, `controls=15`, `show=0`, `mouse=1`, `key=1`
  - first control image: `兑换码.png`
- Chained CUI parsing then succeeds through many blocks:
  - CUI #0: `48330 -> 51816`, `load=5`, `controls=20`
  - CUI #1: `51820 -> 78996`, `load=31`, `controls=102`
  - CUI #2: `79000 -> 238459`, `load=19`, `controls=15`
  - CUI #3: `238463 -> 288965`, `load=928`, `controls=34`
  - CUI #4: `288969 -> 291800`, `load=14`, `controls=8`
  - CUI #5 and onward continue with the same `extra -> marker -> loadEvents -> controls -> show/mouse/key` layout
- A 1000-block chain probe did not hit a parser error. Late entries become empty placeholder-like CUI blocks with:
  - `extra=24`
  - `marker=0`
  - `load=0`
  - `controls=0`
  - `show=0`, `mouse=1`, `key=1`

Current technical conclusion: the previous suspected `DCustomUIItem` branch mismatch was a false alarm caused by an overly low event-count guard. The newer CUI table is now parsable as a chained sequence with inter-block 4-byte extras and no `afterEvent` list. The remaining unknown is how the real CUI table terminates or how its count is encoded before the parser reaches later `DMain` sections.

## Round 8: Counted Custom UI Table Validation

- Added `66rpgProjectDropper/probe_cui_chain_summary.py` to summarize chained newer CUI blocks and detect empty placeholder runs.
- Updated `66rpgProjectDropper/probe_dsystem_tail.py` with `--counted-new-cui`.
- Corrected the `DSystem` tail layout again:
  - `48318`: `UIInitSave=0`
  - `48322`: newer CUI table count: `1000`
  - `48326`: CUI #0 declared byte size: `3486`
  - `48330`: CUI #0 marker/start
- The newer CUI table layout is now:
  - `UIInitSave`
  - `CuiCount`
  - repeated `CuiCount` times: `DeclaredSize -> marker -> loadEvents -> controls -> show/mouse/key`
  - then the next `DSystem` field, likely `MenuIndex`
- Verified all `1000` CUI blocks with declared-size checking:
  - no `size_mismatch`
  - final parsed CUI: `cui[999] start=24414620 end=24414644 declared_size=24 actual_size=24`
  - final table end: `pos=24414644`
- `probe_cui_chain_summary.py` showed sparse placeholders:
  - first empty placeholder appears at `cui[60]`
  - later real CUI entries continue after that
  - last non-empty CUI in the 1000-entry table is `cui[933]`
  - common placeholder shape: `declared_size=24`, `marker=0`, `load=0`, `controls=0`, `show=0`, `mouse=1`, `key=1`
- The field at `24414644` is `0`, consistent with the old public player reading `MenuIndex` immediately after `Cuis`.

Current technical conclusion: the newer `DSystem` tail is now structurally closed. The parser mismatch can be described as: public player expects `UIInitSave -> CuisCount -> old CUI blocks -> MenuIndex`, while this package uses `UIInitSave -> CuisCount=1000 -> size-prefixed new CUI blocks without afterEvents -> MenuIndex`. This is enough to attempt a targeted runner parser patch for `DSystem`/`DCustomUIData`.

## Round 9: Runner DSystem Parser Patch

- Added `patchNewDSystem=1` to `h5_runner_experiment.html`.
- The patch keeps the old player intact unless the query flag is enabled.
- Patch behavior:
  - enables the existing one-byte `DButton` pad workaround automatically
  - replaces `org_data.DSystem` with an experiment parser for this newer package layout
  - parses the expanded button table as `453` buttons when the old count field is `80`
  - parses newer CUI blocks as `DeclaredSize -> marker -> loadEvents -> controls -> show/mouse/key`
  - validates each CUI block's declared byte size against the actual bytes consumed
- Browser validation URL:
  - `http://127.0.0.1:8765/h5_runner_experiment.html?localRes=1&patchNewDSystem=1&traceStructs=1`
- Validation result:
  - `new DSystem buttons oldCount=80 parsed=453 pos=48318`
  - `new DSystem Cuis parsed=1000 menuIndex=0 pos=24414648`
  - `STRUCT exit DMain pos=47345898`
- This confirms the runner can now parse the entire main `data/game.bin` through `DMain`.
- The next failure moved to local resource coverage:
  - missing `data/mallnew.bin`, md5 `e348f5a2ff82e8751adc97af6eb84c64`
  - missing image/resource md5s including `50fa5798f1b3781f07be6d05f33d0abc`, `a8960086d87d7d441a29d281a0cde38c`, and `f6315584df310dbd0ccf1130e544bb1b`
  - these fail because the current local mirror only contains `data/game.bin`
- The later `getInt32 error - Out of bounds` occurs after a 404 response is loaded as binary data, not while parsing the main game bin.

Current technical conclusion: the main structural blocker is cleared in the experimental runner. The remaining validation path is asset/bin dependency mirroring: mirror secondary bin files such as `data/mallnew.bin` and required image/audio resources, then rerun the patched runner to see how far the actual game initialization proceeds.

## Round 10: Runner Startup Dependency Mirroring

- Extended `66rpgProjectDropper/prepare_runner_mirror.py` so the local mirror can pull multiple resources in one run:
  - repeated `--mirror-name`
  - repeated `--mirror-md5`
  - repeated `--mirror-log`, which scans runner logs for `/shareres/xx/<md5>` URLs and mirrors those mapped resources
  - existing local files are reused instead of downloaded again
- Mirrored the first startup dependency set for the patched local runner:
  - `data/game.bin`, md5 `7b633df854b9742c1a653e134ee6f2d8`
  - `data/mallnew.bin`, md5 `e348f5a2ff82e8751adc97af6eb84c64`
  - `graphics/background/封面-美人客栈.jpg`, md5 `50fa5798f1b3781f07be6d05f33d0abc`
  - `graphics/button/ui导入/返回前.png`, md5 `a8960086d87d7d441a29d281a0cde38c`
  - `graphics/button/ui导入/返回后.png`, md5 `f6315584df310dbd0ccf1130e544bb1b`
- Used the new `--mirror-log` flow to mirror the next missing font resources detected by the browser runner:
  - `font/font.list`, md5 `0aac1d3ba7b759f32030df054e8715c2`
  - `font/方正宋刻本秀楷简体$26.xfi`, md5 `e9bbc1dec4b99341c0f11c6333ab43c9`
- Browser validation URL:
  - `http://127.0.0.1:8765/h5_runner_experiment.html?localRes=1&patchNewDSystem=1`
- Validation result:
  - main `data/game.bin` loads locally with HTTP 200
  - `data/mallnew.bin` loads locally with HTTP 200
  - `font/font.list` loads locally with HTTP 200
  - `font/方正宋刻本秀楷简体$26.xfi` loads locally with HTTP 200
  - no remaining 404 was observed in the startup `/shareres` requests for this run
- The current failure moved again:
  - browser reports `ERROR: Script error. @ :0`
  - the Laya canvas is created at `1280x720`, but the visible game area remains black
  - the player's `.error-bg` overlay stays hidden, so this is not the previous visible resource-load error state

Current technical conclusion: dependency mirroring is technically workable and can be driven from observed runner logs. The patched runner now reaches past main-bin parsing and the first secondary bin/font loads. The next blocker is an opaque runtime script error after startup resources load, so the next validation should instrument runtime errors more deeply and identify whether the failure is caused by an external API call, a missing non-`shareres` asset, or another player compatibility issue.

## Round 11: Runtime Error And Stage State Trace

- Added richer runner diagnostics to `h5_runner_experiment.html`:
  - `crossorigin="anonymous"` on static player scripts
  - fuller `window.error` and `unhandledrejection` logging
  - `traceRuntime=1` to log dynamic script URLs, wrap async callbacks, and poll Laya stage state
  - recursive stage child summaries for the first visible scene nodes
- Browser validation URL:
  - `http://127.0.0.1:8765/h5_runner_experiment.html?localRes=1&patchNewDSystem=1&traceRuntime=1`
- Validation result:
  - `Main`, `Laya`, and `GloableData` are all available before initialization
  - `window.gameMain` is created successfully
  - `gameInfo` is populated:
    - `gName`: `【区半挂件】美人客栈`
    - `gIndex`: `127`
    - package runtime `ver`: `108`
    - dimensions: `960x540`
  - local mirrored startup resources load successfully:
    - main `game.bin`: HTTP 200
    - `mallnew.bin`: HTTP 200
    - `font/font.list`: HTTP 200
    - `font/方正宋刻本秀楷简体$26.xfi`: HTTP 200
- The remaining observed external/platform failures are now separated from local asset mirroring:
  - dynamic JSONP script `https://www.66rpg.com/ajax/index/get_home_gray?...` fails as a resource error, and direct local probing returns HTTP 403
  - reporting/investigation URLs are malformed in this local runner context, for example `http:https://report.66rpg.com/...` and `http:https://c.66rpg.com/...`
  - an opaque `Script error. @ :0:0` still fires after the font resources load
- Laya stage state:
  - stage initially has two children, including `adView`
  - after the script error, stage has one root container
  - that container contains a nested loading/progress display: a `960x540` graphics node plus progress-bar-like graphics nodes near `y=446..482`
  - no game scene or title/menu view is mounted after five runtime polls

Current technical conclusion: the runner now reaches the platform/player startup layer, not merely binary parsing. The next likely blocker is the official player startup flow around platform APIs, ads, and loading completion, rather than missing initial `shareres` files. The next validation should stub or bypass nonessential platform endpoints/ad flow (`get_home_gray`, report/investigate calls, possibly `adView`) and trace which player method should advance from the loading view into the game scene.

## Round 12: Bitmap Font Atlas And Title Entry

- Inspected the official `main.min.js` startup path and identified the loading transition:
  - `Main.onLoaded()` creates `org_data.DBitmapFontData`
  - `DBitmapFontData.startLoad()` loads `font/font.list`, `.xfi`, and, on the browser path, bitmap font PNG atlases
  - `Main.loadFontComplete()` then calls `Main.startGame()`
  - `Main.startGame()` dispatches or triggers the transition into `Main.enterGame()`
- Added method-level `traceRuntime=1` diagnostics for:
  - `Main.loadInitBinComplete`, `getInvestigateUrl`, `onLoaded`, `loadFontComplete`, `startGame`, `enterGame`, and `checkAuto`
  - `LoadingLayer` / `LoadingBar`
  - `DBitmapFontData.startLoad`, `pathCallback`, `path_2_Callback`, `readFontConfig`, and `getTextLineHeight`
  - `EventCenter.dispatchEvent`
- First validation with the new trace found the concrete blocking error:
  - `DBitmapFontData.readFontConfig` threw `Cannot read properties of undefined (reading 'width')`
  - this happened because the `.xfi` file loaded, but the bitmap font PNG atlas textures were not mirrored locally
- Mirrored the missing font atlas resources:
  - `font/方正宋刻本秀楷简体$26$1.png`, md5 `ef233e8618723ae2e98b022afed06c3c`
  - `font/方正宋刻本秀楷简体$26$2.png`, md5 `fc90f00f224973fe653c5e23b352cd7a`
  - `font/方正宋刻本秀楷简体$26$3.png`, md5 `8db19f3d9c81fd998291f46b10553413`
- Browser validation after mirroring:
  - `DBitmapFontData.readFontConfig` returned successfully
  - `Main.loadFontComplete` was called
  - `Main.startGame` was called
  - `Main.enterGame` was called
  - `LoadingLayer.dispose` and `LoadingBar.dispose` were called
  - `LOAD_UI_RESOURCE_COMPLETE` fired with `TITLEUI_TYPE`
  - stage changed from the loading/ad layer to a `960x540` root with `13` children, consistent with the title UI being mounted
  - `Graphics/Background/封面-美人客栈.jpg` loaded after title entry
- Remaining non-blocking platform/resource issues observed:
  - `get_home_gray` JSONP still returns a resource error / 403 in local context
  - mall/flower APIs are malformed under the local runner, for example `http://https//www.66rpg.com/PropShop/...`
  - these happen after title entry and do not block reaching `Main.enterGame()`

Current technical conclusion: the technical feasibility bar moved significantly: with the patched parser and mirrored startup/font resources, the official H5 player can enter the game/title layer locally. The next validation should focus on title-screen usability and first interaction: whether the title buttons respond, which additional title/story assets are requested, and which platform APIs must be stubbed to avoid later mall/flower/free-time failures.

## Round 13: Clean Title View And First Click Probe

- Added `hideDebug=1` to `h5_runner_experiment.html` so the runtime trace can stay enabled while the visual canvas is not covered by the debug overlay.
- Browser validation URL:
  - `http://127.0.0.1:8765/h5_runner_experiment.html?localRes=1&patchNewDSystem=1&traceRuntime=1&hideDebug=1`
- Clean title rendering result:
  - the canvas shows the full title cover for `美人客栈`
  - visible prompt: `点击封面任意处进入作品`
  - debug overlay is hidden, but the same trace text remains available through the hidden `#debug` node
- First click attempt exposed three additional missing local resources:
  - `graphics/ui/logo.png`, md5 `d827b63f1cf4a4b483530ee12e3bb093`
  - `graphics/ui/ui导入/底图/姓名框.png`, md5 `41354891b5342e611d0771ddbf98b903`
  - `graphics/ui/ui导入/底图/对话框2.png`, md5 `1a179f92a756fa0b3c7f4dca4ce9caba`
- Mirrored those resources with `prepare_runner_mirror.py` and reran the clean title page.
- After mirroring:
  - `姓名框.png` and `对话框2.png` load with `LOAD_IMAGE_COMPLETE`
  - `Main.loadFontComplete`, `Main.startGame`, and `Main.enterGame` still complete
  - `LOAD_UI_RESOURCE_COMPLETE` still fires with `TITLEUI_TYPE`
  - title cover remains visually complete
- Interaction probe:
  - coordinate click at the cover center did not advance into story
  - Playwright canvas click did not advance into story
  - coordinate click near the bottom prompt did not advance into story
  - the runtime logs `LONG_DOWN_CANCEL_BY_MOVINE_EVENT` after these automated clicks

Current technical conclusion: startup, title rendering, and the first title/story UI resource loads are now technically reproducible from the local mirror. The next blocker is input handling rather than binary parsing or missing startup assets: the local automated clicks are being interpreted by the H5 player as a long-down/move-cancel event, so the next validation should compare a real manual click against the automated click path, then patch or shim the player input event path if manual click succeeds.

## Round 14: Title Button Path And Auto Start Probe

- Downloaded the public H5 player script temporarily for static inspection:
  - `https://c2.cgyouxi.com/website/hfplayer/v2/bin/main.min.js?v=20210202002`
- Static inspection result:
  - the title screen is implemented by `view.TitleUI` and `view.TitleUIMediator`
  - `TitleUI.initButton()` creates `ORGButton` instances only for non-empty title button images
  - `TitleUIMediator.clickButton()` starts the story when the event index is `GloableStaticData.TITLE_BUTTON_TYPE_1`
  - therefore the visible prompt is not a generic full-cover click target; the start path is a title-button event path
- Added two runner-only validation flags:
  - `traceTitle=1` logs parsed title button configuration after title UI resources load
  - `autoStartTitle=1` bypasses pointer input and calls the same start-story path used by the first title button
- Browser validation URL:
  - `http://127.0.0.1:8765/h5_runner_experiment.html?localRes=1&patchNewDSystem=1&traceRuntime=1&traceTitle=1&autoStartTitle=1&hideDebug=1`
- `traceTitle=1` result:
  - `skipTitle=false`
  - `startStoryId=1`
  - `titleImage="封面-美人客栈.jpg"`
  - `buttonCount=6`
  - only title button 1 has non-empty images:
    - button index `10`
    - position `x=0,y=0`
    - images `ui导入\\返回前.png` and `ui导入\\返回后.png`
  - buttons 2-6 have empty images and are not created as clickable `ORGButton` instances
- `autoStartTitle=1` result:
  - emitted `AUTO TITLE START storyId=1`
  - the runtime entered the first story path and requested first-scene resources
  - first missing story asset was md5 `4d575c7975042bff3d52cd7c38613c7a`, mapped to `graphics/oafs/红花瓣飘动_540.oaf2`
- Mirrored the missing OAF container, then used `prepare_runner_mirror.py --mirror-log .http-server.err.log` to bulk mirror the OAF frame PNGs and adjacent first-scene UI/button/background/audio resources observed in local 404 logs, including:
  - `graphics/background/传送门.jpg`
  - `audio/bgm/对月-染霜华-季一昂.mp3`
  - `graphics/oafs/红花瓣飘动_540/0.png` through `59.png`
  - several first-scene UI/button resources loaded after the story path started

Current technical conclusion: title-to-story transition is technically viable when the title start event is triggered directly. The remaining user-interaction problem is not the story engine; it is title input targeting/event dispatch. The next validation should implement a narrow `patchTitleClick=1` shim that converts a click/tap on the visible title cover into `CLICK_TITLE_VIEW_BUTTON` with `TITLE_BUTTON_TYPE_1`, then verify that the page can enter story through normal user input instead of `autoStartTitle`.

## Round 15: Patched Cover Click Enters First Scene

- Added `clearStorage=1` to clear `localStorage` and `sessionStorage` before runner initialization. This prevents previous local autosave/session state from sending the validation directly into a black story layer before title UI appears.
- Added `patchTitleClick=1`:
  - installed native capture listeners for `click`, `pointerup`, `mouseup`, and `touchend` after title UI resources complete
  - on the first cover click, calls the same local start-story helper as `autoStartTitle`
  - default behavior is unchanged unless the flag is present
- Browser validation URL:
  - `http://127.0.0.1:8765/h5_runner_experiment.html?localRes=1&patchNewDSystem=1&traceRuntime=1&traceTitle=1&patchTitleClick=1&clearStorage=1&hideDebug=1`
- Pre-click validation:
  - `browser storage cleared`
  - `TITLE STATE after-title-ui-resource`
  - `patchTitleClick native listeners installed`
  - title data still reports `startStoryId=1`
- Click validation:
  - automated cover click emitted `PATCH TITLE CLICK START storyId=1`
  - story resources loaded after the click, including `Graphics/Background/传送门.jpg`
  - OAF frame resources for `Graphics/oafs/红花瓣飘动_540` loaded
  - screenshot `round15_after_patch_click.png` shows the first interactive game scene with character art, background, menu/light-text controls, and story/management UI
- The underlying runtime still logs `LONG_DOWN_CANCEL_BY_MOVINE_EVENT` around automated pointer input, but it no longer blocks the patched cover-click path.

Current technical conclusion: with the patched parser, mirrored resources, and a small title-click shim, this 66RPG game can be loaded locally from mirrored assets, display its title, accept a cover click, and enter the first playable scene. The next validation should move from bootstrapping to gameplay continuity: click the first scene controls, observe the next resource wave, and use `--mirror-log` iteratively until a short 3-5 minute play path runs without local 404s.

## Round 16: First Scene Continuation Resource Wave

- Reused the local patched runner URL:
  - `http://127.0.0.1:8765/h5_runner_experiment.html?localRes=1&patchNewDSystem=1&traceRuntime=1&traceTitle=1&patchTitleClick=1&clearStorage=1&hideDebug=1`
- First pass:
  - entered the title successfully
  - clicked the cover and reached the first interactive scene
  - clicked the visible `continue management` control in the first scene
  - this exposed a new local missing resource:
    - md5 `087ab1d0f97373d1ec5cf7bcdbb99767`, mapped to `graphics/oafs/dynamic-standing-1.oaf2`
- Ran:
  - `python 66rpgProjectDropper\prepare_runner_mirror.py 1569947 --version 364 --root . --mirror-md5 087ab1d0f97373d1ec5cf7bcdbb99767 --mirror-log .http-server.err.log`
  - then reran `--mirror-log .http-server.err.log` after the next click-generated 404 wave
- The mirror-log pass pulled the next gameplay resource wave, including:
  - `graphics/oafs/dynamic-standing-1.oaf2`
  - `graphics/oafs/dynamic-standing-1/10000.png` through `10025.png`
  - `graphics/half/create-character/1.jpg`
  - `graphics/half/create-character/initial-character-select.png`
  - `graphics/half/create-character/initial-character-select-bg.jpg`
  - `graphics/button/festival-extra-1.png`
  - `graphics/button/festival-extra-2.png`
  - `graphics/button/currency-plus-1.png`
  - `graphics/button/currency-plus-2.png`
- Final rerun after mirroring:
  - title and patched cover click still work
  - first scene loads without new startup/title regression
  - clicking the first-scene continuation control now loads the dynamic-standing frame sequence successfully
  - browser console emits repeated `LOAD_IMAGE_COMPLETE` for `Graphics/oafs/dynamic-standing-1/10000.png` through later frames
  - local server log confirms previously missing `shareres` hashes return `200` or `304` after mirroring
- Remaining observed issue:
  - the runtime still requests `/null%20path` twice after this step; this is not a `shareres` asset miss and appears to be an empty path emitted by the runtime/story data
  - external 66RPG platform JSONP/API errors still exist but are not blocking this specific first-scene continuation resource load
- Browser screenshot capture timed out during the animated post-click state, so this round uses console events plus local HTTP status transitions as the primary evidence.

Current technical conclusion: gameplay continuity is now verified one step beyond the first scene. The local runner can enter the game, click the first scene control, discover the next resource wave, mirror it from the game map, and successfully reload those assets locally. The next validation should identify the source of `/null path`, then continue the same loop on the next visible interaction until platform APIs or story logic, not static asset fetching, becomes the main blocker.

## Round 17: Null Path Trace And Move Sound Resource

- Added a runner-only diagnostic flag:
  - `traceNullPath=1`
- The new trace hooks inspect:
  - `XMLHttpRequest.open`
  - `fetch`
  - `HTMLImageElement.src`
  - `HTMLMediaElement.src`
  - `HTMLSourceElement.src`
  - `ORG.loader.load`
  - `Laya.loader.load`
  - `Laya.loader.create`
  - nested loader payload fields such as `url`, `path`, `src`, `source`, and `name`
- Validation URL:
  - `http://127.0.0.1:8765/h5_runner_experiment.html?localRes=1&patchNewDSystem=1&traceRuntime=1&traceTitle=1&traceNullPath=1&patchTitleClick=1&clearStorage=1&hideDebug=1`
- Observed result:
  - `traceNullPath=1` starts correctly and logs `null path trace enabled`
  - the local server still sees two `GET /null%20path` requests during the first-scene/OAF loading window
  - none of the hooked JS entry points reports a `NULL PATH ...` stack
  - this means the request is likely produced below those public JS APIs, by an internal Laya resource path normalization path, cached resource retry, or another browser/runtime path not exposed through the wrapped methods
  - it does not block title entry, patched cover click, first-scene loading, or dynamic-standing OAF frame loading
- The same run exposed a real next missing resource:
  - md5 `0839375b26561183ca0bd747ed0dccc3`
  - mapped by the game resource map to `audio/se/move_1.mp3`
  - size `32641`
- Mirroring command:
  - `python 66rpgProjectDropper\prepare_runner_mirror.py 1569947 --version 364 --root . --mirror-md5 0839375b26561183ca0bd747ed0dccc3 --mirror-log .http-server.err.log`
- Local verification:
  - `shareres/08/0839375b26561183ca0bd747ed0dccc3` exists locally
  - direct HTTP request to `http://127.0.0.1:8765/shareres/08/0839375b26561183ca0bd747ed0dccc3` returns `200` with length `32641`

Current technical conclusion: `/null path` is a low-priority noisy request in the current path because it is not stopping gameplay progression and is not a normal mapped asset miss. The next practical step is to continue the gameplay loop after `move_1.mp3` is mirrored, then collect and mirror the next real `/shareres/<md5>` 404. If `/null path` later becomes blocking, use a deeper Laya `Loader`/`URL.formatURL` monkey patch rather than treating it as a missing file.

## Round 18: Continue After Move Sound Mirror

- Reused the patched runner with:
  - `localRes=1`
  - `patchNewDSystem=1`
  - `traceRuntime=1`
  - `traceTitle=1`
  - `traceNullPath=1`
  - `patchTitleClick=1`
  - `clearStorage=1`
  - `hideDebug=1`
- Validation path:
  - loaded title
  - clicked the title cover through the patched title-click path
  - reached the first story scene with `Graphics/Background/传送门.jpg`
  - advanced the dialogue/scene with several lower-screen and management-area clicks
- Result after `audio/se/move_1.mp3` was mirrored in Round 17:
  - no new `/shareres/<md5>` `404` was observed in the local HTTP log
  - the only 404s remained the two known `/null%20path` requests
  - after additional clicks, the debug log shows `Graphics/oafs/动态立绘1/...` frame loading repeatedly
  - the debug log also confirms `创建人物` resources appeared earlier in the run
  - local HTTP log confirms the previously mirrored create-character and dynamic-standing resources now return `304`
- Additional interaction probe:
  - several likely create-character / lower-screen click coordinates were tested
  - these did not expose another UI resource wave or new real asset miss
  - no new `RESOURCE ERROR` or `NULL PATH` entries appeared after those extra clicks
- Browser screenshot capture still times out during the animated scene, so this round again uses debug text plus HTTP status logs as primary evidence.

Current technical conclusion: the resource mirror is now stable through the first scene, first dialogue advancement, create-character resource load, and dynamic-standing OAF animation. The next useful validation should reduce noisy animation trace output or add a targeted event/UI-state trace, because raw `LOAD_IMAGE_COMPLETE` logs from looping OAF frames make it hard to identify the next actionable UI state.

## Round 19: Quiet OAF Logs And UI Target Trace

- Added two runner-only diagnostic flags:
  - `quietOafEvents=1`
  - `traceUiState=1`
- `quietOafEvents=1` suppresses repetitive `LOAD_IMAGE_COMPLETE` events for OAF frame paths such as:
  - `Graphics/oafs/.../14.png`
  - `Graphics/oafs/...\\14.png`
- `traceUiState=1` periodically logs:
  - `UI STATE`: visible Laya stage nodes with local and global coordinates (`x/y`, `gx/gy`)
  - `UI TARGETS`: likely clickable targets with center coordinates (`cx/cy`) and bounds
- Validation URL:
  - `http://127.0.0.1:8765/h5_runner_experiment.html?localRes=1&patchNewDSystem=1&traceRuntime=1&traceTitle=1&traceNullPath=1&quietOafEvents=1&traceUiState=1&patchTitleClick=1&clearStorage=1&hideDebug=1`
- Browser validation result:
  - title entry still works
  - patched title click still emits `PATCH TITLE CLICK START`
  - the first scene UI can be inspected without OAF frame log flooding
  - debug text summary after entering first scene:
    - `Graphics/oafs` log count: `0`
    - `UI STATE` count: `7`
    - `UI TARGETS` count: `7`
    - `PATCH TITLE CLICK START` count: `1`
    - `NULL PATH` count: `2`
- Example `UI TARGETS` captured in the first scene:
  - `stage.0.3.0.0`, center `(536,413)`, size `132x50`
  - `stage.0.3.0.1`, center `(632,417)`, size `54x58`
  - `stage.0.3.0.2`, center `(775,429)`, size `69x82`
  - `stage.0.7.0`, center `(921,54)`, size `42x52`
  - `stage.0.7.1`, center `(921,124)`, size `42x52`
- Local HTTP log:
  - no new real `/shareres/<md5>` `404`
  - only the known two `/null%20path` requests remain

Current technical conclusion: the next validation can use `UI TARGETS` instead of guessed coordinates. This gives a cleaner path for automated gameplay probing: click each stable target center, wait briefly, then check for new `LOAD_UI_RESOURCE_COMPLETE`, real `/shareres` 404s, or a changed `UI TARGETS` set.

## Round 20: Effective Visible UI Target Filtering

- Problem found while starting the next click probe:
  - `traceUiState=1` listed hidden title/loading children as `UI TARGETS`.
  - The previous collector checked each node's own `visible` and `alpha`, but did not inherit parent visibility.
- Runner diagnostic patch:
  - `collectUiState()` now propagates `parentVisible`.
  - `UI STATE` entries include `effectiveVisible`.
  - `UI TARGETS` are emitted only for effectively visible nodes with centers inside the 960x540 stage bounds.
- Validation URL:
  - `http://127.0.0.1:8765/h5_runner_experiment.html?localRes=1&patchNewDSystem=1&traceRuntime=1&traceTitle=1&traceNullPath=1&quietOafEvents=1&traceUiState=1&patchTitleClick=1&clearStorage=1&hideDebug=1`
- Browser validation result after title click:
  - `PATCH TITLE CLICK START`: `1`
  - `UI TARGETS` no longer includes the hidden top title targets at `(152,9)`.
  - `UI TARGETS` no longer includes the hidden loading text target `加载中...100%`.
  - Clean first-scene targets:
    - `stage.0.3.0.0`, center `(536,413)`, size `132x50`
    - `stage.0.3.0.1`, center `(632,417)`, size `54x58`
    - `stage.0.3.0.2`, center `(775,429)`, size `69x82`
    - `stage.0.3.0.3`, center `(678,128)`, size `45x55`
    - `stage.0.3.0.4`, center `(582,129)`, size `54x58`
    - `stage.0.7.0`, center `(921,54)`, size `42x52`
    - `stage.0.7.1`, center `(921,124)`, size `42x52`
- Single click probe:
  - clicked `(536,413)`
  - target set did not change after 4 seconds
  - `LOAD_UI_RESOURCE_COMPLETE` stayed at `1`
  - `NULL PATH` stayed at `2`
- Local HTTP log:
  - many mirrored first-scene resources returned `304`
  - no real `/shareres/<md5>` `404`
  - only the known two `/null%20path` requests remain

Current technical conclusion: `UI TARGETS` is now reliable enough for automated isolated click probing. The next useful validation should reload to the same first-scene state for each target, click one target at a time, and classify each target by resulting target-set changes, resource requests, and event counts.

## Round 21: Isolated First-Scene Target Classification

- Reused the Round 20 validation URL and forced a `960x540` browser viewport so `UI TARGETS` coordinates map directly to click coordinates.
- For each run:
  - reloaded with `clearStorage=1`
  - waited for `patchTitleClick native listeners installed`
  - clicked title cover `(480,270)`
  - waited for the stable first-scene `UI TARGETS`
  - clicked one target center
  - waited 5-7 seconds
  - compared page debug text and local HTTP status logs

| Target path | Coordinate | Classification | Result |
| --- | --- | --- | --- |
| `stage.0.3.0.0` | `(536,413)` | dialogue/branch advance | Triggered `CLICK_TEXT_CHOICE_BUTTON`, loaded create-character images, then target set reduced to the two right-side buttons. This was state-sensitive and no longer a no-op in the isolated run. |
| `stage.0.3.0.1` | `(632,417)` | save/menu UI | Triggered `CLICK_TEXT_CHOICE_BUTTON`, `LOAD_UI_RESOURCE_COMPLETE:SAVEFILEUI_TYPE`, and opened the save-file target set at `stage.0.7.2.3` / `stage.0.7.2.4`. |
| `stage.0.3.0.2` | `(775,429)` | save/menu UI plus resource wave | Triggered `CLICK_TEXT_CHOICE_BUTTON`, `LONG_DOWN_CANCEL_BY_BRANCH`, `SAVEFILEUI_TYPE`, `Graphics/Background/传送门.jpg`, `Graphics/Oafs/红瓣540\\红瓣540_bg.png`, and the known two `/null%20path` requests. |
| `stage.0.3.0.3` | `(678,128)` | branch/menu transition | Triggered `CLICK_TEXT_CHOICE_BUTTON` and `LONG_DOWN_CANCEL_BY_BRANCH`; target set reduced to the two right-side buttons. |
| `stage.0.3.0.4` | `(582,129)` | settings UI | Triggered `CLICK_TEXT_CHOICE_BUTTON`, `LOAD_UI_RESOURCE_COMPLETE:SETUI_TYPE`, and loaded `Graphics/UI/ui导入/底图/设置.jpg`, `数值前.png`, and `数值后.png`; target list became empty in the 5s sample window. |
| `stage.0.7.0` | `(921,54)` | main menu/resource wave | Opened the main menu overlay and initially exposed a large batch of real `/shareres/<md5>` 404s for menu buttons and related UI assets. |
| `stage.0.7.1` | `(921,124)` | platform/API boundary | Added `请稍候...` loading text and hit malformed platform JSONP `http://https//www.66rpg.com/ajax/game/get_game_info.json...`; no new mapped local asset miss was identified. |

- Resource-miss loop:
  - Ran `python 66rpgProjectDropper\prepare_runner_mirror.py 1569947 --version 364 --root . --mirror-log .http-server.err.log`.
  - The script resolved all observed mapped `/shareres/<md5>` misses through `Map.bin` and mirrored the missing local files.
  - Important newly mirrored groups include:
    - main menu background/buttons: `Graphics/Other/菜单底图.jpg`, `Graphics/Button/开始*.png`, `Graphics/Button/ui导入/*`
    - save UI: `Graphics/UI/ui导入/底图/档案.jpg` and related choice/bookmark buttons
    - settings UI: `Graphics/UI/ui导入/底图/设置.jpg`, `数值前.png`, `数值后.png`
    - create-character flow: `Graphics/Half/创建人物/*`, `Graphics/Oafs/动态立绘1/*`
    - menu/platform-adjacent buttons such as `商城`, `属性`, `当前任务`, `宠物`, `每日签到`, `分线`, `确认`
- Retest after mirroring:
  - repeated `(921,54)`
  - local HTTP log showed the former menu `/shareres` requests returning `200`
  - no new real `/shareres/<md5>` 404 appeared
  - only the known two `/null%20path` 404s remained
  - `UI TARGETS` expanded to many main-menu overlay targets, including `stage.0.6.0.1`, `stage.0.6.0.2`, `stage.0.6.0.6`, `stage.0.6.0.7`, and others

Current technical conclusion: isolated first-scene target classification is complete for the current stable target set. The next useful validation should probe the newly exposed main-menu overlay targets after `(921,54)`, while treating `(921,124)` as a platform/API boundary until platform service stubs are implemented.

## Round 22: Main Menu Overlay Target Classification

- Reused the Round 21 path:
  - reload with `clearStorage=1`
  - click title cover `(480,270)`
  - wait for first-scene `UI TARGETS`
  - click `(921,54)` to open the main menu overlay
  - click one `stage.0.6.0.*` target per isolated run
- Tested all 15 menu overlay targets listed in `DEBUG_SUMMARY_AND_NEXT_STEPS.md`.

| Menu target | Coordinate | Classification | Result |
| --- | --- | --- | --- |
| `stage.0.6.0.1` | `(944,475)` | close/collapse | Menu overlay closed back to first-scene targets plus right-side buttons. |
| `stage.0.6.0.2` | `(168,112)` | mall/platform boundary | Triggered `LOAD_UI_RESOURCE_COMPLETE:NEW_MALLUI_TYPE` and a browser `Script error. @ :0:0`. After resource mirroring, no mapped local 404 remained. |
| `stage.0.6.0.6` | `(601,324)` | save-file UI | Triggered `LOAD_UI_RESOURCE_COMPLETE:SAVEFILEUI_TYPE` and exposed save-file right-side targets. |
| `stage.0.6.0.7` | `(221,272)` | submenu | Loaded a small submenu with targets around `(124,182)` and `(124,221)`. |
| `stage.0.6.0.9` | `(851,203)` | submenu/gallery-like UI | Loaded a UI with targets around `(200,328)`, `(30,424)`, and `(891,420)`. |
| `stage.0.6.0.10` | `(174,485)` | UI transition/close-like | Triggered a resource wave and returned to first-scene targets. |
| `stage.0.6.0.11` | `(325,499)` | submenu | Loaded a UI with targets around `(892,329)` and `(931,425)`. |
| `stage.0.6.0.12` | `(72,512)` | CG/gallery UI | Triggered `LOAD_UI_RESOURCE_COMPLETE:CGUI_TYPE`; only known `/null%20path` requests appeared. |
| `stage.0.6.0.13` | `(210,469)` | UI transition | Triggered a resource wave and returned to first-scene targets. |
| `stage.0.6.0.14` | `(318,426)` | backpack/items UI | After mirroring, opened an item-category UI with many left-side category targets such as `(74,46)`, `(74,93)`, `(74,140)`, etc. |
| `stage.0.6.0.15` | `(75,439)` | welfare/event UI | After mirroring, opened a right-side vertical menu UI with targets around `x=956` and a left target around `(74,465)`. |
| `stage.0.6.0.16` | `(196,371)` | no-op/menu remains | Emitted `CLICK_SCUI_BUTTON`, but the menu target set stayed effectively unchanged. |
| `stage.0.6.0.17` | `(66,397)` | welfare/event UI | Same right-side vertical menu pattern as `stage.0.6.0.15`. |
| `stage.0.6.0.18` | `(882,117)` | close/return | Menu overlay closed back to first-scene targets. |
| `stage.0.6.0.19` | `(818,115)` | close/return | Menu overlay closed back to first-scene targets. |

- First pass exposed new real `/shareres/<md5>` 404s from several submenus, especially:
  - mall / product detail assets
  - backpack / item category assets
  - pet, sign-in, wardrobe, character-image, and welfare/event assets
  - gallery / locked-image assets
- Mirroring command:
  - `python 66rpgProjectDropper\prepare_runner_mirror.py 1569947 --version 364 --root . --mirror-log .http-server.err.log`
- Important newly mirrored groups include:
  - `Graphics/UI/ui导入/底图/商城.jpg`
  - `Graphics/Other/背包/*`
  - `Graphics/Other/宠物/*`
  - `Graphics/Other/签到/*`
  - `Graphics/Other/衣橱/*`
  - `Graphics/Other/形象选择/*`
  - `Graphics/UI/ui导入/底图/鉴赏.jpg`
  - welfare/event assets such as `Graphics/Other/福利/累充福利.jpg`
- Retested representative resource-wave entries after mirroring:
  - `stage.0.6.0.2`
  - `stage.0.6.0.14`
  - `stage.0.6.0.15`
  - `stage.0.6.0.17`
- Retest result:
  - previous mapped `/shareres` misses now return `200` or `304`
  - no new real `/shareres/<md5>` 404 appeared in the retest window
  - only the known `/null%20path` 404s remained
  - `stage.0.6.0.2` still emits `Script error. @ :0:0`, so mall/platform behavior likely needs platform-service stubbing rather than more static assets

Current technical conclusion: main menu overlay classification is complete for the first-level menu targets, and the local mirror now covers the representative resource-heavy submenus tested. The next useful validation is to go one level deeper into the submenus that now open successfully: backpack category targets, welfare/event vertical menu targets, gallery targets, and the two-button submenu from `stage.0.6.0.7`. Mall should be tracked separately as a platform/API boundary.

## Round 23: Second-Level Submenu Probe

- Reused the Round 22 isolated path:
  - reload with `clearStorage=1`
  - click title cover `(480,270)`
  - click `(921,54)` to open the main menu overlay
  - click one first-level submenu target
  - click one exposed second-level target per isolated run
- Probed backpack/items, two-button submenu, CG/gallery, and welfare/event paths.

| Parent path | Second-level target | Coordinate | Classification | Result |
| --- | --- | --- | --- | --- |
| backpack/items `(318,426)` | `bp.0` | `(74,46)` | category switch | Reopened/reloaded backpack category UI; 52 image loads; no script error. |
| backpack/items `(318,426)` | `bp.1` | `(74,93)` | category switch | Reopened/reloaded backpack category UI; 52 image loads; no script error. |
| backpack/items `(318,426)` | `bp.2` | `(74,140)` | category switch | Category UI; 48 image loads; no script error. |
| backpack/items `(318,426)` | `bp.3` | `(74,187)` | category switch | Category UI; 48 image loads; no script error. |
| backpack/items `(318,426)` | `bp.4` | `(74,234)` | category switch | Category UI; 52 image loads; no script error. |
| backpack/items `(318,426)` | `bp.5` | `(74,281)` | category/page switch | Category UI with small resource wave; exposes an extra target near `(925,496)`. |
| backpack/items `(318,426)` | `bp.6` | `(74,328)` | item/prop category | Category UI with prop/title resources; first pass exposed new mapped `/shareres` misses, then passed after mirroring. |
| backpack/items `(318,426)` | `bp.7` | `(74,375)` | category/page switch | Category UI with small resource wave; exposes a target near `(343,327)`. |
| backpack/items `(318,426)` | `bp.8` | `(74,422)` | category/page switch | Category UI with small resource wave; no script error. |
| backpack/items `(318,426)` | `bp.close` | `(46,481)` | category-like/no close | Behaved like a category refresh rather than closing; exposes a target near `(925,496)`. |
| backpack/items `(318,426)` | `bp.side0` | `(159,69)` | no-op/detail slot | Emitted `CLICK_SCUI_BUTTON` plus cancel noise; target set stayed effectively unchanged. |
| backpack/items `(318,426)` | `bp.side1` | `(159,184)` | no-op/detail slot | Emitted `CLICK_SCUI_BUTTON`; no meaningful target-set change. |
| backpack/items `(318,426)` | `bp.side2` | `(159,299)` | no-op/detail slot | Emitted `CLICK_SCUI_BUTTON`; no meaningful target-set change. |
| two-button submenu `(221,272)` | `two.0` | `(124,182)` | opens deeper UI | Opened a new UI with targets around `(432,478)`, `(617,474)`, and `(925,503)`; 38 image loads; no script error. |
| two-button submenu `(221,272)` | `two.1` | `(124,221)` | mostly no-op | Submenu remained visible; no new resource wave or script error. |
| CG/gallery `(72,512)` | `cg.0` | `(536,413)` | gallery item click | Triggered `SHOW_CG_UI_ITEM_MSG` and `SHOW_CG_UI_ITEM`; no script error. |
| CG/gallery `(72,512)` | `cg.1` | `(632,417)` | gallery item click | Triggered `SHOW_CG_UI_ITEM_MSG` and `SHOW_CG_UI_ITEM`; no script error. |
| CG/gallery `(72,512)` | `cg.2` | `(775,429)` | gallery item click | Triggered `SHOW_CG_UI_ITEM_MSG` and `SHOW_CG_UI_ITEM`; no script error. |
| welfare/event `(75,439)` | `wf.0`-`wf.7` | `(956,65)` through `(956,493)` | vertical menu/page switch | Each emitted `CLICK_SCUI_BUTTON`; kept the same vertical menu pattern; first pass exposed one audio resource miss, then passed after mirroring. |
| welfare/event `(75,439)` | `wf.left` | `(74,465)` | return/collapse | Returned to the first-scene/right-button target set; no script error. |

- New real mapped `/shareres/<md5>` misses observed during second-level probing:
  - `3600bf9b7d679f703bb1d27c573d7fa7` -> title/label asset
  - `e25afea88a8f80f92e64f2222b951445` -> title/label selected asset
  - `f8196840cfb5fb51bd035f920ec7a734` -> sign-in button
  - `d879ac7a74ebf4c3da7e542a087db076` -> sign-in button selected
  - `df8976233d87caa4b768a8aca267fc59` -> locked title/label asset
  - `e9d3f3f2dbaeaef791400d16595e7cde` -> `audio/se/error_1.mp3`
- Mirroring command:
  - `python 66rpgProjectDropper\prepare_runner_mirror.py 1569947 --version 364 --root . --mirror-log .http-server.err.log`
- Representative retests after mirroring:
  - backpack `bp.6` `(74,328)`: triggered `CLICK_SCUI_BUTTON` and `LOAD_UI_RESOURCE_COMPLETE`, no script error, all mapped resources returned `200` or `304`.
  - welfare `wf.0` `(956,65)`: triggered `CLICK_SCUI_BUTTON`, no script error, audio resource returned `200/304`.
  - welfare `wf.left` `(74,465)`: returned to first-scene/right-button targets, no script error.
- Local HTTP log after the mirror/retest window:
  - no new real `/shareres/<md5>` `404`
  - only the known `/null%20path` requests remain
- Browser console note:
  - repeated `NotAllowedError: play() failed because the user didn't interact with the document first` appears during automated reloads; this is browser autoplay policy noise and not a mapped resource miss.
  - occasional browser-control `Statsig` network timeout messages are external tooling noise and not game runtime behavior.

Current technical conclusion: the planned second-level submenu probe is complete for the representative exposed targets. Static resources for those paths are mirrored enough that retests no longer produce real `/shareres` 404s. The next useful validation is deeper than Round 23: probe the newly exposed deeper UI targets from two-button submenu and backpack category/detail pages, and separately define platform/service stubs for mall and account-like features.

## Round 24: Deeper UI Probe

- Continued from the Round 23 next direction.
- Browser viewport was forced to `960x540`.
- Local HTTP server log baseline for this round:
  - before two-button deeper probing: line `3616`
  - after mirroring two-button deeper misses: line `3721`
  - before backpack deeper probing: line `3739`

### Two-Button Deeper UI

Path:

1. click title cover `(480,270)`
2. click main menu `(921,54)`
3. click first-level two-button submenu `(221,272)`
4. click top option `(124,182)`
5. probe deeper targets `(432,478)`, `(617,474)`, and `(925,503)`

| Deeper target | Classification | Result |
| --- | --- | --- |
| `(432,478)` | confirm/transition-like | Triggered `CLICK_SCUI_BUTTON`, `LOAD_UI_RESOURCE_COMPLETE`, 14 image loads, and target count dropped from 20 to 12. No script error. |
| `(617,474)` | refresh/reopen-like | Triggered `CLICK_SCUI_BUTTON`, `LOAD_UI_RESOURCE_COMPLETE`, 38 image loads, and target count stayed 20. No script error. |
| `(925,503)` | close/return | Triggered `CLICK_SCUI_BUTTON` and returned to first-scene/right-button target set. No resource wave and no script error. |

New mapped resource misses exposed by the first pass:

- `c5be296d8fc3dfb5ac20bbbbb180b4a1` -> `graphics/other/称号/称号/称号4.jpg`
- `87d0fc55a07cda95560a418edefb542a` -> `graphics/other/称号/称号/称号2.jpg`

Mirroring command:

```powershell
python 66rpgProjectDropper\prepare_runner_mirror.py 1569947 --version 364 --root . --mirror-log .http-server.err.log
```

Retest result:

- `(432,478)` requested `c5be296d8fc3dfb5ac20bbbbb180b4a1`, now `200`.
- `(617,474)` requested `87d0fc55a07cda95560a418edefb542a`, now `200`.
- No new real `/shareres/<md5>` 404 appeared after the two-button retest.

### Backpack Deeper Targets

| Setup path | Deeper target | Classification | Result |
| --- | --- | --- | --- |
| backpack `(318,426)` -> `bp.5` `(74,281)` | `(925,496)` | close/return | Triggered `CLICK_SCUI_BUTTON`; target count dropped from 16 to 7 and returned to first-scene/right-button targets. No resource wave or script error. |
| backpack `(318,426)` -> `bp.6` `(74,328)` | `(672,193)` | no effective hit | No `CLICK_SCUI_BUTTON`, no resource wave, target count stayed 20. Likely coordinate was near a displayed target but not an active click area in this state. |
| backpack `(318,426)` -> `bp.7` `(74,375)` | `(343,327)` | no effective hit | No `CLICK_SCUI_BUTTON`, no resource wave, target count stayed 18. Likely coordinate was near a displayed target but not an active click area in this state. |

Backpack deeper HTTP result:

- No new real `/shareres/<md5>` 404 appeared after line `3739`.
- New backpack/deeper resources requested during this round returned `200` or `304`.
- Only known `/null%20path` requests remained.

### Welfare Longer Stabilization

Path:

1. click title cover `(480,270)`
2. click main menu `(921,54)`
3. click welfare/event `(75,439)`
4. click right-side target `(956,65)`
5. wait 9 seconds

Result:

- Target count stayed at 14.
- Target pattern stayed the same right-side vertical menu family.
- No deeper inner-page target set appeared during the 9-second stabilization window.
- No script error appeared.

Current technical conclusion: the deeper two-button UI path is now classified and its newly exposed title-image resources are mirrored. Backpack deeper probing found one reliable close/return target and two coordinate probes that do not hit effective buttons in the current state. Welfare/event does not expose a further inner target set after a longer wait. The next useful validation should either add better target-coordinate extraction for Laya nodes or move to platform/service boundary work, especially mall/shop and account-like features.

## Round 25: Enhanced UI Target Trace

- Implemented runner-side `traceUiState` improvements in `h5_runner_experiment.html`.
- `UI TARGETS` now includes:
  - `x` / `y` aliases for the click center, in addition to `cx` / `cy`
  - `left`, `top`, `right`, `bottom`
  - `w`, `h`
  - `texture`
  - `listeners`
  - `mouseEnabled`
  - `likelyInteractive`
  - `boundsSource`
- `UI STATE` nodes now also include texture, listener, alpha, disabled, and bounds details.
- Important implementation detail:
  - Laya `getBounds()` can already include accumulated offsets for some nodes.
  - For nodes with non-zero `width` and `height`, target centers now prefer `globalX/globalY + width/height`.
  - `getBounds()` is used as a fallback for zero-sized texture children and supplemental state data.
- Target filtering was tightened:
  - action-listener nodes such as `click`, `mousedown`, and `mouseup` are preferred
  - pure texture children are not emitted as duplicate targets when their clickable parent carries the event listeners
  - parent buttons can inherit a single child texture URL for easier resource identification

Validation:

- Forced a cache-busted reload with `traceUiState=1` and `patchTitleClick=1`.
- First-scene target output returned to the expected 7 clickable targets:
  - `stage.0.3.0.0` `(536,413)`
  - `stage.0.3.0.1` `(632,417)`
  - `stage.0.3.0.2` `(775,429)`
  - `stage.0.3.0.3` `(678,128)`
  - `stage.0.3.0.4` `(582,129)`
  - `stage.0.7.0` `(921,54)`
  - `stage.0.7.1` `(921,124)`
- Main menu target output now includes enhanced fields while preserving known centers such as:
  - `stage.0.6.0.2` `(168,112)`
  - `stage.0.6.0.7` `(221,272)`
  - `stage.0.6.0.14` `(318,426)`
  - `stage.0.6.0.15` `(75,439)`
- Example improvement:
  - `stage.0.7.0` now carries its inherited texture URL `game_menu2_web.png` and event listener list including `click`.

Current technical conclusion: `UI TARGETS` is now more suitable for automated probing because it exposes reliable `x/y` click centers, visible bounds, texture hints, and listener metadata. The next useful validation is to re-run a small backpack deeper probe with the enhanced target output and use the emitted exact centers instead of hand-picked approximate coordinates.

## Round 26: Backpack Reprobe With Enhanced Targets

- Reused the enhanced `UI TARGETS` output from Round 25.
- Local HTTP log baseline: line `4036`.
- Path:
  1. reload with `clearStorage=1`
  2. click title cover `(480,270)`
  3. click main menu `(921,54)`
  4. click backpack `(318,426)`
  5. click category `bp.6` `(74,328)`
  6. inspect emitted target centers before clicking deeper controls

Enhanced target output for `bp.6` showed:

- the previously hand-picked approximate point `(672,193)` does not correspond to an emitted clickable target in this state
- actual emitted clickable targets include:
  - bottom vertical slots: `(210,476)`, `(331,476)`, `(451,476)`, `(570,476)`, `(690,476)`, `(810,476)`
  - action/detail-like targets: `(626,320)` and `(785,354)`

Representative exact-target clicks:

| Target path | Coordinate | Classification | Result |
| --- | --- | --- | --- |
| `stage.0.6.0.24` | `(626,320)` | actionable/no visible state change | Triggered `CLICK_SCUI_BUTTON`; target count stayed 25; no resource wave and no script error. |
| `stage.0.6.0.25` | `(785,354)` | actionable/no visible state change | Triggered `CLICK_SCUI_BUTTON`; target count stayed 25; no resource wave and no script error. |

HTTP result:

- no new real `/shareres/<md5>` 404 appeared after line `4036`
- only the known `/null%20path` requests appeared

Current technical conclusion: the enhanced target trace resolved the earlier false coordinate probe. `(672,193)` was not a real emitted target; the nearby real `bp.6` controls are `(626,320)` and `(785,354)`. Both are clickable but currently do not produce visible target-set or resource changes in the sample window. The next useful validation can continue exact-target probing of the bottom slots, or switch to the mall/shop platform boundary.

## Round 27: Backpack `bp.6` Bottom Slot Probe

- Continued exact-target probing with enhanced `UI TARGETS`.
- Local HTTP log baseline: line `4173`.
- Path per isolated run:
  1. reload with `clearStorage=1`
  2. click title cover `(480,270)`
  3. click main menu `(921,54)`
  4. click backpack `(318,426)`
  5. click category `bp.6` `(74,328)`
  6. click one emitted bottom slot target

| Target path | Coordinate | Result |
| --- | --- | --- |
| `stage.0.6.0.16` | `(210,476)` | Triggered `CLICK_SCUI_BUTTON`; target count stayed 25; no resource wave, no script error. |
| `stage.0.6.0.17` | `(331,476)` | Triggered `CLICK_SCUI_BUTTON`; target count stayed 25; one `LOAD_IMAGE_COMPLETE`; no script error. |
| `stage.0.6.0.18` | `(451,476)` | Triggered `CLICK_SCUI_BUTTON`; target count stayed 25; one `LOAD_IMAGE_COMPLETE`; no script error. |
| `stage.0.6.0.19` | `(570,476)` | Triggered `CLICK_SCUI_BUTTON`; target count stayed 25; one `LOAD_IMAGE_COMPLETE`; no script error. |
| `stage.0.6.0.20` | `(690,476)` | Triggered `CLICK_SCUI_BUTTON`; target count stayed 25; one `LOAD_IMAGE_COMPLETE`; no script error. |
| `stage.0.6.0.21` | `(810,476)` | Triggered `CLICK_SCUI_BUTTON`; target count stayed 25; one `LOAD_IMAGE_COMPLETE`; no script error. |

HTTP result:

- no new real `/shareres/<md5>` 404 appeared after line `4173`
- resource requests were `200` or `304`
- only known `/null%20path` requests appeared

Current technical conclusion: all sampled `bp.6` bottom slots are valid clickable nodes, but they behave as stable/no-visible-change controls in the 5-second sample window. They do not open deeper target sets, do not trigger UI resource loads, and do not expose missing static resources. The next useful validation is to move to the mall/shop platform boundary (`stage.0.6.0.2`) or add state-variable tracing if these silent backpack clicks need deeper interpretation.

## Round 28: Mall `GetImageBase64` Boundary

- Local HTTP log baseline: line `4423`.
- Path:
  1. reload with `clearStorage=1`
  2. click title cover `(480,270)`
  3. click main menu `(921,54)`
  4. click exact mall target `stage.0.6.0.2` `(168,112)`

Pre-fix result:

- main-menu target count before mall click: `23`
- target count after mall click: `5`
- `LOAD_UI_RESOURCE_COMPLETE` emitted with parameter `NEW_MALLUI_TYPE`
- browser console exposed the real underlying error:
  - `Uncaught TypeError: window.GetImageBase64 is not a function`
- debug overlay also logged:
  - `ERROR: Script error. @ :0:0`
- no new real `/shareres/<md5>` 404 appeared

Fix applied:

- added a local `window.GetImageBase64(url, width, height, callback)` compatibility stub in `h5_runner_experiment.html`
- implementation loads the image, draws a requested-size canvas, converts it to PNG data URL, and calls the runtime callback
- failures return an empty string and log the failed URL

Post-fix result:

| Check | Result |
| --- | --- |
| `NEW_MALLUI_TYPE` resource completion | emitted once |
| `GetImageBase64` callback | succeeded 6 times at `72x72` |
| `Script error. @ :0:0` | gone |
| real `/shareres/<md5>` 404 | none |
| mall target set | opens to 6 targets |
| new mall target | `stage.0.7.2.12` `(921,455)` |

The new mall target `(921,455)` was clicked once:

- target count changed from `6` back to the main-menu `23`
- no new `Script error`
- no new resource wave
- no new real `/shareres/<md5>` 404

Remaining platform issue:

- mall still emits malformed PropShop JSONP script URLs:
  - `http:https://www.66rpg.com/PropShop/engine/v1/user/getUserHaveAllPropNum...`
  - `http:https://www.66rpg.com/PropShop/engine/v1/user/getMyAccountMoney...`
- the browser normalizes these into failed `http://https//www.66rpg.com/...` script loads

Current technical conclusion: the mall was not blocked by missing static assets. The immediate crash was a missing host bridge function, `GetImageBase64`; the compatibility stub allows the new mall UI to open and close. The next useful validation is to stub or intercept the PropShop JSONP responses so mall account/owned-item state is deterministic locally.

## Round 29: PropShop JSONP Stub

- Local HTTP log baseline: line `4469`.
- Added a gated `stubPropShop=1` runner option.
- The stub intercepts `HTMLScriptElement.src` only for PropShop JSONP URLs and rewrites them to local `data:text/javascript` callback scripts.

Stubbed endpoints:

| Endpoint | Payload |
| --- | --- |
| `/PropShop/engine/v1/user/getUserHaveAllPropNum` | `{ "status": 1, "data": [] }` |
| `/PropShop/engine/v1/user/getMyAccountMoney` | `{ "status": 1, "data": { "coin_count": 0 } }` |
| `/PropShop/engine/v1/user/getUserHavePropNum` | `{ "status": 1, "data": [] }` |

Validation URL added `stubPropShop=1`.

Path:

1. wait for title target
2. click title cover `(480,270)`
3. wait for first-scene targets
4. click main menu `(921,54)`
5. click exact mall target `stage.0.6.0.2` `(168,112)`
6. click mall close/return target `stage.0.7.2.12` `(921,455)`

Result:

| Check | Result |
| --- | --- |
| title target count | `1` |
| first-scene target count | `7` |
| main-menu target count | `23` |
| mall target count | `6` |
| target count after close | `23` |
| PropShop JSONP stub hits | `4` |
| PropShop script resource errors | `0` |
| `GetImageBase64` conversions | `6` |
| `Script error. @ :0:0` | `0` |
| real `/shareres/<md5>` 404 | `0` |

Remaining noise:

- `get_home_gray` still fails as a separate platform/telemetry script.
- known `/null%20path` requests still appear.

Current technical conclusion: the new mall can now open and close locally with deterministic fake account state. The previous PropShop malformed URL failures are neutralized when `stubPropShop=1` is enabled. The next useful validation is to click mall item/buy/detail targets under this stub and identify any additional PropShop endpoints needed for purchase/status flows.

## Round 30: Mall Item Target Trace

- Local HTTP log baseline: line `4477`.
- Added detail logging for mall-related `EventCenter.dispatchEvent` payloads:
  - `MALL EVENT DETAIL <type> <parameter summary>`
  - object summaries are depth-limited and skip private/function fields

Validation URL kept `stubPropShop=1`.

Path:

1. reload runner
2. click title cover `(480,270)`
3. open main menu `(921,54)`
4. open mall through `stage.0.6.0.2` `(168,112)`
5. click mall non-close targets around `(536,413)`, `(632,417)`, and `(775,429)`

Observed mall state:

| Check | Result |
| --- | --- |
| mall opens under `stubPropShop=1` | yes |
| mall target count | `6` |
| PropShop stub errors | none |
| real `/shareres/<md5>` 404 | none |
| `Script error. @ :0:0` | none |
| new purchase/status endpoint | none observed |

Event findings:

- One item-like click on `(536,413)` emitted `CLICK_NEW_MALL_ITEM_BG`.
- That sample did not request `/getUserHavePropNum`, `/createBuyOrder`, or any new PropShop endpoint.
- The target set dropped to `0` in that sample, suggesting the click may move the mall into a transient or visually changed state that the current `UI TARGETS` trace does not describe well.
- A clean retest with detail logging captured mall refresh events such as `MALL EVENT DETAIL UPDATE_MALL_ITEM -2` and `MALL EVENT DETAIL UPDATE_MALL_ITEM -1`.
- Repeated clicks on the emitted non-close coordinates did not reliably emit additional mall item/buy events in the current target trace.

Current technical conclusion: the PropShop/opening boundary is stable. The next mall blocker is no longer a missing endpoint; it is insufficient state visibility for the mall item list and selected item. The next useful validation is a mall-specific object/state trace, for example selected item id, visible mall item records, and the mediator/view object handling `CLICK_NEW_MALL_ITEM_BG`.

## Round 31: Main Story And Save/Load Smoke Test

- Local HTTP log baseline: line `5325`.
- Added `screenX/screenY` and screen bounds to `UI TARGETS`.
- Reason: the Laya stage reports `960x540` coordinates, while the browser canvas was displayed at `1280x720`; direct browser clicks need scaled screen coordinates.

Validation URL kept `stubPropShop=1`.

Main story path:

1. reload with `clearStorage=1`
2. click title cover
3. reach first playable scene with 7 targets
4. click main story/branch target `stage.0.3.0.0` at stage `(536,413)`, screen `(715,551)`
5. reach new CG/story scene with target `stage.0.3.0.0` at stage `(896,55)`
6. click stage `(896,55)`, screen `(1195,73)`
7. reach another visually distinct CG/story scene

Main story result:

| Check | Result |
| --- | --- |
| title to first scene | pass |
| first scene to CG/story scene | pass |
| second CG/story click | pass |
| auto-save log | `自动存档`, `自动存档204` after story transitions |
| new real `/shareres/<md5>` 404 | none |
| `Script error. @ :0:0` | none |

Save/load path:

1. from first scene, click the save/archive target `stage.0.3.0.1` at stage `(632,417)`, screen `(843,556)`
2. archive UI opens
3. screenshot confirms the archive page with local/cloud buttons
4. click an empty visible local slot area
5. click cloud button

Save/load result:

| Check | Result |
| --- | --- |
| archive UI opens | pass |
| archive UI target count | `3` |
| local archive slot click | no effective write/load action observed in empty slot sample |
| cloud archive click | blocked by login boundary |
| cloud warning text | `未登录不能使用云存档。` |
| new real `/shareres/<md5>` 404 | none |
| `Script error. @ :0:0` | none |

HTTP log after the baseline showed only normal `200`/`304` resource hits plus the known `/null%20path` 404 pair. A new story resource `54081a0390cb6af5fccf9db34a25c4d4` returned `200`.

Current technical conclusion: core local story playback is viable beyond the first scene when clicks use screen-scaled coordinates. Auto-save is firing successfully enough to log `204`. Manual archive UI opens locally, but local slot write/read behavior is not yet proven; cloud archive is explicitly a platform/login boundary and should be disabled or stubbed for a local MVP.

## Round 32: Local Auto-Save Persistence And Reload Restore

- Local HTTP log baseline: line `5478`.
- Added `traceStorage=1` runner instrumentation for local storage persistence:
  - `localStorage` / `sessionStorage` `setItem`, `removeItem`, and `clear`
  - non-empty `getItem` reads
  - storage key snapshots when storage changes
  - `indexedDB.open` calls
- `traceStorageVerbose=1` can be used when empty `getItem` probes are needed.

Auto-save write validation:

1. reload with `clearStorage=1` and `traceStorage=1`
2. click title cover
3. advance the main story target at screen `(715,551)`
4. advance the next story target at screen `(1195,73)`

Observed writes:

| Step | Storage key | Length |
| --- | --- | --- |
| first story advance | `save0a235c54f16c431ab5736c92997edb47undefined-100` | `3045` |
| later story advance | `save0a235c54f16c431ab5736c92997edb47undefined-100` | `3341` |

Relevant runtime logs:

- `自动存档`
- `STORAGE localStorage.setItem key=save0a235c54f16c431ab5736c92997edb47undefined-100 ...`
- `自动存档204`

Reload/read validation:

1. reload without `clearStorage=1`
2. keep `traceStorage=1`
3. wait for game initialization

Observed reads:

| Check | Result |
| --- | --- |
| save key survives reload | pass |
| save key read by runtime | pass |
| non-empty read length | `3341` |
| restored state target pattern | story-layer right-side menu targets, not title-only UI |
| new real `/shareres/<md5>` 404 | none |
| `Script error. @ :0:0` | none |

HTTP log after the baseline showed:

- runner reloads returned `200`
- `shareres/7b/7b633df854b9742c1a653e134ee6f2d8` returned `200`
- only the known `/null%20path` 404 pair appeared

Current technical conclusion: local auto-save now has a proven persistence loop. The runtime writes the auto-save to `localStorage`, the value survives a reload, and the runtime reads the same non-empty save key on initialization. This is enough to treat browser-local auto-save recovery as working for the local-play MVP. Manual archive slot write/load is still a separate UI path and remains unproven.

## Round 33: Main Story Longer-Run Probe

- Local HTTP log baseline: line `5488`.
- Goal: extend the main-story validation beyond the previous two transitions.
- Added optional `traceFullTargets=1` to allow `UI TARGETS` to include large/full-screen clickable surfaces when needed.

Long-run observations:

1. Reloaded with `clearStorage=1`, `traceUiState=1`, `traceStorage=1`, and `stubPropShop=1`.
2. The runner auto-save path still wrote the local auto-save key:
   - `save0a235c54f16c431ab5736c92997edb47undefined-100`
   - observed length: `3341`
3. `UI TARGETS` only exposed the right-side system menu buttons in the sampled black-screen state.
4. A clipped browser screenshot confirmed a full black viewport.
5. Coordinate-driven continuation attempts did not increase the auto-save length or expose a new target set.

New resource miss found:

| MD5 | Mapped file | Result |
| --- | --- | --- |
| `d66f13cb49738edd14ba4f6aecf577cb` | `graphics/half/创建人物/3.jpg` | mirrored locally |

Mirror command:

```powershell
python 66rpgProjectDropper\prepare_runner_mirror.py 1569947 --version 364 --root . --mirror-md5 d66f13cb49738edd14ba4f6aecf577cb
```

Retest after mirroring:

| Check | Result |
| --- | --- |
| direct local request for `d66...` | `200` |
| retest request for `d66...` | `200` |
| new real `/shareres/<md5>` 404 after retest | none |
| `Script error. @ :0:0` | none |
| viewport after continuation attempts | black |
| auto-save length after continuation attempts | unchanged at `3341` |

Current technical conclusion: the next main-story blocker is no longer a missing mapped asset in this sampled path. The newly discovered `graphics/half/创建人物/3.jpg` miss is fixed, but the long-run path still reaches a black-screen/stalled story state with no script error and no new real `/shareres/<md5>` 404. The next validation should inspect runtime scene/display state during the black screen: visible Laya nodes, active story index/command, current background/half-body resource ids, and whether an overlay or alpha state is hiding the rendered scene.

## Round 34: Black-Screen Runtime Display Trace

- Local HTTP log baseline: line `5522`.
- Added display/runtime trace improvements:
  - `traceDisplay=1` display-tree sampler
  - deeper `RUNTIME STATE` node summaries when `traceDisplay=1`
  - texture, text, z-order, mouse, and graphics metadata in runtime child summaries

Validation path:

1. reload with `clearStorage=1`
2. click title center
3. click the known first branch point
4. click the known top-right story point twice
5. wait for runtime/display logs and capture a clipped screenshot

Observed state:

| Check | Result |
| --- | --- |
| screenshot | full black viewport |
| new real `/shareres/<md5>` 404 | none |
| fixed `d66...` resource | requested as `304` / cached success |
| `Script error. @ :0:0` | none |
| stage root | present |
| main stage child | visible, `960x540`, `numChildren=13` |
| visible full-size display layer | present but no texture reported in the reliable runtime summary |
| candidate content groups | several full-size children under `stage.0.2` are `visible:false` |
| auto-save key | unchanged from the previous black-screen sample |

Important trace caveat:

- The standalone `DISPLAY STATE` branch did not emit in the browser trace even though the served HTML contains it.
- The already-reliable `RUNTIME STATE` logs did emit and were used for the current conclusion.
- The next step should keep using/expanding `RUNTIME STATE` unless the `traceDisplay` branch activation issue is resolved.

Current technical conclusion: the black screen is now more likely a runtime display/state problem than a static asset miss. The stage is alive and the game main object exists, but the visible full-screen display stack does not expose an active texture in the current runtime summary, while other full-screen candidate content groups are hidden. The next validation should identify which story/display manager owns `stage.0.0`, `stage.0.2`, and `stage.0.3`, then trace the command that hides content or fails to assign the next background/half-body texture.
