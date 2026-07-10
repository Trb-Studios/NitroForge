// Booster page: sub-feature toggles, allowlist, startup apps, honest notes,
// and the live list of applied (reversible) changes.
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState } from "react";
import { ExternalLink, RotateCcw, ShieldCheck } from "lucide-react";
import { api, usePoll, type BoosterState, type Live, type StartupApp } from "../api";
import { Button, Card, SectionTitle, SeverityCard, Toggle } from "../components/ui";

const FEATURES: [string, string, string][] = [
  ["boost_suspend_apps", "Suspend background apps",
   "Freezes only the allowlisted apps below (browsers, cloud sync, RGB suites). Resumed on revert - nothing is killed."],
  ["boost_priority", "Raise game priority to High",
   "Windows favours the game. Realtime is deliberately not offered - it can starve the OS."],
  ["boost_affinity", "CPU affinity tuning (leave core 0 free)",
   "Pins the game to cores 1..N so core 0 stays free for OS/interrupt work. Helps some CPUs; off by default."],
  ["boost_power_plan", "High/Ultimate Performance power plan",
   "This is what 'disable CPU throttling' really means: powercfg switches plan, your previous plan is restored on revert."],
  ["boost_game_mode", "Enable Windows Game Mode",
   "Windows' own optimisation (registry toggle). Reverted if we changed it."],
  ["boost_game_bar", "Disable Xbox Game Bar overlay",
   "Official registry switches only. Steam/GeForce overlays are third-party - disable those in each launcher."],
  ["boost_visual_effects", "Reduce Windows visual effects",
   "Sets 'adjust for best performance'. Mostly helps older PCs; parts apply after re-login."],
  ["boost_services", "Pause background services",
   "Temporarily stops Windows Update, Search, SysMain, Maps, Delivery Optimization, Telemetry. Restarted on revert. Needs admin. Security/AV services are hard-blocked in code."],
  ["boost_network_latency", "Disable Nagle's algorithm",
   "Sends small game packets immediately instead of batching them - lower, steadier ping. Per-adapter registry values, restored exactly on revert. Needs admin."],
  ["boost_responsiveness", "Lift network throttling + system responsiveness",
   "NetworkThrottlingIndex off and SystemResponsiveness 0 give the foreground game more CPU/network priority. Restored on revert. Needs admin."],
  ["boost_games_scheduling", "Raise MMCSS 'Games' scheduling priority",
   "Tells Windows' multimedia scheduler to give games top GPU/CPU/IO priority (GPU 8, Priority 6, High). Restored on revert. Needs admin."],
  ["boost_power_latency", "USB power-parking off + CPU core parking off",
   "Stops Windows suspending USB devices (your mouse/keyboard) and parking CPU cores mid-game. Restored to your previous plan values on revert. Needs admin."],
];

