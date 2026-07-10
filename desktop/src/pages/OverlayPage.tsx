// FPS overlay control: PresentMon setup, capture start/stop, overlay
// window visibility / corner / size.
import { useEffect, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { openUrl } from "@tauri-apps/plugin-opener";
import { WebviewWindow } from "@tauri-apps/api/webviewWindow";
import { PhysicalPosition, primaryMonitor } from "@tauri-apps/api/window";
import { Crosshair, Download, FolderOpen, Lock, Move, Play, Square } from "lucide-react";
import { api, type AppSettings, type Live } from "../api";
import { Button, Card, Segmented, SectionTitle, TextInput, Toggle } from "../components/ui";

const CORNERS = ["top-left", "top-right", "bottom-left", "bottom-right"];

/** Click-through when locked, so the overlay never moves or steals clicks
 *  mid-game; interactive (draggable) when unlocked. */
async function setOverlayLocked(locked: boolean) {
  const overlay = await WebviewWindow.getByLabel("overlay");
  if (overlay) await overlay.setIgnoreCursorEvents(locked);
}

async function positionOverlay(corner: string) {
  const overlay = await WebviewWindow.getByLabel("overlay");
  const mon = await primaryMonitor();
  if (!overlay || !mon) return;
  const size = await overlay.outerSize();
  const pad = 24;
  const x = corner.includes("right") ? mon.size.width - size.width - pad : pad;
  const y = corner.includes("bottom") ? mon.size.height - size.height - pad : pad;
  await overlay.setPosition(new PhysicalPosition(mon.position.x + x, mon.position.y + y));
}

export default function OverlayPage({ live }: { live: Live | null }) {
  const [pmPath, setPmPath] = useState("");
  const [target, setTarget] = useState("");
  const [corner, setCorner] = useState("top-left");
  const [size, setSize] = useState("medium");
  const [visible, setVisible] = useState(false);
  const [locked, setLocked] = useState(true);
  const [autoTarget, setAutoTarget] = useState(true);
  const [err, setErr] = useState("");

  useEffect(() => {
    api<AppSettings>("/settings").then((s) => {
      setPmPath(s.presentmon_path || "");
      setCorner(s.overlay_corner || "top-left");
      setSize(s.overlay_size || "medium");
      setAutoTarget(s.fps_auto_target !== false);
      setLocked(s.overlay_locked !== false);
    }).catch(() => {});
    WebviewWindow.getByLabel("overlay").then((w) => w?.isVisible().then(setVisible));
  }, []);

  const applyLock = async (v: boolean) => {
    setLocked(v);
    await setOverlayLocked(v);
    await api("/settings", { key: "overlay_locked", value: v });
  };

  const pickPresentMon = async () => {
    const path = await open({
      title: "Locate PresentMon-*.exe",
      filters: [{ name: "Executable", extensions: ["exe"] }],
    });
    if (typeof path === "string") {
      const r = await api<{ ok: boolean; error?: string }>("/settings", {
        key: "presentmon_path",
        value: path,
      });
      if (r.ok) setPmPath(path);
      else setErr(r.error ?? "invalid path");
    }
  };

  const startCapture = async () => {
    setErr("");
    const r = await api<{ ok: boolean; error?: string | null }>("/fps/start", {
      process: target.trim() || undefined,
    });
    if (!r.ok) setErr(r.error || "could not start capture");
  };

  const stopCapture = () => api("/fps/stop", {});

  const toggleOverlay = async () => {
    const overlay = await WebviewWindow.getByLabel("overlay");
    if (!overlay) return;
    if (visible) {
      await overlay.hide();
      setVisible(false);
    } else {
      await positionOverlay(corner);
      await overlay.show();
      await setOverlayLocked(locked);   // apply click-through state on show
      setVisible(true);
    }
  };

  const running = live?.fps_running ?? false;

  return (
    <div className="space-y-5">
      <Card className="flex items-center gap-5 flex-wrap">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${running ? "bg-ok/15" : "bg-card2"}`}>
            <Crosshair size={19} className={running ? "text-ok" : "text-mute"} />
          </div>
          <div>
            <div className="text-[14px] font-semibold">
              {running ? "Capture running" : "Capture stopped"}
            </div>
            <div className="text-[12px] text-mute">
              {live?.fps.fps
                ? `${Math.round(live.fps.fps)} FPS - ${live.fps.frametime_ms?.toFixed(1)} ms (${live.fps.process ?? "auto"})`
                : running
                  ? "waiting for frames (game must be borderless/windowed)"
                  : "PresentMon captures real frame timings via Windows ETW"}
            </div>
          </div>
        </div>
        <div className="ml-auto flex items-center gap-2">
          {running ? (
            <Button kind="danger" onClick={stopCapture}>
              <span className="flex items-center gap-2"><Square size={13} /> Stop</span>
            </Button>
          ) : (
            <Button onClick={startCapture} disabled={!pmPath}>
              <span className="flex items-center gap-2"><Play size={13} /> Start capture</span>
            </Button>
          )}
          <Button kind="ghost" onClick={toggleOverlay}>
            {visible ? "Hide overlay window" : "Show overlay window"}
          </Button>
        </div>
        {err && <div className="w-full text-[12px] text-warn">{err}</div>}
      </Card>

      <div className="grid grid-cols-2 gap-5">
        <Card delay={0.05}>
          <SectionTitle>PresentMon (one-time setup)</SectionTitle>
          <div className="text-[12.5px] text-ink2 leading-relaxed mb-3">
            Real FPS needs frame-timing data. Nitro Forge uses Intel's free,
            signed <b>PresentMon</b> instead of injecting into games (which
            anti-cheat hates). Download it once, then point to the exe.
          </div>
          <div className="flex items-center gap-2 mb-2">
            <Button
              kind="ghost"
              onClick={() => openUrl("https://github.com/GameTechDev/PresentMon/releases")}
            >
              <span className="flex items-center gap-2"><Download size={14} /> Get PresentMon</span>
            </Button>
            <Button kind="ghost" onClick={pickPresentMon}>
              <span className="flex items-center gap-2"><FolderOpen size={14} /> Locate exe...</span>
            </Button>
          </div>
          <div className="text-[11.5px] text-mute truncate" title={pmPath}>
            {pmPath || "not configured yet"}
          </div>
          <div className="mt-4">
            <div className="text-[12px] text-mute mb-1.5">
              Target process (optional - auto-detects the busiest game if empty)
            </div>
            <TextInput value={target} onChange={setTarget} placeholder="e.g. cs2.exe" />
          </div>
        </Card>

        <Card delay={0.09}>
          <SectionTitle>Overlay window</SectionTitle>
          <div className="space-y-4">
            <div>
              <div className="text-[12px] text-mute mb-1.5">Corner</div>
              <Segmented
                id="corner"
                options={CORNERS}
                value={corner}
                onChange={async (v) => {
                  setCorner(v);
                  await api("/settings", { key: "overlay_corner", value: v });
                  if (visible) await positionOverlay(v);
                }}
              />
            </div>
            <div>
              <div className="text-[12px] text-mute mb-1.5">Size</div>
              <Segmented
                id="size"
                options={["small", "medium", "large"]}
                value={size}
                onChange={async (v) => {
                  setSize(v);
                  await api("/settings", { key: "overlay_size", value: v });
                }}
              />
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                {locked ? <Lock size={14} className="text-ok" /> : <Move size={14} className="text-warn" />}
                <div>
                  <div className="text-[13px] font-medium">
                    {locked ? "Locked (click-through)" : "Move mode"}
                  </div>
                  <div className="text-[11px] text-mute">
                    {locked
                      ? "Won't move or catch clicks while you play"
                      : "Drag the overlay to reposition, then lock it"}
                  </div>
                </div>
              </div>
              <Button kind="ghost" onClick={() => applyLock(!locked)}>
                {locked ? "Move overlay" : "Lock overlay"}
              </Button>
            </div>
            <div className="flex items-center justify-between">
              <div>
                <div className="text-[13px] font-medium">Auto-follow foreground game</div>
                <div className="text-[11px] text-mute">
                  Points the counter at whatever game you tab into
                </div>
              </div>
              <Toggle
                on={autoTarget}
                onChange={async (v) => {
                  setAutoTarget(v);
                  await api("/settings", { key: "fps_auto_target", value: v });
                }}
              />
            </div>
            <div className="text-[11.5px] text-mute leading-relaxed">
              Games in <b>exclusive fullscreen</b> bypass every desktop overlay -
              use borderless/windowed mode.
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
