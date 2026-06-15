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
