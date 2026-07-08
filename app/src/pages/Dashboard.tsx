// Dashboard: live gauges, rolling utilization chart, one-click boost hero.
import { motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Rocket, Undo2, Wifi, Zap } from "lucide-react";
import { api, type Live } from "../api";
import Gauge from "../components/Gauge";
import { Button, Card, CountUp, SectionTitle } from "../components/ui";

interface Point {
  t: number;
  cpu: number;
  ram: number;
  gpu: number | null;
}

export default function Dashboard({ live }: { live: Live | null }) {
  const [history, setHistory] = useState<Point[]>([]);
  const [busy, setBusy] = useState(false);
  const lastTs = useRef(0);

  useEffect(() => {
    if (!live) return;
    const now = Date.now();
    if (now - lastTs.current < 1200) return;
    lastTs.current = now;
    setHistory((h) =>
      [...h, { t: now, cpu: live.cpu, ram: live.ram.percent, gpu: live.gpu.load }].slice(-120),
    );
  }, [live]);

  const toggleBoost = async () => {
    if (!live || busy) return;
    setBusy(true);
    try {
      await api(live.boost.active ? "/booster/revert" : "/booster/apply", {});
    } finally {
      setBusy(false);
    }
  };

  const active = live?.boost.active ?? false;

  return (
    <div className="space-y-5">
      <Card className="flex items-center justify-around py-6">
        <Gauge value={live?.cpu ?? null} label="CPU" color="var(--color-cpu)" />
        <Gauge
          value={live?.ram.percent ?? null}
          label="RAM"
          color="var(--color-ram)"
          display={
            live ? `${live.ram.used_gb.toFixed(1)} / ${live.ram.total_gb.toFixed(0)} GB` : undefined
          }
        />
        <Gauge
          value={live?.gpu.load ?? null}
          label="GPU"
          color="var(--color-gpu)"
          display={live?.gpu.temp != null ? `${live.gpu.temp.toFixed(0)} C` : undefined}
        />
        <Gauge
          value={live?.fps.fps ?? null}
          label="FPS"
          color="#2ea043"
          suffix=""
          max={240}
          display={
            live?.fps.frametime_ms != null
              ? `${live.fps.frametime_ms.toFixed(1)} ms`
              : live?.fps_running
                ? "waiting..."
                : "overlay off"
          }
        />
      </Card>

      <div className="grid grid-cols-[1.6fr_1fr] gap-5">
        <Card delay={0.06}>
          <SectionTitle>Utilization - last 3 minutes</SectionTitle>
          <div className="h-[210px] -mx-2">
            <ResponsiveContainer>
              <AreaChart data={history} margin={{ top: 4, right: 8, left: -18, bottom: 0 }}>
                <defs>
                  {[
                    ["cpu", "var(--color-cpu)"],
                    ["ram", "var(--color-ram)"],
                    ["gpu", "var(--color-gpu)"],
                  ].map(([k, c]) => (
                    <linearGradient key={k} id={`g-${k}`} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={c} stopOpacity={0.28} />
                      <stop offset="100%" stopColor={c} stopOpacity={0} />
                    </linearGradient>
                  ))}
                </defs>
                <CartesianGrid stroke="var(--color-line)" strokeWidth={0.6} vertical={false} />
                <XAxis dataKey="t" hide />
                <YAxis
                  domain={[0, 100]}
                  tick={{ fill: "var(--color-mute)", fontSize: 10 }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  contentStyle={{
                    background: "var(--color-card2)",
                    border: "1px solid var(--color-line)",
                    borderRadius: 12,
                    fontSize: 12,
                  }}
                  labelFormatter={() => ""}
                  formatter={(v: number, name: string) => [`${v?.toFixed(0)}%`, name.toUpperCase()]}
                />
                <Area type="monotone" dataKey="cpu" stroke="var(--color-cpu)" strokeWidth={1.8} fill="url(#g-cpu)" isAnimationActive={false} />
                <Area type="monotone" dataKey="ram" stroke="var(--color-ram)" strokeWidth={1.8} fill="url(#g-ram)" isAnimationActive={false} />
                <Area type="monotone" dataKey="gpu" stroke="var(--color-gpu)" strokeWidth={1.8} fill="url(#g-gpu)" isAnimationActive={false} connectNulls={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <div className="flex gap-4 mt-1 text-[11px] text-ink2">
            {[
              ["CPU", "var(--color-cpu)"],
              ["RAM", "var(--color-ram)"],
              ["GPU", "var(--color-gpu)"],
            ].map(([l, c]) => (
              <span key={l} className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-[3px]" style={{ background: c }} />
                {l}
              </span>
            ))}
          </div>
        </Card>

        <Card delay={0.12} className="flex flex-col">
          <SectionTitle>Game Booster</SectionTitle>
          <motion.button
            onClick={toggleBoost}
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.96 }}
            className={`relative mx-auto my-4 w-36 h-36 rounded-full cursor-pointer flex flex-col items-center justify-center gap-1.5 font-bold text-white transition-colors ${
              active
                ? "bg-gradient-to-br from-warn/80 to-[#b97f00] animate-pulse-glow"
                : "bg-gradient-to-br from-accent to-[#1c5cab] shadow-[0_0_36px_rgba(57,135,229,.35)]"
            } ${busy ? "opacity-60" : ""}`}
          >
            {active ? <Undo2 size={30} /> : <Rocket size={30} />}
            <span className="text-[14px] tracking-wide">
              {busy ? "..." : active ? "UNDO BOOST" : "BOOST NOW"}
            </span>
          </motion.button>
          <div className="text-center text-[12px] text-ink2 leading-relaxed">
            {active ? (
              <>
                <CountUp value={live?.boost.changes.length ?? 0} className="text-accent2 font-bold" />{" "}
                change(s) applied - all reverted automatically
                {live?.boost.game ? ` when ${live.boost.game} exits` : " on undo"}.
              </>
            ) : (
              "Applies only your enabled, fully reversible tweaks. Configure them in the Booster tab."
            )}
          </div>
          <div className="mt-auto pt-4 flex items-center justify-center gap-4 text-[11.5px] text-mute">
            <span className="flex items-center gap-1.5">
              <Wifi size={13} />
              {live?.net.type ?? "..."}
            </span>
            <span className="flex items-center gap-1.5">
              <Zap size={13} />
              {live ? (live.admin ? "Administrator" : "Limited (not admin)") : "..."}
            </span>
          </div>
        </Card>
      </div>
    </div>
  );
}
