// Sidebar navigation: 6 consolidated sections (was 10 flat menus),
// spring-animated active pill, live status footer.
import { motion } from "motion/react";
import {
  Cpu,
  Gamepad2,
  LayoutDashboard,
  LineChart,
  Rocket,
  Settings,
  ShieldAlert,
} from "lucide-react";
import type { Live, Meta } from "../api";

export const NAV = [
  { id: "dashboard", label: "Dashboard", Icon: LayoutDashboard },
  { id: "games", label: "Games", Icon: Gamepad2 },
  { id: "boost", label: "Boost", Icon: Rocket },
  { id: "system", label: "System", Icon: Cpu },
  { id: "insights", label: "Insights", Icon: LineChart },
  { id: "settings", label: "Settings", Icon: Settings },
] as const;

export type PageId = (typeof NAV)[number]["id"];

export default function Sidebar({
  page,
  onNav,
  live,
  meta,
}: {
  page: PageId;
  onNav: (p: PageId) => void;
  live: Live | null;
  meta: Meta | null;
}) {
  return (
    <aside className="w-[210px] shrink-0 flex flex-col bg-panel border-r border-line/60 py-3">
      <nav className="flex-1 px-2.5 space-y-0.5 overflow-y-auto">
        {NAV.map(({ id, label, Icon }, i) => (
          <motion.button
            key={id}
            initial={{ opacity: 0, x: -16 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.05 + i * 0.045, duration: 0.35 }}
            onClick={() => onNav(id)}
            className={`relative w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-[13.5px] transition-colors cursor-pointer ${
              page === id ? "text-ink" : "text-mute hover:text-ink2"
            }`}
          >
            {page === id && (
              <motion.div
                layoutId="nav-pill"
                transition={{ type: "spring", stiffness: 480, damping: 38 }}
                className="absolute inset-0 rounded-xl bg-accent/[.14] shadow-[inset_0_0_0_1px_rgba(124,192,244,.35)]"
              />
            )}
            <Icon
              size={17}
              className="relative z-10 shrink-0"
              style={page === id ? { color: "var(--color-accent)" } : undefined}
            />
            <span className="relative z-10 font-medium">{label}</span>
          </motion.button>
        ))}
      </nav>

      <div className="px-4 pt-3 space-y-2 border-t border-line/60">
        {live?.boost.active && (
          <div className="flex items-center gap-2 text-[11.5px] text-accent2">
            <span className="w-2 h-2 rounded-full bg-accent animate-pulse-glow" />
            BOOST ACTIVE
            {live.boost.game ? ` - ${live.boost.game}` : ""}
          </div>
        )}
        {live && !live.admin && (
          <div className="flex items-center gap-2 text-[11.5px] text-warn">
            <ShieldAlert size={13} className="shrink-0" />
            Not running as admin
          </div>
        )}
        <div className="text-[10.5px] text-mute pb-1">
          {live
            ? `${live.net.type} - ${Math.max(live.net.down_mbps, 0).toFixed(1)} Mbps`
            : "connecting..."}
          {meta ? ` | v${meta.version}` : ""}
        </div>
      </div>
    </aside>
  );
}
