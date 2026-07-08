// Display resolution: current mode, supported mode list, gaming-resolution
// auto-switch (applied on game launch, restored on exit).
import { useEffect, useMemo, useState } from "react";
import { MonitorCog } from "lucide-react";
import { api, type AppSettings, type Live, type Mode } from "../api";
import { Button, Card, SectionTitle, Toggle } from "../components/ui";

interface ResData {
  current: Mode | null;
  modes: Mode[];
}

const fmt = (m: Mode | null) => (m ? `${m[0]} x ${m[1]} @ ${m[2]} Hz` : "unknown");

export default function Resolution(_: { live: Live | null }) {
  const [data, setData] = useState<ResData | null>(null);
  const [applyOnGame, setApplyOnGame] = useState(false);
  const [gamingRes, setGamingRes] = useState<Mode | null>(null);
  const [msg, setMsg] = useState("");

  const load = async () => {
    setData(await api<ResData>("/resolution"));
    const s = await api<AppSettings>("/settings");
    setApplyOnGame(!!s.apply_res_on_game);
    setGamingRes((s.gaming_resolution as Mode | null) ?? null);
  };
  useEffect(() => {
    load().catch(() => {});
  }, []);

  const groups = useMemo(() => {
    const by = new Map<string, Mode[]>();
    for (const m of data?.modes ?? []) {
      const k = `${m[0]} x ${m[1]}`;
      by.set(k, [...(by.get(k) ?? []), m]);
    }
    return Array.from(by.entries());
  }, [data]);

  const setMode = async (m: Mode) => {
    setMsg("switching...");
    const r = await api<{ ok: boolean; current: Mode | null }>("/resolution/set", {
      w: m[0],
      h: m[1],
      hz: m[2],
      persist: true,
    });
    setData((d) => (d ? { ...d, current: r.current } : d));
    setMsg(r.ok ? `now ${fmt(r.current)}` : "the display rejected that mode");
    setTimeout(() => setMsg(""), 5000);
  };

  const saveGaming = async (m: Mode | null) => {
    setGamingRes(m);
    await api("/settings", { key: "gaming_resolution", value: m });
  };

  const isCur = (m: Mode) =>
    data?.current && m[0] === data.current[0] && m[1] === data.current[1] && m[2] === data.current[2];

  return (
    <div className="space-y-5">
      <Card className="flex items-center gap-4">
        <div className="w-10 h-10 rounded-xl bg-accent/15 flex items-center justify-center">
          <MonitorCog size={19} className="text-accent" />
        </div>
        <div>
          <div className="text-[14px] font-semibold">Current display mode</div>
          <div className="text-[13px] text-ink2">{fmt(data?.current ?? null)}</div>
        </div>
        <span className="ml-auto text-[12px] text-accent2">{msg}</span>
      </Card>

      <Card delay={0.05}>
        <SectionTitle>Gaming resolution (auto-switch)</SectionTitle>
        <div className="flex items-center gap-3 mb-3">
          <Toggle
            on={applyOnGame}
            onChange={async (v) => {
              setApplyOnGame(v);
              await api("/settings", { key: "apply_res_on_game", value: v });
            }}
          />
          <span className="text-[13px] text-ink2">
            Switch to the selected mode when a game launches; restore the desktop mode when it exits.
          </span>
        </div>
        <select
          value={gamingRes ? gamingRes.join("x") : ""}
          onChange={(e) => {
            const v = e.target.value;
            saveGaming(v ? (v.split("x").map(Number) as unknown as Mode) : null);
          }}
          className="bg-card2 text-ink2 text-[13px] rounded-xl px-3 py-2 outline-none"
        >
          <option value="">No gaming resolution selected</option>
          {(data?.modes ?? []).map((m) => (
            <option key={m.join("x")} value={m.join("x")}>
              {fmt(m)}
            </option>
          ))}
        </select>
      </Card>

      <Card delay={0.1}>
        <SectionTitle>All supported modes</SectionTitle>
        <div className="space-y-2.5">
          {groups.map(([res, modes]) => (
            <div key={res} className="flex items-center gap-3 flex-wrap">
              <span className="w-28 text-[12.5px] text-mute shrink-0">{res}</span>
              {modes.map((m) => (
                <Button
                  key={m.join()}
                  kind={isCur(m) ? "primary" : "ghost"}
                  className="!py-1 !px-3 !text-[12px]"
                  onClick={() => setMode(m)}
                >
                  {m[2]} Hz
                </Button>
              ))}
            </div>
          ))}
          {!groups.length && <div className="text-[12.5px] text-mute">Reading display modes...</div>}
        </div>
      </Card>
    </div>
  );
}
