// Games library: Steam-style box-art grid, launcher-aware launching
// (steam:// / Epic / Riot / uplay://), search + platform filter, per-game
// options, and an "Unverified Game" placeholder when no art exists.
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useMemo, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import {
  FolderPlus,
  Gamepad2,
  Play,
  RefreshCw,
  Rocket,
  Search,
  ShieldQuestion,
  Trash2,
} from "lucide-react";
import { api, logoUrl, type GameInfo, type LaunchReply, type Live } from "../api";
import { Button, EASE, Toggle } from "../components/ui";

const SOURCE_COLORS: Record<string, string> = {
  Steam: "#7cc0f4",
  Epic: "#9d8ff2",
  GOG: "#d99a2b",
  Riot: "#e66767",
  "Battle.net": "#2fbf9a",
  Ubisoft: "#4cc25c",
  EA: "#f4b942",
  Xbox: "#35c26e",
  Manual: "#7d8b9c",
};

function initials(name: string) {
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
}

/** Box art with graceful fallback -> branded "Unverified Game" tile. */
function GameArt({ game }: { game: GameInfo }) {
  const [failed, setFailed] = useState(false);
  const color = SOURCE_COLORS[game.source] ?? "#7d8b9c";
  if (game.appid && !failed) {
    return (
      <img
        src={logoUrl(game.appid)}
        onError={() => setFailed(true)}
        loading="lazy"
        draggable={false}
        alt=""
        className="absolute inset-0 w-full h-full object-cover"
      />
    );
  }
  return (
    <div
      className="absolute inset-0 flex flex-col items-center justify-center gap-2"
      style={{ background: `linear-gradient(150deg, ${color}33, #0d1219 70%)` }}
    >
      <div
        className="w-14 h-14 rounded-2xl flex items-center justify-center font-bold text-[19px] text-ink"
        style={{ background: `linear-gradient(135deg, ${color}, ${color}44)` }}
      >
        {initials(game.name) || <Gamepad2 size={22} />}
      </div>
      <div className="flex items-center gap-1 text-[9.5px] font-semibold tracking-[0.14em] uppercase text-mute">
        <ShieldQuestion size={11} /> Unverified Game
      </div>
    </div>
  );
}

