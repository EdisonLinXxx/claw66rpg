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
