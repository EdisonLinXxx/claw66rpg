# Official Player Compatibility Modularization

> Historical note: this report describes the first source-module refactor. The
> runtime profile list was replaced on 2026-07-12 by dynamically loaded
> `official_player_game_profiles/<gameId>.js` files; see `PRIMARY_PLAY_PATH.md`
> for the current architecture.

## Scope

Refactor the v2 official-player compatibility layer without changing its public
browser entry point or mixing in new game fixes. The browser still loads one
generated file, `official_player_compat.js`.

## Source Architecture

- `official_player_compat_src/00-core.js`: ordered patch registry and profile matching.
- `official_player_compat_src/05-game-profiles.js`: the only source module containing game GUID/version rules.
- `official_player_compat_src/10-built-in-menu.js`: built-in menu fallbacks.
- `official_player_compat_src/20-platform-state.js`: entitlement and inventory state helpers.
- `official_player_compat_src/30-local-save.js`: local save routing and payload normalization.
- `official_player_compat_src/40-platform-api.js`: host/API contracts and development unlock behavior.
- `official_player_compat_src/50-binary-parser.js`: capability-based binary parser patches.
- `official_player_compat_src/60-free-time.js`: standalone free-time behavior.
- `official_player_compat_src/70-storage-trace.js`: storage tracing and archive bridging.
- `official_player_compat_src/90-bootstrap.js`: retry lifecycle.

The build script concatenates the shared-closure source modules in a fixed order.
Patch registration carries an explicit numeric order, preserving the previous
installation sequence even when source modules move.

## Game Profiles

| Profile | Match | Capabilities |
| --- | --- | --- |
| `66rpg-1569947-legacy-v2` | GUID `0a235c54f16c431ab5736c92997edb47`, all versions | `padded-dbutton`, `extended-dsystem` |
| `66rpg-1683317-v1544` | GUID `468fe16ef100b2f24215e6874783ad66`, version `1544` | `extended-dsystem`, `native-v108-sized-cui` |
| `66rpg-1692665-v56` | GUID `9076a69f88f6c963ec508dabe224a73e`, version `56` | `extended-dsystem`, `native-v108-sized-cui` |

The parser source contains no 32-character game GUID. Query-string diagnostic
overrides `compatDButton=1` and `compatDSystem=1` remain available.

## Build And Validation

```sh
npm run compat:build
npm run compat:validate
```

Both commands use dependency-free Node.js scripts and run unchanged on Windows
and Linux. The generated browser bundle has no Node.js runtime dependency.

Validation covers:

- generated bundle freshness;
- generated bundle JavaScript syntax;
- absence of game GUIDs in the binary parser module;
- exact profile/capability resolution for all configured games, a wrong version,
  and an unknown GUID.

## Browser Regression

- `1569947` / version `364`: DSystem parsed 454 buttons and completed at byte 24,414,648; no browser errors.
- `1683317` / version `1544`: DSystem parsed 1,733 buttons and completed at byte 22,529,488; no browser errors.
- `1692665` / version `56`: DSystem parsed 508 buttons and completed at byte 944,054; no browser errors.
- `1692665` automatic resume returned to character creation, and built-in menu
  `10014` opened the four-field local name editor.
- Local platform API interception and free-time bypass remained active during the
  same run.

An extra non-profile regression of `1692785` / version `52` reproduced its
pre-existing `readUTFBytes` parser failure. The pre-refactor compatibility file
did not select a DSystem patch for that GUID, so the modularization intentionally
does not add one without a separate binary-evidence investigation.
