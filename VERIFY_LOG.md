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
