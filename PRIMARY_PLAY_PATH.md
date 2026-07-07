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

Implementation files:

- `official_player_proxy.html`
- `official_player_proxy.py`
- `official_player_compat.js`
- `scripts/serve-play.ps1`
- `scripts/serve-official-proxy.ps1`

Regression validation:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-official-proxy-pages.ps1
```

The validation script enters the official proxy path, captures the main management page, key second-level pages, menu, and save/load UI, then writes screenshots plus `summary.json` under `C:\tmp\official_proxy_main_pages` by default.

Legacy/debug path:

- `h5_runner_experiment.html`

Use the legacy runner only for parser diagnostics or side-by-side debugging. UI parity and save/load work should be developed against the official proxy path.
