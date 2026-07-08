# Building Nitro Forge

## Prerequisites

| Tool | Version | Used for |
|---|---|---|
| Python | 3.11+ | engine + sidecar |
| Node.js | 20+ | UI build |
| Rust (MSVC) | stable | Tauri shell |
| PyInstaller | 6.10+ | freezing the sidecar (`pip install pyinstaller`) |

## Development

```powershell
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

cd desktop
npm install
npm run tauri dev     # starts Vite + the shell; shell runs sidecar via `py`
```

## Release build (one command)

```powershell
scripts\build.ps1
```

What it does:

1. **Sidecar** - PyInstaller (`sidecar.spec`) → `dist/nitro-forge-sidecar.exe`
   (one file, windowed, game catalog bundled).
   The spec keeps `multiprocessing.freeze_support()` intact - removing it
   brings back the "app opens hundreds of times" bug.
2. **UI** - `npm run build` (tsc typecheck + Vite production bundle).
3. **Shell + installer** - `npm run tauri build` → NSIS installer under
   `desktop/src-tauri/target/release/bundle/nsis/`.
4. Copies the sidecar exe next to the shell exe so the installer picks it up.

Outputs:

* `Nitro Forge_2.0.0_x64-setup.exe` - the installer users download
* `desktop/src-tauri/target/release/nitro-forge.exe` - the bare app exe

## Verifying a build

1. Run the installer, launch Nitro Forge.
2. Launch it **again** - the existing window must focus instead of opening a
   second instance.
3. Boost on → check Task Manager (services paused if admin) → Boost off.
4. Launch a Steam game from the library - Steam should start it.
5. Kill the app while boosted → relaunch → system must be back to normal
   (check Insights → Logs).

## CI

`.github/workflows/ci.yml` runs on every push/PR:

* Python: byte-compile the engine + sidecar.
* UI: `npm run build` (tsc + vite).
* Shell: `cargo check`.

Release packaging runs on tags (`v*`) and uploads the NSIS installer as an
artifact - wire it to a GitHub Release when ready.
