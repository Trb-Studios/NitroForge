// Input / peripherals tab: the real Windows mouse settings we CAN change
// (pointer acceleration + speed), plus honest guidance for the settings that
// live on the device or in its own software (DPI, polling rate, key actuation).
import { useEffect, useState } from "react";
import { Gauge, Keyboard, Mouse, Zap } from "lucide-react";
import { api, type Live } from "../api";
import { Card, SectionTitle, SeverityCard, Toggle } from "../components/ui";

interface MouseState {
  enhance_pointer: boolean;
  pointer_speed: number;
}

export default function Input(_: { live: Live | null }) {
  const [mouse, setMouse] = useState<MouseState | null>(null);
  const [admin, setAdmin] = useState(true);

  useEffect(() => {
    api<{ mouse: MouseState; admin: boolean }>("/input")
      .then((r) => {
        setMouse(r.mouse);
        setAdmin(r.admin);
      })
      .catch(() => {});
  }, []);

  const setEnhance = async (v: boolean) => {
    setMouse((m) => (m ? { ...m, enhance_pointer: v } : m));
    const r = await api<{ mouse: MouseState }>("/input/mouse", { enhance_pointer: v });
    setMouse(r.mouse);
  };

  const setSpeed = async (v: number) => {
    setMouse((m) => (m ? { ...m, pointer_speed: v } : m));
    const r = await api<{ mouse: MouseState }>("/input/mouse", { pointer_speed: v });
    setMouse(r.mouse);
  };

  return (
    <div className="space-y-5">
      <Card>
        <SectionTitle>
          <span className="flex items-center gap-2">
            <Mouse size={13} /> Mouse (applied instantly, system-wide)
          </span>
        </SectionTitle>
        <div className="space-y-5">
          <div className="flex items-center justify-between">
            <div className="max-w-[70%]">
              <div className="text-[13.5px] font-semibold">
                Enhance pointer precision (mouse acceleration)
              </div>
              <div className="text-[12px] text-mute leading-relaxed">
                Windows speeds the cursor up the faster you move. Competitive
                players turn this <b>off</b> so the same hand movement always
                travels the same distance - a true 1:1 feel your muscle memory
                can rely on.
              </div>
            </div>
            <Toggle
              on={mouse?.enhance_pointer ?? true}
              onChange={setEnhance}
            />
          </div>

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <div className="text-[13.5px] font-semibold">Pointer speed</div>
              <div className="text-[12px] text-accent2 tabular-nums">
                {mouse?.pointer_speed ?? 10} / 20
              </div>
            </div>
            <input
              type="range"
              min={1}
              max={20}
              value={mouse?.pointer_speed ?? 10}
              onChange={(e) => setSpeed(Number(e.target.value))}
              className="w-full accent-[var(--color-accent)] cursor-pointer"
            />
            <div className="flex justify-between text-[11px] text-mute mt-1">
              <span>slower</span>
              <span>6/20 = Windows default 1:1 · set DPI on the mouse, not here</span>
              <span>faster</span>
            </div>
          </div>
        </div>
      </Card>

      {!admin && (
        <SeverityCard
          severity="warn"
          title="Some tweaks need Administrator"
          detail="Mouse settings here work without admin, but the Boost tab's network/scheduling latency tweaks need you to run Nitro Forge as Administrator."
        />
      )}

      <div className="grid grid-cols-2 gap-5">
        <Card delay={0.05}>
          <SectionTitle>
            <span className="flex items-center gap-2">
              <Gauge size={13} /> DPI &amp; polling rate
            </span>
          </SectionTitle>
          <div className="space-y-3">
            <SeverityCard
              severity="ok"
              title="Set DPI on the mouse itself"
              detail="DPI/CPI lives in your mouse's firmware and its vendor app (Logitech G HUB, Razer Synapse, SteelSeries GG, Corsair iCUE). 800 or 1600 DPI is the competitive standard; go lower for big arm-aim swipes, higher for tiny wrist movements."
            />
            <SeverityCard
              severity="ok"
              title="Polling rate: 1000 Hz+"
              delay={0.05}
              detail="Set 1000 Hz (or 4000/8000 Hz if your mouse and its software support it) in the vendor app. Higher polling reports position more often, shaving a hair of input latency. A Python app can't flash mouse firmware - so this is a pointer, not a fake button."
            />
          </div>
        </Card>

        <Card delay={0.09}>
          <SectionTitle>
            <span className="flex items-center gap-2">
              <Keyboard size={13} /> Keyboard actuation
            </span>
          </SectionTitle>
          <div className="space-y-3">
            <SeverityCard
              severity="ok"
              title="Actuation point (Hall-effect / analog boards)"
              detail="If you have a Wooting, Razer Huntsman Analog, SteelSeries Apex Pro or similar, set a shorter actuation (e.g. 1.0-1.5 mm) and Rapid Trigger in its software for faster key registration. Standard mechanical/membrane boards have a fixed actuation point."
            />
            <SeverityCard
              severity="ok"
              title="N-key rollover & polling"
              delay={0.05}
              detail="Enable NKRO and the highest polling rate in your keyboard's software so fast multi-key inputs never drop. As with the mouse, these live on the device - Nitro Forge points you to them rather than pretending to set them."
            />
          </div>
        </Card>
      </div>

      <Card delay={0.13}>
        <SectionTitle>
          <span className="flex items-center gap-2">
            <Zap size={13} /> Where the rest of your input latency lives
          </span>
        </SectionTitle>
        <div className="text-[12.5px] text-ink2 leading-relaxed">
          The biggest input-lag wins are: a wired (not wireless) mouse/keyboard,
          your monitor at its true max refresh rate with G-Sync/FreeSync on, and
          NVIDIA Reflex / AMD Anti-Lag enabled in-game. The Boost tab handles the
          system side (USB power parking, scheduling, network throttling); the
          display side lives in the System &gt; Resolution tab and your monitor's
          own menu (turn off its "motion smoothing" / TV game modes - those add
          real display lag).
        </div>
      </Card>
    </div>
  );
}
