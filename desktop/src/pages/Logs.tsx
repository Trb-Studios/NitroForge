// Audit log: every system change the app makes (old -> new), polled live.
import { useEffect, useRef, useState } from "react";
import { api, type Live, type LogRecord } from "../api";
import { Button, Card } from "../components/ui";

const LEVEL_COLOR: Record<string, string> = {
  ERROR: "var(--color-bad)",
  WARNING: "var(--color-warn)",
  INFO: "var(--color-ink2)",
  DEBUG: "var(--color-mute)",
};

export default function Logs(_: { live: Live | null }) {
  const [records, setRecords] = useState<LogRecord[]>([]);
  const [follow, setFollow] = useState(true);
  const last = useRef(0);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const r = await api<{ records: LogRecord[]; last: number }>(
          `/logs?since=${last.current}`,
        );
        if (alive && r.records.length) {
          last.current = r.last;
          setRecords((prev) => [...prev, ...r.records].slice(-1500));
        }
      } catch {
        /* retry */
      }
      if (alive) t = window.setTimeout(tick, 2000);
    };
    let t = window.setTimeout(tick, 0);
    return () => {
      alive = false;
      window.clearTimeout(t);
    };
  }, []);

  useEffect(() => {
    if (follow && box.current) box.current.scrollTop = box.current.scrollHeight;
  }, [records, follow]);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Button kind="ghost" onClick={() => setRecords([])}>
          Clear view
        </Button>
        <label className="flex items-center gap-2 text-[12.5px] text-ink2 cursor-pointer">
          <input
            type="checkbox"
            checked={follow}
            onChange={(e) => setFollow(e.target.checked)}
            className="accent-[var(--color-accent)]"
          />
          Follow new entries
        </label>
        <span className="text-[12px] text-mute ml-auto">
          Every change Nitro Forge makes is recorded here and in app.log.
        </span>
      </div>

      <Card className="!p-0 overflow-hidden">
        <div ref={box} className="max-h-[62vh] overflow-y-auto p-3 font-mono text-[11.5px] leading-relaxed">
          {records.map((r) => (
            <div key={r.n} className="flex gap-3 whitespace-pre-wrap break-all">
              <span className="text-mute shrink-0 tabular-nums">
                {new Date(r.ts * 1000).toLocaleTimeString()}
              </span>
              <span
                className="shrink-0 w-14 font-semibold"
                style={{ color: LEVEL_COLOR[r.level] ?? "var(--color-ink2)" }}
              >
                {r.level}
              </span>
              <span className="text-ink2">{r.msg}</span>
            </div>
          ))}
          {!records.length && (
            <div className="text-mute font-sans text-[12.5px] p-2">Waiting for log entries...</div>
          )}
        </div>
      </Card>
    </div>
  );
}