export default function Booster({ live }: { live: Live | null }) {
  const state = usePoll<BoosterState>("/booster", 2500);
  const [flags, setFlags] = useState<Record<string, boolean>>({});
  const [onLaunch, setOnLaunch] = useState(false);
  const [allow, setAllow] = useState("");
  const [allowDirty, setAllowDirty] = useState(false);
  const [startup, setStartup] = useState<StartupApp[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!state) return;
    setFlags((f) => (Object.keys(f).length ? f : state.flags));
    setOnLaunch(state.boost_on_launch);
    if (!allowDirty) setAllow(state.allowlist.join("\n"));
  }, [state]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    api<{ apps: StartupApp[] }>("/startup").then((r) => setStartup(r.apps)).catch(() => {});
  }, []);

  const setFlag = async (key: string, v: boolean) => {
    setFlags((f) => ({ ...f, [key]: v }));
    await api("/settings", { key, value: v });
  };

  const saveAllow = async () => {
    const names = allow.split("\n").map((s) => s.trim()).filter(Boolean);
    const r = await api<{ value: string[] }>("/settings", { key: "suspend_apps", value: names });
    setAllow(r.value.join("\n"));
    setAllowDirty(false);
  };

  const toggleBoost = async () => {
    setBusy(true);
    try {
      await api(state?.active ? "/booster/revert" : "/booster/apply", {});
    } finally {
      setBusy(false);
    }
  };

  const toggleStartup = async (a: StartupApp) => {
    await api("/startup/toggle", { name: a.name, enabled: !a.enabled });
    const r = await api<{ apps: StartupApp[] }>("/startup");
    setStartup(r.apps);
  };

  return (
    <div className="space-y-5">
      <Card className="flex items-center gap-5">
        <Button
          onClick={toggleBoost}
          disabled={busy}
          kind={state?.active ? "danger" : "primary"}
          className="!px-7 !py-3 !text-[15px]"
        >
          {state?.active ? "Undo Boost" : "Boost Now"}
        </Button>
        <div className="flex items-center gap-3">
          <Toggle
            on={onLaunch}
            onChange={async (v) => {
              setOnLaunch(v);
              await api("/settings", { key: "boost_on_launch", value: v });
            }}
          />
          <span className="text-[13px] text-ink2">
            Use when launching games (apply before launch, auto-revert on exit)
          </span>
        </div>
        {live && !live.admin && (
          <span className="ml-auto text-[12px] text-warn">
            Not admin: service pausing will be skipped
          </span>
        )}
      </Card>

      <div className="grid grid-cols-2 gap-5">
        <Card delay={0.05}>
          <SectionTitle>What Boost is allowed to do</SectionTitle>
          <div className="space-y-4">
            {FEATURES.map(([key, label, desc]) => (
              <div key={key} className="flex gap-3.5 items-start">
                <Toggle on={flags[key] ?? false} onChange={(v) => setFlag(key, v)} />
                <div>
                  <div className="text-[13.5px] font-semibold">{label}</div>
                  <div className="text-[12px] text-mute leading-relaxed">{desc}</div>
                </div>
              </div>
            ))}
          </div>
        </Card>

        <div className="space-y-5">
          <Card delay={0.08}>
            <SectionTitle>Applied changes (all reversible)</SectionTitle>
            <div className="space-y-1.5 min-h-[60px]">
              <AnimatePresence>
                {(state?.changes ?? []).map((c) => (
                  <motion.div
                    key={c}
                    initial={{ opacity: 0, x: -12 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: 12 }}
                    className="flex items-center gap-2 text-[12.5px] text-ink2"
                  >
                    <RotateCcw size={12} className="text-accent2 shrink-0" />
                    {c}
                  </motion.div>
                ))}
              </AnimatePresence>
              {!state?.changes.length && (
                <div className="text-[12.5px] text-mute">None - system is in its normal state.</div>
              )}
            </div>
          </Card>

          <Card delay={0.11}>
            <SectionTitle>Background-app allowlist</SectionTitle>
            <div className="text-[12px] text-mute mb-2 flex items-center gap-1.5">
              <ShieldCheck size={13} className="text-ok" />
              Only these can be suspended. OS-critical and security processes are refused even if typed here.
            </div>
            <textarea
              value={allow}
              onChange={(e) => {
                setAllow(e.target.value);
                setAllowDirty(true);
              }}
              spellCheck={false}
              className="w-full h-36 rounded-xl bg-card2 p-3 text-[12px] font-mono text-ink2 outline-none focus:ring-1 focus:ring-accent resize-none"
            />
            <Button onClick={saveAllow} kind="ghost" className="mt-2" disabled={!allowDirty}>
              Save allowlist
            </Button>
          </Card>
        </div>
      </div>

      <Card delay={0.14}>
        <SectionTitle>Startup apps (current user)</SectionTitle>
        <div className="grid grid-cols-2 gap-x-8 gap-y-1.5">
          {startup.map((a) => (
            <div key={a.name} className="flex items-center gap-3 py-1">
              <Toggle on={a.enabled} onChange={() => toggleStartup(a)} />
              <span className={`text-[13px] truncate ${a.enabled ? "text-ink" : "text-mute"}`} title={a.command}>
                {a.name}
              </span>
            </div>
          ))}
          {!startup.length && <div className="text-[12.5px] text-mute">No per-user startup entries found.</div>}
        </div>
      </Card>

      <Card delay={0.17}>
        <SectionTitle>Things only you (or your drivers) can do</SectionTitle>
        <div className="grid grid-cols-2 gap-3">
          <SeverityCard severity="warn" title="Laptop hybrid graphics"
            detail="Forcing the discrete GPU is an NVIDIA Optimus / AMD Switchable Graphics driver setting. Set 'High performance' per game in Windows Graphics settings or the vendor panel - an app can't safely override it." />
          <SeverityCard severity="warn" title="Driver settings" delay={0.05}
            detail="NVIDIA Control Panel: Power management 'Prefer maximum performance', Low Latency Mode On/Ultra (AMD: Anti-Lag). Use the button below to open the panel." />
          <SeverityCard severity="warn" title="Network QoS" delay={0.1}
            detail="Pausing cloud-sync apps frees bandwidth, but true packet prioritisation only exists in your router settings - no desktop app can do it, whatever the marketing says." />
          <SeverityCard severity="warn" title="In-game settings" delay={0.15}
            detail="Shadows, anti-aliasing and post-processing are the usual FPS hogs. This app won't fake an 'apply' button for settings that live inside each game." />
        </div>
        <Button
          kind="ghost"
          className="mt-4"
          onClick={() => api("/gpu-panel", {})}
        >
          <span className="flex items-center gap-2">
            <ExternalLink size={14} /> Open GPU control panel
          </span>
        </Button>
      </Card>
    </div>
  );
}
