# Contributing to Nitro Forge

## Ground rules (read first)

Nitro Forge's value is that it is **safe and honest**. Any PR must respect the
safety contract in [core/config.py](core/config.py):

1. Only allowlisted processes/services may ever be suspended, stopped or
   reprioritized. Nothing may enumerate-and-kill.
2. Antivirus / security software is hard-blocked. No code path may weaken it.
3. Every system change must be pushed onto the Booster undo stack (or logged
   via `log_action`) so it is visible and reversible.
4. No fake features: if Windows/a desktop app genuinely can't do something,
   present guidance, not a placebo button.

## Dev setup

```powershell
py -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
cd desktop && npm install && npm run tauri dev
```

Prereqs: Python 3.11+, Node 20+, Rust (stable, MSVC toolchain).

## Layout

| Path | What lives here |
|---|---|
| `core/` | Python engine - all privileged system logic + guards |
| `sidecar/server.py` | Localhost JSON API consumed by the UI |
| `desktop/src/` | React UI (pages = sections, components = shared) |
| `desktop/src-tauri/` | Rust shell (keep it thin) |
| `website/` | Static site |

## Style

* Python: PEP 8, type hints, docstring at the top of each module explaining *why*.
* TypeScript: strict mode is on; no `any` unless unavoidable.
* Keep the sidecar dumb: privileged logic and guards belong in `core`.
* UI: use the shared components in `desktop/src/components/ui.tsx`; colors come
  from the tokens in `index.css` - never hardcode hex in pages.

## Before you open a PR

```powershell
py -m compileall core sidecar        # engine syntax
cd desktop && npm run build          # typecheck + bundle
cd src-tauri && cargo check          # shell
```

Manual smoke test: `npm run tauri dev`, boost on/off, launch a game, check the
Logs page shows the changes and the revert.