export default function Games(_: { live: Live | null }) {
  const [games, setGames] = useState<GameInfo[] | null>(null);
  const [scanning, setScanning] = useState(false);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("All");
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

  const sources = useMemo(
    () => ["All", ...Array.from(new Set((games ?? []).map((g) => g.source)))],
    [games],
  );

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (games ?? []).filter(
      (g) =>
        (filter === "All" || g.source === filter) &&
        (!q || g.name.toLowerCase().includes(q)),
    );
  }, [games, query, filter]);

  const key = (g: GameInfo) => g.source + g.name + g.exe;

  const setGameNote = (g: GameInfo, text: string, clearMs = 6000) => {
    setNote((n) => ({ ...n, [key(g)]: text }));
    if (clearMs) setTimeout(() => setNote((n) => ({ ...n, [key(g)]: "" })), clearMs);
  };

  const launch = async (g: GameInfo) => {
    setGameNote(g, "launching...", 0);
    try {
      const r = await api<LaunchReply>("/games/launch", g);
      setGameNote(
        g,
        r.ok
          ? r.method === "launcher"
            ? `handing off to ${g.source}...`
            : "launched"
          : (r.error ?? "launch failed"),
      );
    } catch (e) {
      setGameNote(g, String((e as Error).message));
    }
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

  const removeManual = async (g: GameInfo) => {
    await api("/games/remove", { exe: g.exe });
    load();
  };

  const toggleFso = async (g: GameInfo, v: boolean) => {
    await api("/games/fso", { exe: g.exe, disabled: v });
    setGames((gs) => gs?.map((x) => (x.exe === g.exe ? { ...x, fso_disabled: v } : x)) ?? null);
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-mute" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search library..."
            spellCheck={false}
            className="w-[220px] rounded-xl bg-card2 pl-9 pr-3 py-2 text-[13px] text-ink outline-none placeholder:text-mute focus:ring-1 focus:ring-accent"
          />
        </div>
        <div className="flex gap-1 flex-wrap">
          {sources.map((s) => (
            <button
              key={s}
              onClick={() => setFilter(s)}
              className={`px-3 py-1.5 rounded-lg text-[12px] font-medium transition-colors cursor-pointer ${
                filter === s
                  ? "bg-accent text-on-accent"
                  : "bg-card2 text-mute hover:text-ink2"
              }`}
            >
              {s}
            </button>
          ))}
        </div>
        <div className="ml-auto flex items-center gap-2">
          <Button kind="ghost" onClick={addManual}>
            <span className="flex items-center gap-2">
              <FolderPlus size={14} /> Add game
            </span>
          </Button>
          <Button onClick={() => load(true)} disabled={scanning}>
            <span className="flex items-center gap-2">
              <RefreshCw size={14} className={scanning ? "animate-spin" : ""} />
              {scanning ? "Scanning..." : "Rescan"}
            </span>
          </Button>
        </div>
      </div>

      <div className="text-[12px] text-mute -mt-2">
        {games
          ? `${shown.length} of ${games.length} games - Steam / Epic / Riot / GOG / Ubisoft / Battle.net / EA / Xbox`
          : "scanning your launchers..."}
      </div>

      {games === null && (
        <div className="grid grid-cols-3 xl:grid-cols-4 gap-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="rounded-2xl skeleton aspect-[3/4]" />
          ))}
        </div>
      )}

      <div className="grid grid-cols-3 xl:grid-cols-4 gap-4">
        <AnimatePresence>
          {shown.map((g, i) => {
            const color = SOURCE_COLORS[g.source] ?? "#7d8b9c";
            return (
              <motion.div
                key={key(g)}
                layout
                initial={{ opacity: 0, y: 18, scale: 0.97 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, scale: 0.96 }}
                transition={{ duration: 0.35, delay: Math.min(i * 0.04, 0.35), ease: EASE }}
                whileHover={{ y: -5 }}
                className="group relative rounded-2xl bg-card ring-hair overflow-hidden hover:shadow-[0_14px_40px_rgba(0,0,0,.5)] transition-shadow"
              >
                {/* box art */}
                <div className="relative aspect-[3/4]">
                  <GameArt game={g} />
                  <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/10 to-transparent" />
                  {/* hover launch */}
                  <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                    <motion.button
                      whileHover={{ scale: 1.06 }}
                      whileTap={{ scale: 0.94 }}
                      onClick={() => launch(g)}
                      className="w-14 h-14 rounded-full bg-accent text-on-accent flex items-center justify-center shadow-[0_0_30px_rgba(124,192,244,.55)] cursor-pointer"
                    >
                      <Play size={22} className="ml-1" />
                    </motion.button>
                  </div>
                  {/* platform badge */}
                  <div
                    className="absolute top-2.5 left-2.5 px-2 py-0.5 rounded-md text-[10px] font-bold tracking-wide"
                    style={{ background: `${color}e6`, color: "#06121d" }}
                  >
                    {g.source}
                  </div>
                  {g.launch_uri && (
                    <div className="absolute top-2.5 right-2.5 w-6 h-6 rounded-md bg-black/55 flex items-center justify-center"
                      title={`Launches through ${g.source} (DRM, anti-cheat and cloud saves handled by the launcher)`}>
                      <Rocket size={12} className="text-accent2" />
                    </div>
                  )}
                  {/* name + note */}
                  <div className="absolute bottom-0 inset-x-0 p-3">
                    <div className="text-[13.5px] font-semibold leading-tight drop-shadow" title={g.name}>
                      {g.name}
                    </div>
                    {note[key(g)] && (
                      <div className="text-[11px] text-accent2 mt-0.5">{note[key(g)]}</div>
                    )}
                  </div>
                </div>
                {/* footer actions */}
                <div className="flex items-center justify-between px-3 py-2.5">
                  <label
                    className="flex items-center gap-2 text-[10.5px] text-mute"
                    title="Disable Windows fullscreen optimizations for this game's exe"
                  >
                    <Toggle on={g.fso_disabled} onChange={(v) => toggleFso(g, v)} disabled={!g.exe} />
                    Disable FSO
                  </label>
                  {g.source === "Manual" ? (
                    <button
                      onClick={() => removeManual(g)}
                      className="text-mute hover:text-bad transition-colors cursor-pointer"
                      title="Remove from library"
                    >
                      <Trash2 size={14} />
                    </button>
                  ) : (
                    <span className="text-[10.5px] text-mute truncate max-w-[110px]" title={g.exe}>
                      {g.exe ? g.exe.split("\\").pop() : "launcher-managed"}
                    </span>
                  )}
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>

      {games?.length === 0 && (
        <div className="text-[13px] text-mute">
          Nothing found in Steam / Epic / Riot / GOG / Ubisoft / Battle.net / EA / Xbox.
          Use "Add game" to point at any .exe.
        </div>
      )}
    </div>
  );
}
