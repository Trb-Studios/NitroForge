// Custom frameless-window title bar with drag region + window controls.
import { getCurrentWindow } from "@tauri-apps/api/window";
import { Minus, Square, X, Zap } from "lucide-react";

const win = getCurrentWindow();

export default function TitleBar() {
  return (
    <div
      data-tauri-drag-region
      className="h-10 shrink-0 flex items-center justify-between bg-panel border-b border-line/60 select-none"
    >
      <div data-tauri-drag-region className="flex items-center gap-2.5 px-4 pointer-events-none">
        <div className="w-5 h-5 rounded-md bg-gradient-to-br from-accent to-[#1c5cab] flex items-center justify-center shadow-[0_0_12px_rgba(57,135,229,.5)]">
          <Zap size={12} strokeWidth={2.6} className="text-white" />
        </div>
        <span className="text-[13px] font-semibold tracking-wide text-ink2">
          FPSBooster
        </span>
      </div>
      <div className="flex h-full">
        <button
          onClick={() => win.minimize()}
          className="w-11 h-full flex items-center justify-center text-mute hover:text-ink hover:bg-white/5 transition-colors"
        >
          <Minus size={15} />
        </button>
        <button
          onClick={() => win.toggleMaximize()}
          className="w-11 h-full flex items-center justify-center text-mute hover:text-ink hover:bg-white/5 transition-colors"
        >
          <Square size={12} />
        </button>
        <button
          onClick={() => win.close()}
          className="w-11 h-full flex items-center justify-center text-mute hover:text-white hover:bg-bad transition-colors"
        >
          <X size={15} />
        </button>
      </div>
    </div>
  );
}
