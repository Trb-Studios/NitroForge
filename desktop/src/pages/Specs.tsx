// PC specs: hardware inventory cards (one fetch + manual refresh).
import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { api, type Live } from "../api";
import { Button, Card, SectionTitle } from "../components/ui";

interface Specs {
  cpu: { name: string; physical_cores: number; logical_cores: number; base_mhz: number | null };
  cpu_live: { percent: number; current_mhz: number | null };
  gpus: { name: string; vram_mb: number | null; driver_version: string | null; driver_date: string | null }[];
  gpu_live: { load: number | null; mem_used: number | null; mem_total: number | null; temp: number | null };
  ram: { total_gb: number; used_gb: number; available_gb: number; percent: number };
  modules: { capacity_gb: number; speed_mhz: number | null; manufacturer: string; slot: string }[];
  storage: { mount: string; total_gb: number; used_percent: number; kind: string }[];
  monitors: { name: string | null; width: number; height: number; primary: boolean; refresh_hz: number | null }[];
  os: { os: string; version: string; machine: string; hostname: string; admin: boolean };
  hags: boolean | null;
  driver_warning: string | null;
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-6 py-1 border-b border-line/40 last:border-0">
      <span className="text-[12.5px] text-mute shrink-0">{label}</span>
      <span className="text-[12.5px] text-ink2 text-right">{value}</span>
    </div>
  );
}

export default function Specs(_: { live: Live | null }) {
  const [specs, setSpecs] = useState<Specs | null>(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      setSpecs(await api<Specs>("/specs"));
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    load();
  }, []);

  if (!specs) {
    return <div className="text-[13px] text-mute animate-pulse">Reading hardware info (WMI is slow)...</div>;
  }

  const g = specs.gpus[0];
  const gl = specs.gpu_live;
  return (
    <div className="space-y-4">
      <Button kind="ghost" onClick={load} disabled={loading}>
        <span className="flex items-center gap-2">
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} /> Refresh
        </span>
      </Button>
      <div className="grid grid-cols-2 gap-4">
        <Card>
          <SectionTitle>CPU</SectionTitle>
          <Row label="Model" value={specs.cpu.name} />
          <Row label="Cores" value={`${specs.cpu.physical_cores} physical / ${specs.cpu.logical_cores} logical`} />
          <Row label="Base clock" value={specs.cpu.base_mhz ? `${specs.cpu.base_mhz} MHz` : "?"} />
          <Row label="Current clock" value={specs.cpu_live.current_mhz ? `${specs.cpu_live.current_mhz} MHz` : "?"} />
          <Row label="Usage now" value={`${specs.cpu_live.percent.toFixed(0)}%`} />
        </Card>
        <Card delay={0.04}>
          <SectionTitle>GPU</SectionTitle>
          <Row label="Model" value={g?.name ?? "not detected"} />
          <Row
            label="VRAM"
            value={
              gl.mem_total
                ? `${gl.mem_used?.toFixed(0)} / ${gl.mem_total.toFixed(0)} MB used`
                : g?.vram_mb
                  ? `${g.vram_mb.toFixed(0)} MB (live stats need NVIDIA)`
                  : "n/a"
            }
          />
          <Row label="Load" value={gl.load != null ? `${gl.load.toFixed(0)}%` : "n/a (non-NVIDIA fallback)"} />
          <Row label="Temperature" value={gl.temp != null ? `${gl.temp.toFixed(0)} C` : "n/a (driver-dependent)"} />
          <Row label="Driver" value={g?.driver_version ?? "?"} />
          <Row
            label="HW GPU scheduling"
            value={specs.hags === null ? "unknown" : specs.hags ? "on" : "off (Windows Graphics settings)"}
          />
          {specs.driver_warning && (
            <div className="mt-2 text-[12px] text-warn">{specs.driver_warning}</div>
          )}
        </Card>
        <Card delay={0.08}>
          <SectionTitle>RAM</SectionTitle>
          <Row
            label="Installed"
            value={`${specs.ram.total_gb.toFixed(1)} GB - ${specs.ram.percent.toFixed(0)}% used`}
          />
          {specs.modules.map((m, i) => (
            <Row
              key={i}
              label={m.slot}
              value={`${m.capacity_gb.toFixed(0)} GB @ ${m.speed_mhz ?? "?"} MHz (${m.manufacturer})`}
            />
          ))}
        </Card>
        <Card delay={0.12}>
          <SectionTitle>Storage</SectionTitle>
          {specs.storage.map((s) => (
            <Row
              key={s.mount}
              label={s.mount}
              value={`${s.total_gb.toFixed(0)} GB - ${s.used_percent.toFixed(0)}% used - ${s.kind} (best-effort)`}
            />
          ))}
        </Card>
        <Card delay={0.16}>
          <SectionTitle>Monitors</SectionTitle>
          {specs.monitors.map((m, i) => (
            <Row
              key={i}
              label={m.name ?? `Display ${i + 1}`}
              value={`${m.width} x ${m.height}${m.refresh_hz ? ` @ ${m.refresh_hz} Hz` : ""}${m.primary ? "  [primary]" : ""}`}
            />
          ))}
        </Card>
        <Card delay={0.2}>
          <SectionTitle>System</SectionTitle>
          <Row label="OS" value={`${specs.os.os} (${specs.os.machine})`} />
          <Row label="Build" value={specs.os.version} />
          <Row label="Computer" value={specs.os.hostname} />
          <Row label="Privileges" value={specs.os.admin ? "Administrator" : "Standard user (some tweaks limited)"} />
        </Card>
      </div>
    </div>
  );
}
