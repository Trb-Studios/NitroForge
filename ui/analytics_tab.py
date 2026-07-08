"""
Analytics tab: history charts (matplotlib embedded via FigureCanvasTkAgg)
over the sqlite samples the background sampler records.

Chart design follows the validated reference palette: fixed categorical
slots per series (CPU=blue, RAM=aqua, GPU=yellow, FPS=green, frame
time=violet), one axis per chart (FPS and frame time are separate subplots,
never a dual axis), recessive grid, muted inks.
"""
from __future__ import annotations

import math
import time

import customtkinter as ctk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from ui import theme

_WINDOWS = {"Last hour": 3600, "Last day": 86400, "Last week": 604800}


class AnalyticsTab(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=theme.PAD, pady=(theme.PAD, 0))
        self._window = ctk.CTkSegmentedButton(bar, values=list(_WINDOWS),
                                              command=lambda *_: self._refresh())
        self._window.set("Last hour")
        self._window.pack(side="left")
        self._info = theme.body_label(bar, "", secondary=True)
        self._info.pack(side="left", padx=theme.PAD)

        tiles = ctk.CTkFrame(self, fg_color="transparent")
        tiles.pack(fill="x", padx=theme.PAD, pady=theme.GAP)
        self._tiles = {}
        for i, key in enumerate(("Avg FPS", "Min FPS", "Max FPS",
                                 "Avg CPU", "Avg GPU")):
            tiles.grid_columnconfigure(i, weight=1)
            frame, val = theme.stat_tile(tiles, key)
            frame.grid(row=0, column=i, sticky="nsew",
                       padx=(0 if i == 0 else theme.GAP, 0))
            self._tiles[key] = val

        c = theme.CHART[theme.mode()]
        self._fig = Figure(figsize=(8, 6), dpi=100, facecolor=c["surface"])
        self._axes = self._fig.subplots(3, 1, sharex=True)
        self._fig.subplots_adjust(left=0.07, right=0.98, top=0.95,
                                  bottom=0.07, hspace=0.35)
        self._canvas = FigureCanvasTkAgg(self._fig, master=self)
        self._canvas.get_tk_widget().pack(fill="both", expand=True,
                                          padx=theme.PAD,
                                          pady=(0, theme.PAD))
        self._refresh()
        self.after(15000, self._tick)

    def _tick(self):
        if not self.winfo_exists():
            return
        self._refresh()
        self.after(15000, self._tick)

    # ------------------------------------------------------------- drawing
    def _style_axis(self, ax, c, title):
        ax.set_facecolor(c["surface"])
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_color(c["baseline"])
        ax.grid(axis="y", color=c["grid"], linewidth=0.8)
        ax.tick_params(colors=c["muted"], labelsize=8, length=0)
        ax.set_title(title, loc="left", fontsize=9, color=c["muted"])

    # NB: named _refresh, not _draw - CTkFrame uses _draw() internally
    def _refresh(self):
        secs = _WINDOWS[self._window.get()]
        rows = self.app.db.query_samples(secs)
        stats = self.app.db.summary_stats(secs)
        fmt = lambda v, suf="": (f"{v:.0f}{suf}" if v is not None else "--")
        self._tiles["Avg FPS"].configure(text=fmt(stats["avg_fps"]))
        self._tiles["Min FPS"].configure(text=fmt(stats["min_fps"]))
        self._tiles["Max FPS"].configure(text=fmt(stats["max_fps"]))
        self._tiles["Avg CPU"].configure(text=fmt(stats["avg_cpu"], "%"))
        self._tiles["Avg GPU"].configure(text=fmt(stats["avg_gpu"], "%"))
        self._info.configure(
            text=f"{stats['count'] or 0} samples (one every "
                 "3 s while the app runs)")

        c = theme.CHART[theme.mode()]
        self._fig.set_facecolor(c["surface"])
        now = time.time()
        t = [(r[0] - now) / 60 for r in rows]        # minutes ago (negative)
        nan = float("nan")
        col = lambda i: [r[i] if r[i] is not None else nan for r in rows]

        ax0, ax1, ax2 = self._axes
        for ax in self._axes:
            ax.clear()

        self._style_axis(ax0, c, "Utilization %")
        ax0.plot(t, col(1), color=c["cpu"], linewidth=1.8, label="CPU")
        ax0.plot(t, col(2), color=c["ram"], linewidth=1.8, label="RAM")
        if any(not math.isnan(v) for v in col(3)):
            ax0.plot(t, col(3), color=c["gpu"], linewidth=1.8, label="GPU")
        ax0.set_ylim(0, 100)
        leg = ax0.legend(loc="upper left", fontsize=8, frameon=False,
                         ncols=3)
        for txt in leg.get_texts():
            txt.set_color(c["ink"])

        self._style_axis(ax1, c, "FPS (needs PresentMon running)")
        ax1.plot(t, col(5), color=c["fps"], linewidth=1.8)
        ax1.set_ylim(bottom=0)

        self._style_axis(ax2, c, "Frame time, ms (lower + flatter = smoother)")
        ax2.plot(t, col(6), color=c["frametime"], linewidth=1.8)
        ax2.set_ylim(bottom=0)
        ax2.set_xlabel("minutes ago", fontsize=8, color=c["muted"])
        if t:
            ax2.set_xlim(min(t), 0)
        self._canvas.draw_idle()
