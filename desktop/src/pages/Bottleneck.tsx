// Bottleneck analysis: hardware pairing rules (static) + what the last
// 5 minutes of samples say is holding your FPS back (live).
import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { api, type Finding, type Live } from "../api";
import { Button, SectionTitle, SeverityCard } from "../components/ui";

export default function Bottleneck(_: { live: Live | null }) {
  const [statics, setStatics] = useState<Finding[] | null>(null);
  const [lives, setLives] = useState<Finding[] | null>(null);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    setBusy(true);
    try {
      const [s, l] = await Promise.all([
        api<{ findings: Finding[] }>("/bottleneck/static"),
        api<{ findings: Finding[] }>("/bottleneck/live"),
      ]);
      setStatics(s.findings);
      setLives(l.findings);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    load().catch(() => setBusy(false));
  }, []);

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <Button kind="ghost" onClick={load} disabled={busy}>
          <span className="flex items-center gap-2">
            <RefreshCw size={14} className={busy ? "animate-spin" : ""} /> Re-analyze
          </span>
        </Button>
        <span className="text-[12px] text-mute">
          Live findings use the last 5 minutes of samples - play a game first for real results.
        </span>
      </div>

      <div>
        <SectionTitle>Right now (live)</SectionTitle>
        <div className="space-y-2.5">
          {(lives ?? []).map((f, i) => (
            <SeverityCard key={i} severity={f.severity} title={f.title} detail={f.detail} delay={i * 0.05} />
          ))}
          {lives !== null && !lives.length && (
            <div className="text-[12.5px] text-mute">
              Not enough recent activity to judge - start a game and check back.
            </div>
          )}
          {lives === null && <div className="h-16 rounded-xl skeleton" />}
        </div>
      </div>

      <div>
        <SectionTitle>Hardware pairing (static)</SectionTitle>
        <div className="space-y-2.5">
          {(statics ?? []).map((f, i) => (
            <SeverityCard key={i} severity={f.severity} title={f.title} detail={f.detail} delay={i * 0.05} />
          ))}
          {statics === null && <div className="h-16 rounded-xl skeleton" />}
        </div>
      </div>
    </div>
  );
}
