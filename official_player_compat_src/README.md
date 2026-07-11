# Official Player Compatibility Sources

`official_player_compat.js` is a generated browser bundle. Edit the modules in
this directory and regenerate the bundle with:

```powershell
.\scripts\build-official-player-compat.ps1
```

Module responsibilities:

| Module | Responsibility |
| --- | --- |
| `00-core.js` | Shared helpers, patch registry, profile matching, and ordered installation. |
| `05-game-profiles.js` | GUID/version matching and declarative capability selection. |
| `10-built-in-menu.js` | Missing built-in menu implementations such as `10014`. |
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

Run the source/bundle and syntax checks with:

```powershell
.\scripts\validate-official-player-compat.ps1
```
