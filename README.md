# FPSBooster

A game-focused PC optimizer for Windows with a modern dark-mode GUI:
one-click reversible **Game Booster**, live **FPS overlay** (via Intel
PresentMon), a better **task manager**, hardware **specs** and
**bottleneck** analysis, display **resolution** switching, a **games
library** launcher, performance **history charts**, and a full audit
**log** of every change the app makes.

Built with Python 3.11+ / CustomTkinter / psutil / matplotlib / sqlite3.

## Install

```powershell
# from the project folder
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
py main.py
```

## Why run as Administrator?

The app works without elevation, but these features need admin rights and
are skipped (with a log entry) otherwise:

* **Pausing services** during a boost (Windows Update, Windows Search,
  SysMain, Downloaded Maps, Delivery Optimization, Telemetry) — `sc stop`
  requires admin. They are always restarted on revert.
* **PresentMon FPS capture** — frame timing comes from Windows ETW, which
  requires elevation.
* Changing priority/affinity of processes you don't own.

Use the **"Restart as Administrator"** button in the header, or right-click
your shortcut → *Run as administrator*.

## FPS overlay setup (PresentMon)

Real FPS measurement requires frame-timing data. Instead of injecting code
into games (cheat-tool territory, and out of scope for Python), FPSBooster
shells out to **Intel PresentMon** — the free, digitally signed, open-source
tool that industry overlays are built on.

1. Download `PresentMon-x.x.x-x64.exe` from
   <https://github.com/GameTechDev/PresentMon/releases>.
2. Put it anywhere (e.g. `C:\Tools\PresentMon.exe`).
3. In the **FPS Overlay** tab, browse to the exe once. Done.

Both PresentMon 1.x and 2.x are supported. Note: games in *exclusive
fullscreen* bypass all desktop overlays — use borderless/windowed mode.

## Safety design (what this app will and won't do)

* Every Booster change is recorded on an undo stack and **reverted
  automatically** when the boosted game exits, when you click Undo, when
  the app closes, and via an `atexit` backstop if it crashes.
* Only small, visible **allowlists** can ever be suspended (background
  apps) or paused (services). Nothing is enumerated-and-killed.
* **Antivirus / security software is hard-blocked in code** — there is no
  toggle anywhere that stops, pauses, or weakens Defender or any AV/security
  service. Entries that look like security software are refused even if you
  add them to the allowlist yourself.
* Every system change is written to the **Logs** tab and `app.log`
  (old value → new value), so you always have an audit trail.
* Honesty over marketing: things a desktop app genuinely cannot do
  (packet-level QoS, forcing laptop discrete-GPU mode, changing in-game
  render settings, "clearing" standby RAM without a dedicated tool) are
  presented as guidance, not fake buttons.

## Data locations

| What | Where |
|---|---|
| Settings | `%LOCALAPPDATA%\FPSBooster\settings.json` |
| Performance history | `%LOCALAPPDATA%\FPSBooster\history.sqlite3` |
| Log file | `%LOCALAPPDATA%\FPSBooster\app.log` (rotating) |

## Project layout

```
main.py              entry point, window + tab shell, sampler wiring
core/                config/allowlists, logger, sqlite, hardware info,
                     processes, power/services/registry, resolution,
                     network, game scanner, PresentMon wrapper, booster,
                     bottleneck rules
ui/                  theme + one module per tab
overlay/             the always-on-top transparent FPS window
```

## Packaging to a single .exe (later)

The project is PyInstaller-ready:

```powershell
pip install pyinstaller
pyinstaller --onefile --windowed --name FPSBooster main.py
```

(`py-cpuinfo` uses multiprocessing — keep the provided `main()` guard.)
