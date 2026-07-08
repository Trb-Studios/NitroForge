import { AnimatePresence, motion } from "motion/react";
import { useState, type JSX } from "react";
import { usePoll, type Live } from "./api";
import Sidebar, { type PageId } from "./components/Sidebar";
import TitleBar from "./components/TitleBar";
import { EASE } from "./components/ui";
import Analytics from "./pages/Analytics";
import Booster from "./pages/Booster";
import Bottleneck from "./pages/Bottleneck";
import Dashboard from "./pages/Dashboard";
import Games from "./pages/Games";
import Logs from "./pages/Logs";
import OverlayPage from "./pages/OverlayPage";
import Processes from "./pages/Processes";
import Resolution from "./pages/Resolution";
import Specs from "./pages/Specs";

const PAGES: Record<PageId, (p: { live: Live | null }) => JSX.Element> = {
  dashboard: Dashboard,
  booster: Booster,
  games: Games,
  processes: Processes,
  specs: Specs,
  resolution: Resolution,
  overlay: OverlayPage,
  analytics: Analytics,
  bottleneck: Bottleneck,
  logs: Logs,
};

export default function App() {
  const [page, setPage] = useState<PageId>("dashboard");
  const live = usePoll<Live>("/live", 1500);
  const Page = PAGES[page];

  return (
    <div className="h-screen flex flex-col bg-bg text-ink overflow-hidden">
      <TitleBar />
      <div className="flex flex-1 min-h-0">
        <Sidebar page={page} onNav={setPage} live={live} />
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
              <Page live={live} />
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </div>
  );
}
