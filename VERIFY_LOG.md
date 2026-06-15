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
