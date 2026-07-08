<div align="center">

# 🔥 Nitro Forge

**Forge more FPS out of the PC you already own.**

A game-focused Windows optimizer with a modern desktop UI: one-click *reversible*
Game Boost, a launcher-aware game library with box art, a real FPS overlay
(Intel PresentMon), hardware specs & bottleneck analysis, performance history,
and a full audit log of every change the app makes.

*Dark UI - baby-blue accent - built to feel like Spotify/Discord/Steam, not a 2009 tweak tool.*

</div>

---

## Architecture

Native-speed engine, web-speed UI, smallest possible shell:

```
nitro-forge/
├── desktop/          Desktop app
│   ├── src/          React 19 + TypeScript + Tailwind 4 + Motion (the UI)
│   └── src-tauri/    Tauri 2 (Rust) shell: window, single-instance,
│                     sidecar lifecycle, graceful shutdown
├── core/             Python system engine: booster, game scanner,
│   │                 hardware info, processes, power/services/registry,
│   │                 resolution, PresentMon wrapper, crash reporter
│   └── data/         Bundled game catalog (top 2,500 titles + Steam appids)
├── sidecar/          Local-only JSON API bridging the UI to the engine
│                     (127.0.0.1, ephemeral port, per-session auth token)
├── website/          Static marketing site (same dark/baby-blue theme)
├── docs/             Architecture, building, Discord integration, website
└── scripts/          Build & packaging scripts
```

**Why this stack?** Tauri gives a ~10 MB shell using the OS webview (Electron
ships a whole Chromium, ~150 MB+ and far more RAM). React+TS+Tailwind gives a
modern, animated, maintainable UI. The battle-tested Python engine does the
actual system work behind strict safety guards, and everything speaks over a
token-authenticated localhost API. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Features

| | |
|---|---|
| 🚀 **Game Boost** | Suspends allowlisted background apps, raises game priority, performance power plan, Game Mode, pauses Windows Update/Search/telemetry - every change reverted automatically (undo, game exit, app close, or crash backstop) |
| 🎮 **Game library** | Auto-detects Steam, Epic, Riot, GOG, Ubisoft, Battle.net, EA, Xbox installs; launches through each platform's own launcher (DRM/anti-cheat safe); box art with an "Unverified Game" fallback |
| 📊 **FPS overlay** | Real frame timings via Intel PresentMon (ETW) - no game injection |
| 🧠 **Insights** | CPU/GPU/RAM/FPS history, honest bottleneck analysis, audit log |
| 🛠 **Task manager** | See what steals resources from your game; suspend/reprioritize/kill with OS-critical processes protected |
| 🖥 **Display** | Resolution switching + per-game gaming resolution |
| 📨 **Crash reporting** | Local diagnostic reports, optional Discord webhook + website API delivery, in-app feedback (see [docs/DISCORD_INTEGRATION.md](docs/DISCORD_INTEGRATION.md)) |

## Safety design

* Every system change goes on an undo stack and is **reverted automatically**.
* Only small, visible **allowlists** can be suspended/paused. Nothing is enumerated-and-killed.
* **Antivirus / security software is hard-blocked in code** - no toggle can touch it.
* Every change is logged (old value → new value) in the app and `app.log`.
* No fake buttons: things desktop software cannot do are presented as guidance.

## Quick start (development)

```powershell
# 1. Python engine
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 2. Desktop app (needs Node 20+ and Rust)
cd desktop
npm install
npm run tauri dev
```

Run as Administrator for the full feature set (service pausing, PresentMon ETW).

## Building the installer

```powershell
scripts\build.ps1        # sidecar exe (PyInstaller) + Tauri NSIS installer
```

See [docs/BUILDING.md](docs/BUILDING.md) for details and prerequisites.

## Data locations

| What | Where |
|---|---|
| Settings | `%LOCALAPPDATA%\NitroForge\settings.json` |
| Performance history | `%LOCALAPPDATA%\NitroForge\history.sqlite3` |
| Logs | `%LOCALAPPDATA%\NitroForge\app.log` (rotating) |
| Crash reports | `%LOCALAPPDATA%\NitroForge\crashes\` |
| Cached box art | `%LOCALAPPDATA%\NitroForge\logos\` |

## Docs

* [Architecture](docs/ARCHITECTURE.md) - how the three layers fit together
* [Building](docs/BUILDING.md) - dev setup, release builds, CI
* [Discord integration](docs/DISCORD_INTEGRATION.md) - crash/bug/feedback reports into your server
* [Website](docs/WEBSITE.md) - deploying the marketing site
* [Changelog](CHANGELOG.md) - what changed in 2.0
* [Contributing](CONTRIBUTING.md)
