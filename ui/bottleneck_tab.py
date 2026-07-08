"""
Bottleneck tab: static hardware-vs-baseline findings + live CPU/GPU/RAM
boundedness analysis, both as ranked plain-English cards.
"""
from __future__ import annotations

import threading

import customtkinter as ctk

from core import bottleneck
from ui import theme


class BottleneckTab(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.pack(fill="both", expand=True, padx=theme.GAP,
                          pady=theme.GAP)

        bar = ctk.CTkFrame(self._scroll, fg_color="transparent")
        bar.pack(fill="x")
        theme.heading(bar, "Your hardware vs modern-gaming baselines"
                      ).pack(side="left")
        ctk.CTkButton(bar, text="Re-analyse", width=100,
                      fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                      command=self._run_static).pack(side="right")
        self._static_frame = ctk.CTkFrame(self._scroll,
                                          fg_color="transparent")
        self._static_frame.pack(fill="x", pady=theme.GAP)
        theme.body_label(self._static_frame, "analysing hardware...",
                         secondary=True).pack()

        theme.heading(self._scroll, "Live: what's limiting you right now"
                      ).pack(fill="x", pady=(theme.PAD, 0))
        theme.body_label(
            self._scroll, "Based on the last ~5 minutes of samples. Most "
            "useful while a game is running (FPS needs PresentMon).",
            secondary=True).pack(fill="x")
        self._live_frame = ctk.CTkFrame(self._scroll, fg_color="transparent")
        self._live_frame.pack(fill="x", pady=theme.GAP)

        self._run_static()
        self.after(3000, self._live_tick)

    # -------------------------------------------------------------- static
    def _run_static(self):
        threading.Thread(target=self._static_bg, daemon=True).start()

    def _static_bg(self):
        try:
            finds = bottleneck.static_findings()
        except Exception as exc:
            finds = [bottleneck.Finding("warn", "Analysis failed", str(exc))]
        if self.winfo_exists():
            self.after(0, lambda: self._fill(self._static_frame, finds))

    # ---------------------------------------------------------------- live
    def _live_tick(self):
        if not self.winfo_exists():
            return
        try:
            finds = bottleneck.live_findings(self.app.db.query_samples(300))
        except Exception as exc:
            finds = [bottleneck.Finding("warn", "Live analysis failed",
                                        str(exc))]
        self._fill(self._live_frame, finds)
        self.after(15000, self._live_tick)

    @staticmethod
    def _fill(frame, findings):
        for w in frame.winfo_children():
            w.destroy()
        for f in findings:
            theme.severity_row(frame, f.severity, f.title, f.detail
                               ).pack(fill="x", pady=(0, theme.GAP))
