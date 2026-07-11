# Primary Local Play Path

The main implementation is now the official 66RPG H5 player with a local resource/API proxy.

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\serve-play.ps1
```

Play:

```text
http://127.0.0.1:8766/
```

Direct player URL:

```text
http://127.0.0.1:8766/official_player_proxy.html
```

Platform unlock is the default MVP play mode. It models the product rule that the user pays once on the platform and does not see in-game purchases:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\serve-play.ps1
```

```text
http://127.0.0.1:8766/official_player_proxy.html
```

This mode only affects the local proxy. It returns local stub balances, HP, buy/unlock success responses, cumulative flower/activity state, welfare award responses, and a local purchased-item inventory so paid branches can be played after the external platform entitlement is granted.

Comparison mode can be started explicitly when needed:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\serve-play.ps1 -NoPlatformUnlock
```

```text
http://127.0.0.1:8766/official_player_proxy.html?platformUnlock=0
```

Implementation files:

- `official_player_proxy.html`
- `official_player_proxy.py`
- `official_player_compat_src/` (canonical compatibility modules and game profiles)
- `official_player_compat.js` (generated single-file browser bundle)
- `scripts/build-official-player-compat.js`
- `scripts/validate-official-player-compat.js`
- `scripts/serve-play.ps1`
- `scripts/serve-official-proxy.ps1`

Regenerate and validate the compatibility bundle after changing a module or
game profile:

```sh
npm run compat:build
npm run compat:validate
```

Game GUID/version matching belongs in
`official_player_compat_src/05-game-profiles.js`. Parser and runtime modules
select behavior by capability name and must not embed game identifiers.

Regression validation:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-official-proxy-pages.ps1
```

The validation script enters the official proxy path, captures the main management page, key second-level pages, menu, and save/load UI, then writes screenshots plus `summary.json` under `C:\tmp\official_proxy_main_pages` by default.
