# Nitro Forge Architecture

## The three layers

```
┌────────────────────────────────────────────────────────┐
│ Desktop Interface  -  desktop/src  (React + TS)        │
│   6 sections, animations, boot screen, error boundary  │
└──────────────▲─────────────────────────────────────────┘
               │ fetch http://127.0.0.1:<port>/api/*  (X-NF-Token)
┌──────────────┴─────────────────────────────────────────┐
│ Sidecar API  -  sidecar/server.py  (stdlib http.server)│
│   routing, CORS allowlist, token auth, logo serving    │
└──────────────▲─────────────────────────────────────────┘
               │ plain function calls
┌──────────────┴─────────────────────────────────────────┐
│ Core Engine  -  core/  (Python)                        │
│   booster (undo stack) - game_scanner - game_catalog   │
│   system_info - process/power/resolution/network utils │
│   fps_monitor (PresentMon) - db (SQLite) - logger      │
│   crash_reporter - config (settings + safety lists)    │
└────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────┐
│ Shell  -  desktop/src-tauri  (Rust / Tauri 2)          │
│   single-instance, window mgmt, spawns the sidecar,    │
│   passes port+token to the UI, kills it gracefully     │
└────────────────────────────────────────────────────────┘
```

## Technology decisions

| Choice | Why | Alternatives considered |
|---|---|---|
| **Tauri 2** shell | ~10 MB exe, OS webview, low RAM, Rust safety | Electron (150 MB+, whole Chromium per app) |
| **React 19 + TypeScript + Vite + Tailwind 4 + Motion** | fast dev, strict types, tokenized theming, spring animations | Qt/QML (heavier dev loop), plain JS (unmaintainable at this size) |
| **Python engine kept** | the system-control code (guards, undo stack, WMI/ETW handling) is the hardest-won part of the codebase; rewriting it in C++/Rust adds risk for zero user-visible gain. PyInstaller freezes it to one exe. | full C++ rewrite (planned candidate for hot paths later - the API boundary makes swapping the engine possible without touching the UI) |
| **SQLite** history | zero-config, indexed by timestamp, pruned to 30 days | flat files (no querying), Postgres (absurd for desktop) |
| **stdlib `http.server` sidecar** | zero dependencies to freeze, ~400 lines, threading model fits polling | FastAPI (drags uvicorn/pydantic into the frozen exe) |
| **Discord webhooks** for reports | no bot hosting, no account access, user pastes one URL | Discord bot (needs a server + token management) |

## Security model

* Sidecar binds `127.0.0.1` on an **ephemeral port**; the port is only known to
  the shell (reads it from stdout) and the UI (via Tauri `invoke`).
* Every request must present the per-session 40-char token (`X-NF-Token`
  header; `?t=` query param for `<img>` logo requests, appid strictly numeric).
* CORS is answered only for the app's own origins, so a random website cannot
  drive the API from a browser.
* The settings API has an explicit **writable-keys allowlist**.
* All privileged logic and safety guards live in `core`, not in the API layer.

## Data flow examples

**Boost**: UI `POST /booster/apply` → `Booster.apply()` applies enabled tweaks,
pushing `(description, revert_fn)` per change onto an undo stack → UI polls
`/live` and renders `boost.changes`. Revert pops the stack LIFO; an `atexit`
hook is the crash backstop.

**Launch a game**: UI posts the full game record → `game_scanner.launch()`
prefers the platform URI (`steam://rungameid/<id>`, Epic, `uplay://`, Riot
client args) and falls back to the exe → if boost-on-launch is enabled, a
watcher waits for the game process to appear, attaches priority/affinity,
and auto-reverts when it exits.

**Box art**: `<img src="/api/logo/<appid>?t=token">` → disk cache → Steam's
local `librarycache` → lazy CDN download (serialized). Misses render the
"Unverified Game" placeholder client-side. The 2,500-title catalog
(`core/data/game_catalog.json`, ~115 KB) maps names → appids for non-Steam
stores; it is loaded once and never blocks scans.

**Crash**: any unhandled Python exception (or UI error boundary catch) →
`crash_reporter.build_report()` (version, OS, hardware summary, stack, log
tail) → saved to `crashes/` → optionally POSTed to the configured Discord
webhook / website endpoint (rate-limited, opt-in).

## Performance notes

* `/live` is the only hot endpoint (1.5 s poll); everything expensive behind it
  is cached (network type 30 s, games list until rescan).
* History sampler writes one row / 3 s; DB pruned to 30 days on start.
* Frontend: manual chunks split React / charts / motion so first paint doesn't
  parse recharts; box art is `loading="lazy"`; lists are capped.
* Release Rust profile: LTO, one codegen unit, stripped symbols.
