import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState, type JSX } from "react";
import { api, usePoll, type Live, type Meta } from "./api";
import BootScreen from "./components/BootScreen";
import Sidebar, { type PageId } from "./components/Sidebar";
import TitleBar from "./components/TitleBar";
import { EASE } from "./components/ui";
import Boost from "./pages/Boost";
import Dashboard from "./pages/Dashboard";
import Games from "./pages/Games";
import Insights from "./pages/Insights";
import Settings from "./pages/Settings";
import System from "./pages/System";

const PAGES: Record<PageId, (p: { live: Live | null; meta: Meta | null }) => JSX.Element> = {
  dashboard: Dashboard,
  games: Games,
  boost: Boost,
  system: System,
  insights: Insights,
  settings: Settings,
};

const MIN_BOOT_MS = 1400; // let the intro play; never flash-skip the boot

export default function App() {
  const [page, setPage] = useState<PageId>("dashboard");
  const [meta, setMeta] = useState<Meta | null>(null);
  const [bootDone, setBootDone] = useState(false);
  const [status, setStatus] = useState("Starting engine...");
  // 2s live poll keeps the UI responsive while roughly halving the app's own
  // idle CPU wakeups vs a 1s cadence (lighter footprint while gaming).
  const live = usePoll<Live>("/live", 2000);

  // Boot sequence: wait for the sidecar handshake (meta) + first live
  // sample, keep the intro on screen for at least MIN_BOOT_MS.
  useEffect(() => {
    const started = Date.now();
    let alive = true;
    (async () => {
      for (let attempt = 0; alive; attempt++) {
        try {
          const m = await api<Meta>("/meta");
          if (!alive) return;
          setMeta(m);
          setStatus(`Loading game catalog (${m.catalog_size.toLocaleString()} titles)...`);
          break;
        } catch {
          setStatus(
            attempt < 4 ? "Connecting to the Nitro Forge engine..." :
            "Still starting the engine (first run can take a moment)...",
          );
          await new Promise((r) => setTimeout(r, 700));
        }
      }
      const wait = Math.max(0, MIN_BOOT_MS - (Date.now() - started));
      setTimeout(() => alive && setBootDone(true), wait);
    })();
    return () => {
      alive = false;
    };
  }, []);

  const Page = PAGES[page];

  return (
    <div className="h-screen flex flex-col bg-bg text-ink overflow-hidden">
      <AnimatePresence>
        {!bootDone && (
          <motion.div
            key="boot"
            exit={{ opacity: 0, scale: 1.04, filter: "blur(8px)" }}
            transition={{ duration: 0.5, ease: EASE }}
            className="absolute inset-0 z-[90]"
          >
            <BootScreen status={status} />
          </motion.div>
        )}
      </AnimatePresence>

      <TitleBar />
      <div className="flex flex-1 min-h-0">
        <Sidebar page={page} onNav={setPage} live={live} meta={meta} />
        <main className="flex-1 min-w-0 overflow-y-auto">
          <AnimatePresence mode="wait">
            <motion.div
              key={page}
              initial={{ opacity: 0, y: 18, filter: "blur(6px)" }}
              animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
              exit={{ opacity: 0, y: -12, filter: "blur(6px)" }}
              transition={{ duration: 0.3, ease: EASE }}
              className="p-6 max-w-[1200px] mx-auto"
            >
              <Page live={live} meta={meta} />
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </div>
  );
}
