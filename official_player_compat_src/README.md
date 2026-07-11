# Official Player Compatibility Sources

`official_player_compat.js` is a generated browser bundle. Edit the modules in
this directory and regenerate the bundle with:

```sh
npm run compat:build
```

Module responsibilities:

| Module | Responsibility |
| --- | --- |
| `00-core.js` | Shared helpers, patch registry, profile matching, and ordered installation. |
| `05-game-profiles.js` | GUID/version matching and declarative capability selection. |
| `10-built-in-menu.js` | Missing built-in menu implementations such as `10014`. |
| `15-game-index.js` | Capability-gated fallback from the proxy query game ID to an invalid runtime game index. |
| `20-platform-state.js` | Development entitlement and inventory state helpers. |
| `30-local-save.js` | Local save-mode selection and legacy payload normalization. |
| `40-platform-api.js` | Local API contracts, unlock emulation, and network-noise filtering. |
| `50-binary-parser.js` | Capability-based DButton, DSystem, and CUI parser patches. |
| `60-free-time.js` | Standalone free-time gate behavior. |
| `70-storage-trace.js` | Save/archive tracing and automatic/manual archive bridging. |
| `90-bootstrap.js` | Retry lifecycle for installing registered patches. |

Game GUIDs and versions belong only in `05-game-profiles.js`. Parser and runtime
modules must select behavior by capability name. New games should reuse an
existing capability before adding a new parser implementation.

`player_render_refresh.js` preserves the legacy forced-repaint behavior unless a
GUID/version profile explicitly selects another policy through
`player_render_refresh_policy.js`. A render policy must not be assigned to a game
until that game's scene, menu, and save-page regressions pass.

Run the source/bundle and syntax checks with:

```sh
npm run compat:validate
```
