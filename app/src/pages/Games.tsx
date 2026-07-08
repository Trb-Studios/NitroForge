// Games library: animated card grid, direct launch, per-game FSO toggle.
import { motion } from "motion/react";
import { useEffect, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { FolderPlus, Play, RefreshCw } from "lucide-react";
import { api, type GameInfo, type Live } from "../api";
import { Button, EASE, Toggle } from "../components/ui";

const SOURCE_COLORS: Record<string, string> = {
  Steam: "#3987e5",
  Epic: "#9085e9",
  GOG: "#c98500",
  Riot: "#e66767",
  "Battle.net": "#199e70",
  Xbox: "#0ca30c",
  Manual: "#898781",
};

function initials(name: string) {
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
}

export default function Games(_: { live: Live | null }) {
  const [games, setGames] = useState<GameInfo[] | null>(null);
  const [scanning, setScanning] = useState(false);
  const [note, setNote] = useState<Record<string, string>>({});

  const load = async (rescan = false) => {
    setScanning(true);
    try {
      const r = await api<{ games: GameInfo[] }>(`/games${rescan ? "?rescan=1" : ""}`);
      setGames(r.games);
    } finally {
      setScanning(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const launch = async (g: GameInfo) => {
    setNote((n) => ({ ...n, [g.exe]: "launching..." }));
    const r = await api<{ ok: boolean; error?: string }>("/games/launch", g);
    setNote((n) => ({
      ...n,
      [g.exe]: r.ok
        ? "launched"
        : (r.error ?? "failed - if it needs its launcher (Steam DRM etc.), start it there"),
    }));
    setTimeout(() => setNote((n) => ({ ...n, [g.exe]: "" })), 6000);
  };

  const addManual = async () => {
    const path = await open({
      title: "Pick the game's .exe",
      filters: [{ name: "Executable", extensions: ["exe"] }],
    });
    if (typeof path === "string") {
      await api("/games/add", { exe: path });
      load();
    }
  };

  const toggleFso = async (g: GameInfo, v: boolean) => {
    await api("/games/fso", { exe: g.exe, disabled: v });
    setGames((gs) => gs?.map((x) => (x.exe === g.exe ? { ...x, fso_disabled: v } : x)) ?? null);
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <Button onClick={() => load(true)} disabled={scanning}>
          <span className="flex items-center gap-2">
            <RefreshCw size={14} className={scanning ? "animate-spin" : ""} />
            {scanning ? "Scanning..." : "Rescan"}
          </span>
        </Button>
        <Button kind="ghost" onClick={addManual}>
          <span className="flex items-center gap-2">
            <FolderPlus size={14} /> Add game manually
          </span>
        </Button>
        <span className="text-[12.5px] text-mute">
          {games ? `${games.length} game(s)` : "scanning Steam / Epic / GOG / Riot / Xbox..."}
        </span>
      </div>

      <div className="grid grid-cols-2 xl:grid-cols-3 gap-4">
        {(games ?? []).map((g, i) => {
          const color = SOURCE_COLORS[g.source] ?? "#898781";
          return (
            <motion.div
              key={g.source + g.exe + g.name}
              initial={{ opacity: 0, y: 18 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: Math.min(i * 0.05, 0.4), ease: EASE }}
              whileHover={{ y: -4 }}
              className="group rounded-2xl bg-card ring-hair p-4 flex flex-col gap-3 hover:shadow-[0_12px_36px_rgba(0,0,0,.45)] transition-shadow"
            >
              <div className="flex items-center gap-3">
                <div
                  className="w-11 h-11 rounded-xl flex items-center justify-center font-bold text-[15px] text-white shrink-0"
                  style={{ background: `linear-gradient(135deg, ${color}, ${color}55)` }}
                >
                  {initials(g.name)}
                </div>
                <div className="min-w-0">
                  <div className="text-[14px] font-semibold truncate" title={g.name}>
                    {g.name}
                  </div>
                  <div className="text-[11px]" style={{ color }}>
                    {g.source}
                  </div>
                </div>
              </div>
              <div className="text-[11px] text-mute truncate" title={g.exe}>
                {g.exe || "no exe matched - add manually"}
              </div>
              <div className="flex items-center justify-between mt-auto">
                <label className="flex items-center gap-2 text-[11px] text-mute">
                  <Toggle on={g.fso_disabled} onChange={(v) => toggleFso(g, v)} />
                  Disable fullscreen opt.
                </label>
                <Button onClick={() => launch(g)} disabled={!g.exe} className="!py-1.5">
                  <span className="flex items-center gap-1.5">
                    <Play size={13} /> Launch
                  </span>
                </Button>
              </div>
              {note[g.exe] && <div className="text-[11px] text-accent2">{note[g.exe]}</div>}
            </motion.div>
          );
        })}
      </div>
      {games?.length === 0 && (
        <div className="text-[13px] text-mute">
          Nothing found in the common launcher folders. Use "Add game manually" to point at any .exe.
        </div>
      )}
    </div>
  );
}
