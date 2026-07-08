// Small shared building blocks: Card, CountUp, Toggle, Segmented, Modal,
// SeverityCard. All animation springs live here so the app feels coherent.
import { AnimatePresence, motion, useSpring, useTransform } from "motion/react";
import { ReactNode, useEffect } from "react";
import { AlertOctagon, AlertTriangle, CheckCircle2 } from "lucide-react";

export const EASE: [number, number, number, number] = [0.22, 1, 0.36, 1];

export function Card({
  children,
  className = "",
  delay = 0,
}: {
  children: ReactNode;
  className?: string;
  delay?: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, delay, ease: EASE }}
      className={`rounded-2xl bg-card ring-hair p-5 ${className}`}
    >
      {children}
    </motion.div>
  );
}

export function SectionTitle({ children }: { children: ReactNode }) {
  return (
    <div className="text-[11px] font-semibold tracking-[0.14em] uppercase text-mute mb-3">
      {children}
    </div>
  );
}

/** Spring-animated number. */
export function CountUp({
  value,
  decimals = 0,
  suffix = "",
  className = "",
}: {
  value: number | null;
  decimals?: number;
  suffix?: string;
  className?: string;
}) {
  const spring = useSpring(0, { stiffness: 90, damping: 22 });
  useEffect(() => {
    if (value !== null && Number.isFinite(value)) spring.set(value);
  }, [value, spring]);
  const text = useTransform(spring, (v) =>
    value === null ? "--" : v.toFixed(decimals) + suffix,
  );
  return <motion.span className={className}>{text}</motion.span>;
}

export function Toggle({
  on,
  onChange,
  disabled = false,
}: {
  on: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <button
      onClick={() => !disabled && onChange(!on)}
      className={`relative w-11 h-6 shrink-0 rounded-full p-0.5 flex transition-colors duration-200 ${
        on ? "bg-accent" : "bg-card2"
      } ${disabled ? "opacity-40" : "cursor-pointer"}`}
    >
      <motion.div
        layout
        transition={{ type: "spring", stiffness: 550, damping: 32 }}
        className={`w-5 h-5 rounded-full bg-white shadow ${on ? "ml-auto" : ""}`}
      />
    </button>
  );
}

export function Segmented({
  options,
  value,
  onChange,
  id,
}: {
  options: string[];
  value: string;
  onChange: (v: string) => void;
  id: string;
}) {
  return (
    <div className="inline-flex rounded-xl bg-card2 p-1 gap-0.5">
      {options.map((o) => (
        <button
          key={o}
          onClick={() => onChange(o)}
          className={`relative px-3.5 py-1.5 text-[13px] rounded-lg transition-colors cursor-pointer ${
            value === o ? "text-white" : "text-mute hover:text-ink2"
          }`}
        >
          {value === o && (
            <motion.div
              layoutId={`seg-${id}`}
              transition={{ type: "spring", stiffness: 500, damping: 38 }}
              className="absolute inset-0 rounded-lg bg-accent/90"
            />
          )}
          <span className="relative z-10">{o}</span>
        </button>
      ))}
    </div>
  );
}

export function Modal({
  open,
  onClose,
  children,
  width = "w-[420px]",
}: {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
  width?: string;
}) {
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.18 }}
          onClick={onClose}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-[3px]"
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.92, y: 14 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 8 }}
            transition={{ type: "spring", stiffness: 380, damping: 30 }}
            onClick={(e) => e.stopPropagation()}
            className={`${width} max-w-[92vw] max-h-[84vh] overflow-y-auto rounded-2xl bg-card ring-hair p-6 shadow-2xl`}
          >
            {children}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export function Button({
  children,
  onClick,
  kind = "primary",
  className = "",
  disabled = false,
}: {
  children: ReactNode;
  onClick?: () => void;
  kind?: "primary" | "ghost" | "danger";
  className?: string;
  disabled?: boolean;
}) {
  const styles = {
    primary: "bg-accent hover:bg-accent2 text-white",
    ghost: "bg-card2 hover:bg-[#2e2e2c] text-ink2",
    danger: "bg-bad/90 hover:bg-bad text-white",
  }[kind];
  return (
    <motion.button
      whileHover={disabled ? undefined : { scale: 1.02 }}
      whileTap={disabled ? undefined : { scale: 0.97 }}
      onClick={disabled ? undefined : onClick}
      className={`px-4 py-2 rounded-xl text-[13px] font-semibold transition-colors ${styles} ${
        disabled ? "opacity-40" : "cursor-pointer"
      } ${className}`}
    >
      {children}
    </motion.button>
  );
}

const SEV_META = {
  ok: { color: "var(--color-ok)", Icon: CheckCircle2, label: "OK" },
  warn: { color: "var(--color-warn)", Icon: AlertTriangle, label: "WARN" },
  bad: { color: "var(--color-bad)", Icon: AlertOctagon, label: "ISSUE" },
} as const;

export function SeverityCard({
  severity,
  title,
  detail,
  delay = 0,
}: {
  severity: "ok" | "warn" | "bad";
  title: string;
  detail: string;
  delay?: number;
}) {
  const meta = SEV_META[severity];
  return (
    <motion.div
      initial={{ opacity: 0, x: -14 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.4, delay, ease: EASE }}
      className="flex gap-3.5 rounded-xl bg-card ring-hair p-4"
    >
      <div
        className="w-1 rounded-full self-stretch shrink-0"
        style={{ background: meta.color }}
      />
      <meta.Icon size={19} className="shrink-0 mt-0.5" style={{ color: meta.color }} />
      <div className="min-w-0">
        <div className="text-[13.5px] font-semibold" style={{ color: meta.color }}>
          {title}
        </div>
        <div className="text-[12.5px] text-ink2 leading-relaxed mt-0.5">{detail}</div>
      </div>
    </motion.div>
  );
}
