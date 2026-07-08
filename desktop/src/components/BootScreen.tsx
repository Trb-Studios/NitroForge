// Boot screen: shown until the sidecar answers, so the app never renders
// half-loaded. Logo forges in, wordmark staggers letter by letter, and a
// status line reports real startup progress.
import { motion } from "motion/react";
import { Flame } from "lucide-react";
import { EASE } from "./ui";

const WORD = "NITRO FORGE";

export default function BootScreen({ status }: { status: string }) {
  return (
    <div className="fixed inset-0 z-[90] flex flex-col items-center justify-center bg-bg">
      <motion.div
        initial={{ scale: 0.55, opacity: 0, rotate: -14 }}
        animate={{ scale: 1, opacity: 1, rotate: 0 }}
        transition={{ type: "spring", stiffness: 210, damping: 17 }}
        className="w-20 h-20 rounded-3xl bg-gradient-to-br from-accent to-accent-deep flex items-center justify-center shadow-[0_0_60px_rgba(124,192,244,.45)] animate-pulse-glow"
      >
        <Flame size={40} strokeWidth={2.4} className="text-on-accent" />
      </motion.div>

      <div className="mt-7 flex">
        {WORD.split("").map((ch, i) => (
          <motion.span
            key={i}
            initial={{ opacity: 0, y: 18, filter: "blur(6px)" }}
            animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
            transition={{ delay: 0.25 + i * 0.045, duration: 0.4, ease: EASE }}
            className={`text-[26px] font-bold tracking-[0.3em] ${
              i > 5 ? "text-accent" : "text-ink"
            }`}
          >
            {ch === " " ? " " : ch}
          </motion.span>
        ))}
      </div>

      <motion.div
        initial={{ opacity: 0, scaleX: 0 }}
        animate={{ opacity: 1, scaleX: 1 }}
        transition={{ delay: 0.7, duration: 0.5, ease: EASE }}
        className="mt-8 w-[240px] h-[3px] rounded-full overflow-hidden bg-card2"
      >
        <div
          className="h-full w-full rounded-full animate-shimmer"
          style={{
            background:
              "linear-gradient(90deg, transparent, var(--color-accent), transparent)",
            backgroundSize: "200% 100%",
          }}
        />
      </motion.div>

      <motion.div
        key={status}
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="mt-4 text-[12px] text-mute tracking-wide"
      >
        {status}
      </motion.div>
    </div>
  );
}
