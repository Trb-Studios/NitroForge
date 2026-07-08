// The always-on-top transparent FPS overlay window (separate WebView).
// Drag anywhere to move. Games in exclusive fullscreen bypass every desktop
// overlay - use borderless mode (explained in the FPS Overlay page).
import React, { useEffect, useState } from "react";
import ReactDOM from "react-dom/client";
import { api, initApi, type Live } from "./api";

const SIZES: Record<string, { fps: number; sub: number }> = {
  small: { fps: 22, sub: 11 },
  medium: { fps: 32, sub: 13 },
  large: { fps: 46, sub: 16 },
};

function Overlay() {
  const [live, setLive] = useState<Live | null>(null);
  const [size, setSize] = useState("medium");

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const l = await api<Live>("/live");
        if (alive) setLive(l);
      } catch {
        /* retry */
      }
      if (alive) setTimeout(tick, 500);
    };
    const settings = async () => {
      try {
        const s = await api<{ overlay_size: string }>("/settings");
        if (alive) setSize(s.overlay_size || "medium");
      } catch {
        /* retry */
      }
      if (alive) setTimeout(settings, 5000);
    };
    initApi().then(() => {
      tick();
      settings();
    });
    return () => {
      alive = false;
    };
  }, []);

  const sz = SIZES[size] ?? SIZES.medium;
  const fps = live?.fps.fps;
  return (
    <div
      data-tauri-drag-region
      style={{
        fontFamily: '"Segoe UI", system-ui, sans-serif',
        padding: "8px 12px",
        cursor: "move",
        width: "100vw",
        height: "100vh",
        boxSizing: "border-box",
      }}
    >
      <div
        data-tauri-drag-region
        style={{
          fontSize: sz.fps,
          fontWeight: 800,
          lineHeight: 1.05,
          color: fps ? "#39ff5f" : "#c3c2b7",
          textShadow: "0 0 8px rgba(0,0,0,.9), 0 1px 2px rgba(0,0,0,.9)",
          fontVariantNumeric: "tabular-nums",
        }}
      >
        {fps ? `${Math.round(fps)} FPS` : "-- FPS"}
      </div>
      <div
        data-tauri-drag-region
        style={{
          fontSize: sz.sub,
          color: "#c3c2b7",
          textShadow: "0 0 6px rgba(0,0,0,.9)",
          fontVariantNumeric: "tabular-nums",
        }}
      >
        {live?.fps.frametime_ms
          ? `${live.fps.frametime_ms.toFixed(1)} ms  ${live.fps.process ?? ""}`
          : live?.fps_running
            ? "waiting for frames..."
            : "PresentMon off"}
      </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Overlay />
  </React.StrictMode>,
);
