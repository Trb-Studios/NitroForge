# desktop/ - Nitro Forge desktop app

React 19 + TypeScript + Tailwind 4 + Motion UI inside a Tauri 2 (Rust) shell.

```
src/
  App.tsx            boot gating + navigation + page transitions
  api.ts             typed sidecar client (usePoll, logoUrl, types)
  components/        TitleBar, Sidebar, BootScreen, ErrorBoundary, ui.tsx
  pages/             Dashboard, Games, Boost, System, Insights, Settings
                     (+ the sub-pages the hubs compose)
  overlay-main.tsx   the transparent always-on-top FPS overlay window
src-tauri/           Rust shell: single-instance, sidecar spawn/shutdown
```

Dev: `npm install && npm run tauri dev` (spawns `sidecar/server.py` via `py`).

Design tokens live in `src/index.css` - dark only, baby-blue accent. Use the
shared components in `components/ui.tsx`; don't hardcode colors in pages.
