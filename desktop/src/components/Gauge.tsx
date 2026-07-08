// Animated radial gauge: 270-degree arc, spring-driven sweep, soft glow.
import { motion, useSpring, useTransform } from "motion/react";
import { useEffect } from "react";
import { CountUp } from "./ui";

const R = 52;
const CIRC = 2 * Math.PI * R;
const SWEEP = 0.75; // 270 degrees

export default function Gauge({
  value,
  label,
  color,
  display,
  suffix = "%",
  max = 100,
}: {
  value: number | null;
  label: string;
  color: string;
  display?: string;
  suffix?: string;
  max?: number;
}) {
  const spring = useSpring(0, { stiffness: 60, damping: 18 });
  useEffect(() => {
    spring.set(value === null ? 0 : Math.min(Math.max(value / max, 0), 1));
  }, [value, max, spring]);
  const dash = useTransform(spring, (v) => CIRC * SWEEP * v);
  const dashArray = useTransform(dash, (d) => `${d} ${CIRC}`);

  return (
    <div className="flex flex-col items-center">
      <div className="relative w-[124px] h-[124px]">
        <svg viewBox="0 0 124 124" className="w-full h-full -rotate-[225deg]">
          <circle
            cx="62"
            cy="62"
            r={R}
            fill="none"
            stroke="var(--color-card2)"
            strokeWidth="9"
            strokeLinecap="round"
            strokeDasharray={`${CIRC * SWEEP} ${CIRC}`}
          />
          <motion.circle
            cx="62"
            cy="62"
            r={R}
            fill="none"
            stroke={color}
            strokeWidth="9"
            strokeLinecap="round"
            strokeDasharray={dashArray}
            style={{ filter: `drop-shadow(0 0 6px ${color}66)` }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-[26px] font-bold leading-none tracking-tight">
            {value === null ? (
              <span className="text-mute text-lg">n/a</span>
            ) : (
              <CountUp value={value} suffix={suffix} />
            )}
          </span>
          {display && (
            <span className="text-[10.5px] text-mute mt-1 max-w-[90px] truncate">
              {display}
            </span>
          )}
        </div>
      </div>
      <div className="text-[11px] font-semibold tracking-[0.14em] uppercase text-mute mt-1">
        {label}
      </div>
    </div>
  );
}
