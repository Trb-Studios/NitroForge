// Performance history: stat tiles + utilization/FPS charts over a
// selectable window, fed by the background sampler's SQLite history.
import { useEffect, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, type AnalyticsData, type Live } from "../api";
import { Card, CountUp, SectionTitle, Segmented } from "../components/ui";

const WINDOWS: Record<string, number> = {
  "15 min": 900,
  Hour: 3600,
  Day: 86400,
  Week: 604800,
};

function Tile({ label, value, suffix = "", decimals = 0, delay = 0 }: {
  label: string;
  value: number | null;
  suffix?: string;
  decimals?: number;
  delay?: number;
}) {
  return (
    <Card delay={delay} className="!p-4">
      <div className="text-[10.5px] font-semibold tracking-[0.14em] uppercase text-mute mb-1">
        {label}
      </div>
      <div className="text-[24px] font-bold tabular-nums">
        {value === null ? (
          <span className="text-mute text-lg">no data</span>
        ) : (
          <CountUp value={value} decimals={decimals} suffix={suffix} />
        )}
      </div>
    </Card>
  );
}

const tooltipStyle = {
  background: "var(--color-card2)",
  border: "1px solid var(--color-line)",
  borderRadius: 12,
  fontSize: 12,
} as const;

export default function Analytics(_: { live: Live | null }) {
  const [win, setWin] = useState("Hour");
  const [data, setData] = useState<AnalyticsData | null>(null);

  useEffect(() => {
    let alive = true;
    const load = () =>
      api<AnalyticsData>(`/analytics?secs=${WINDOWS[win]}`)
        .then((d) => alive && setData(d))
        .catch(() => {});
    load();
    const t = window.setInterval(load, 15000);
    return () => {
      alive = false;
      window.clearInterval(t);
    };
  }, [win]);

  const rows = (data?.rows ?? []).map((r) => ({
    ...r,
    time: new Date(r.t * 1000).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    }),
  }));
  const s = data?.stats;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <Segmented id="anal-win" options={Object.keys(WINDOWS)} value={win} onChange={setWin} />
        <span className="text-[12px] text-mute">
          {s?.count ? `${s.count.toLocaleString()} samples` : "sampling every 3s in the background"}
        </span>
      </div>

      <div className="grid grid-cols-5 gap-4">
        <Tile label="Avg CPU" value={s?.avg_cpu ?? null} suffix="%" />
        <Tile label="Avg GPU" value={s?.avg_gpu ?? null} suffix="%" delay={0.04} />
        <Tile label="Avg RAM" value={s?.avg_ram ?? null} suffix="%" delay={0.08} />
        <Tile label="Avg FPS" value={s?.avg_fps ?? null} delay={0.12} />
        <Tile label="Min / Max FPS" value={s?.min_fps ?? null} delay={0.16} />
      </div>

      <Card delay={0.1}>
        <SectionTitle>Utilization</SectionTitle>
        <div className="h-[230px] -mx-2">
          <ResponsiveContainer>
            <AreaChart data={rows} margin={{ top: 4, right: 8, left: -18, bottom: 0 }}>
              <defs>
                {[
                  ["cpu", "var(--color-cpu)"],
                  ["ram", "var(--color-ram)"],
                  ["gpu", "var(--color-gpu)"],
                ].map(([k, c]) => (
                  <linearGradient key={k} id={`ga-${k}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={c} stopOpacity={0.25} />
                    <stop offset="100%" stopColor={c} stopOpacity={0} />
                  </linearGradient>
                ))}
              </defs>
              <CartesianGrid stroke="var(--color-line)" strokeWidth={0.6} vertical={false} />
              <XAxis
                dataKey="time"
                tick={{ fill: "var(--color-mute)", fontSize: 10 }}
                axisLine={false}
                tickLine={false}
                minTickGap={60}
              />
              <YAxis
                domain={[0, 100]}
                tick={{ fill: "var(--color-mute)", fontSize: 10 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip contentStyle={tooltipStyle} />
              <Area type="monotone" dataKey="cpu" name="CPU %" stroke="var(--color-cpu)" strokeWidth={1.6} fill="url(#ga-cpu)" isAnimationActive={false} connectNulls />
              <Area type="monotone" dataKey="ram" name="RAM %" stroke="var(--color-ram)" strokeWidth={1.6} fill="url(#ga-ram)" isAnimationActive={false} connectNulls />
              <Area type="monotone" dataKey="gpu" name="GPU %" stroke="var(--color-gpu)" strokeWidth={1.6} fill="url(#ga-gpu)" isAnimationActive={false} connectNulls />
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

      <Card delay={0.15}>
        <SectionTitle>FPS / frame time</SectionTitle>
        <div className="h-[200px] -mx-2">
          <ResponsiveContainer>
            <LineChart data={rows} margin={{ top: 4, right: 8, left: -18, bottom: 0 }}>
              <CartesianGrid stroke="var(--color-line)" strokeWidth={0.6} vertical={false} />
              <XAxis
                dataKey="time"
                tick={{ fill: "var(--color-mute)", fontSize: 10 }}
                axisLine={false}
                tickLine={false}
                minTickGap={60}
              />
              <YAxis
                tick={{ fill: "var(--color-mute)", fontSize: 10 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip contentStyle={tooltipStyle} />
              <Line type="monotone" dataKey="fps" name="FPS" stroke="var(--color-fpsline)" strokeWidth={1.8} dot={false} isAnimationActive={false} connectNulls />
              <Line type="monotone" dataKey="ft" name="Frame ms" stroke="var(--color-ft)" strokeWidth={1.4} dot={false} isAnimationActive={false} connectNulls />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div className="text-[11.5px] text-mute mt-1">
          FPS rows only exist while PresentMon capture is running (System → FPS Overlay).
        </div>
      </Card>
    </div>
  );
}
