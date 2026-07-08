// Better task manager: diagnostics, sortable live table, guarded actions.
import { motion } from "motion/react";
import { useMemo, useState } from "react";
import { api, usePoll, type Diagnostic, type Live, type ProcRow } from "../api";
import { Button, Card, Modal, SectionTitle } from "../components/ui";

type SortKey = "name" | "pid" | "cpu" | "ram" | "disk_mbs";
const PRIORITIES = ["Low", "Below Normal", "Normal", "Above Normal", "High", "Realtime"];

const SEV_DOT = { ok: "var(--color-ok)", warn: "var(--color-warn)", bad: "var(--color-bad)" };

export default function Processes(_: { live: Live | null }) {
  const data = usePoll<{ rows: ProcRow[]; diagnostics: Diagnostic[] }>("/processes", 3000);
  const [sort, setSort] = useState<{ key: SortKey; desc: boolean }>({ key: "cpu", desc: true });
  const [sel, setSel] = useState<number | null>(null);
  const [prio, setPrio] = useState("High");
  const [confirm, setConfirm] = useState<{ title: string; body: string; run: () => Promise<unknown> } | null>(null);
  const [affinityOpen, setAffinityOpen] = useState(false);
  const [cores, setCores] = useState<boolean[]>([]);
  const [msg, setMsg] = useState("");

  const rows = useMemo(() => {
    const r = [...(data?.rows ?? [])];
    r.sort((a, b) => {
      const va = a[sort.key], vb = b[sort.key];
      const c = typeof va === "string" ? (va as string).localeCompare(vb as string) : (va as number) - (vb as number);
      return sort.desc ? -c : c;
    });
    return r.slice(0, 250);
  }, [data, sort]);

  const selected = rows.find((r) => r.pid === sel) ?? null;

  const act = async (body: Record<string, unknown>, okMsg: string) => {
    try {
      await api("/process/action", { pid: sel, ...body });
      setMsg(okMsg);
    } catch (e) {
      setMsg(String((e as Error).message));
    }
    setTimeout(() => setMsg(""), 5000);
  };

  const header = (key: SortKey, label: string, right = false) => (
    <th
      onClick={() => setSort((s) => ({ key, desc: s.key === key ? !s.desc : key !== "name" }))}
      className={`px-3 py-2 text-[11px] font-semibold uppercase tracking-wider text-mute cursor-pointer hover:text-ink2 select-none ${right ? "text-right" : "text-left"}`}
    >
      {label} {sort.key === key ? (sort.desc ? "↓" : "↑") : ""}
    </th>
  );

  const nCores = navigator.hardwareConcurrency || 8;

  return (
    <div className="space-y-4">
      <Card>
        <SectionTitle>What's slowing my game</SectionTitle>
        <div className="space-y-1.5">
          {(data?.diagnostics ?? []).map((d, i) => (
            <div key={i} className="flex items-start gap-2.5 text-[12.5px] text-ink2">
              <span className="w-2 h-2 rounded-full mt-1.5 shrink-0" style={{ background: SEV_DOT[d.severity] }} />
              {d.text}
            </div>
          ))}
          {data && !data.diagnostics.length && (
            <div className="text-[12.5px] text-ink2">
              Nothing significant is competing with your game right now.
            </div>
          )}
        </div>
      </Card>

      <div className="flex items-center gap-2 flex-wrap">
        <select
          value={prio}
          onChange={(e) => setPrio(e.target.value)}
          className="bg-card2 text-ink2 text-[13px] rounded-xl px-3 py-2 outline-none"
        >
          {PRIORITIES.map((p) => (
            <option key={p}>{p}</option>
          ))}
        </select>
        <Button kind="ghost" disabled={!selected} onClick={() =>
          prio === "Realtime"
            ? setConfirm({
                title: "Realtime priority?",
                body: "Realtime can starve Windows itself (audio glitches, input lag, hangs). High is almost always better. Set Realtime anyway?",
                run: () => api("/process/action", { pid: sel, action: "priority", level: "Realtime" }),
              })
            : act({ action: "priority", level: prio }, `priority set to ${prio}`)
        }>
          Set priority
        </Button>
        <Button kind="ghost" disabled={!selected} onClick={() => { setCores(Array(nCores).fill(true)); setAffinityOpen(true); }}>
          Set affinity...
        </Button>
        <Button kind="ghost" disabled={!selected} onClick={() =>
          setConfirm({
            title: `Suspend ${selected?.name}?`,
            body: "The process freezes until you resume it.",
            run: () => api("/process/action", { pid: sel, action: "suspend" }),
          })
        }>
          Suspend
        </Button>
        <Button kind="ghost" disabled={!selected} onClick={() => act({ action: "resume" }, "resumed")}>
          Resume
        </Button>
        <Button kind="danger" disabled={!selected} onClick={() =>
          setConfirm({
            title: `Kill ${selected?.name} (pid ${sel})?`,
            body: "Unsaved data in that process will be lost.",
            run: () => api("/process/action", { pid: sel, action: "kill" }),
          })
        }>
          Kill
        </Button>
        <span className="text-[12px] text-warn">{msg}</span>
      </div>

      <Card className="!p-0 overflow-hidden">
        <div className="max-h-[52vh] overflow-y-auto">
          <table className="w-full text-[12.5px]">
            <thead className="sticky top-0 bg-card2 z-10">
              <tr>
                {header("name", "Process")}
                {header("pid", "PID", true)}
                {header("cpu", "CPU %", true)}
                {header("ram", "RAM %", true)}
                {header("disk_mbs", "Disk MB/s", true)}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr
                  key={r.pid}
                  onClick={() => setSel(r.pid === sel ? null : r.pid)}
                  className={`cursor-pointer transition-colors ${
                    r.pid === sel ? "bg-accent/20" : "odd:bg-white/[.015] hover:bg-white/[.05]"
                  }`}
                >
                  <td className="px-3 py-1.5 truncate max-w-[300px]">
                    {r.name}
                    {r.protected && <span className="ml-2 text-[10px] text-mute">[protected]</span>}
                  </td>
                  <td className="px-3 py-1.5 text-right text-mute tabular-nums">{r.pid}</td>
                  <td className={`px-3 py-1.5 text-right tabular-nums ${r.cpu > 15 ? "text-warn" : ""}`}>{r.cpu.toFixed(1)}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums">{r.ram.toFixed(1)}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums">{r.disk_mbs.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Modal open={!!confirm} onClose={() => setConfirm(null)}>
        <div className="text-[15px] font-semibold mb-2">{confirm?.title}</div>
        <div className="text-[13px] text-ink2 mb-5">{confirm?.body}</div>
        <div className="flex justify-end gap-2">
          <Button kind="ghost" onClick={() => setConfirm(null)}>Cancel</Button>
          <Button
            kind="danger"
            onClick={async () => {
              try {
                await confirm?.run();
                setMsg("done");
              } catch (e) {
                setMsg(String((e as Error).message));
              }
              setConfirm(null);
              setTimeout(() => setMsg(""), 5000);
            }}
          >
            Confirm
          </Button>
        </div>
      </Modal>

      <Modal open={affinityOpen} onClose={() => setAffinityOpen(false)}>
        <div className="text-[15px] font-semibold mb-1">CPU affinity - {selected?.name}</div>
        <div className="text-[12.5px] text-mute mb-4">Pick which logical cores the process may run on.</div>
        <div className="grid grid-cols-4 gap-2 mb-5">
          {cores.map((on, i) => (
            <motion.button
              key={i}
              whileTap={{ scale: 0.92 }}
              onClick={() => setCores((c) => c.map((v, j) => (j === i ? !v : v)))}
              className={`px-2 py-2 rounded-lg text-[12px] font-semibold transition-colors ${
                on ? "bg-accent text-white" : "bg-card2 text-mute"
              }`}
            >
              Core {i}
            </motion.button>
          ))}
        </div>
        <div className="flex justify-end gap-2">
          <Button kind="ghost" onClick={() => setAffinityOpen(false)}>Cancel</Button>
          <Button
            onClick={async () => {
              const list = cores.map((v, i) => (v ? i : -1)).filter((i) => i >= 0);
              if (list.length) await act({ action: "affinity", cores: list }, "affinity set");
              setAffinityOpen(false);
            }}
          >
            Apply
          </Button>
        </div>
      </Modal>
    </div>
  );
}
