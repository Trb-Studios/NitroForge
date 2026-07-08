# Changelog

## 2.0.0 - "Nitro Forge" (2026-07)

Complete modernization, rebrand and reliability release.

### Rebrand
- **FPSBooster → Nitro Forge** everywhere: product name, window titles, package
  names, installer, data directory (`%LOCALAPPDATA%\NitroForge`), repo layout.
- Settings migrate automatically from the old FPSBooster folder on first run;
  legacy analytics/history data is cleaned up.

### Fixed
- **Multi-instance launch bug**: the packaged exe could open unbounded copies of
  itself (`py-cpuinfo` spawns child processes via `multiprocessing`; the frozen
  entry point lacked `multiprocessing.freeze_support()`, so every child re-ran
  the whole app). Fixed at the entry point *and* guarded by proper
  single-instance protection in the shell (second launch focuses the existing
  window).
- **Frontend did not compile**: five pages (Analytics, Bottleneck, Logs,
  Overlay, Resolution) were imported but never existed. All implemented.
- Game launching for launcher-managed titles (Steam DRM, Epic, Riot) no longer
  tries to run the raw exe and fail silently.

### Game library
- Launcher-aware detection & launching: Steam (`steam://rungameid`), Epic
  (`com.epicgames.launcher://`), Riot (Riot Client args), Ubisoft
  (`uplay://launch`), GOG (registry), Battle.net / EA / Xbox roots.
- Steam library parsed from `appmanifest_*.acf` - real names + appids.
- Box art: bundled catalog of the top 2,500 games (name → Steam appid), local
  Steam library-cache reuse, lazy CDN download with on-disk cache, and an
  "Unverified Game" placeholder when no art exists. Nothing blocks the UI.
- Search, platform filter, manual add/remove, per-game fullscreen-optimization
  toggle.

### New: crash & feedback reporting
- Python + UI crash handlers produce structured diagnostic reports (version,
  OS/hardware summary, stack trace, recent log tail) saved locally.
- Optional delivery to a **Discord webhook** and/or a **website API endpoint** -
  strictly opt-in, configured in Settings, with a "send test report" button.
- Friendly in-app crash screen with user feedback + send.
- In-app bug report / feedback form (Settings).

### UI
- Rebuilt around a consolidated 6-section layout (was 10 flat menus):
  Dashboard, Games, Boost, System, Insights, Settings.
- New dark theme with baby-blue accent; animated boot screen; skeleton loading
  states; spring animations throughout; lucide icon set.
- Code-split bundles so the boot-critical path stays small.

### Engine & packaging
- Sidecar exception hook wired into the crash reporter.
- Tauri shell: single-instance plugin, graceful sidecar shutdown (boosts always
  revert), release profile with LTO + strip.
- NSIS installer target; PyInstaller spec for the sidecar; `scripts/build.ps1`
  one-command release build; GitHub Actions CI.

### Removed
- Legacy CustomTkinter UI (`main.py`, `ui/`, `overlay/`) and its dependencies
  (customtkinter, matplotlib).
- Tracked build artifacts and `.pyc` files; proper `.gitignore` added.

## 1.x - FPSBooster
- Original CustomTkinter application.
