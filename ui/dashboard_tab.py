"""Dashboard: at-a-glance live gauges + one-click boost."""
from __future__ import annotations

import customtkinter as ctk
import psutil

from core import network_utils, power_utils
from ui import theme


class DashboardTab(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app

        tiles = ctk.CTkFrame(self, fg_color="transparent")
        tiles.pack(fill="x", padx=theme.PAD, pady=theme.PAD)
        self._tiles = {}
        for i, key in enumerate(("CPU", "RAM", "GPU", "FPS")):
            tiles.grid_columnconfigure(i, weight=1)
            frame, val = theme.stat_tile(tiles, key)
            frame.grid(row=0, column=i, sticky="nsew",
                       padx=(0 if i == 0 else theme.GAP, 0))
            bar = ctk.CTkProgressBar(frame, progress_color=theme.ACCENT)
            bar.set(0)
            bar.pack(fill="x", padx=theme.PAD, pady=(0, theme.PAD))
            self._tiles[key] = (val, bar)

        status = theme.card(self)
        status.pack(fill="x", padx=theme.PAD)
        self._status_lbl = theme.body_label(status, "Checking system...",
                                            secondary=True)
        self._status_lbl.pack(fill="x", padx=theme.PAD, pady=theme.GAP)

        boost = theme.card(self)
        boost.pack(fill="x", padx=theme.PAD, pady=theme.PAD)
        theme.heading(boost, "Game Booster").pack(fill="x", padx=theme.PAD,
                                                  pady=(theme.GAP, 0))
        self._boost_lbl = theme.body_label(
            boost, "Booster is off. It applies only your enabled, reversible "
            "tweaks - see the Booster tab for full control.", secondary=True)
        self._boost_lbl.pack(fill="x", padx=theme.PAD)
        row = ctk.CTkFrame(boost, fg_color="transparent")
        row.pack(fill="x", padx=theme.PAD, pady=theme.GAP)
        self._boost_btn = ctk.CTkButton(row, text="Boost Now",
                                        fg_color=theme.ACCENT,
                                        hover_color=theme.ACCENT_HOVER,
                                        command=self._toggle_boost)
        self._boost_btn.pack(side="left")

        self._slow_net = None
        self.after(400, self._tick)
        self.after(1500, self._slow_tick)

    # ------------------------------------------------------------- updates
    def _tick(self):
        if not self.winfo_exists():
            return
        cpu = psutil.cpu_percent(None)
        ram = psutil.virtual_memory().percent
        gpu = self.app.gpu.live()
        fps = self.app.fps.current_stats()

        self._set("CPU", f"{cpu:.0f}%", cpu / 100)
        self._set("RAM", f"{ram:.0f}%", ram / 100)
        if gpu["load"] is not None:
            self._set("GPU", f"{gpu['load']:.0f}%", gpu["load"] / 100)
        else:
            self._set("GPU", "n/a", 0)
        if fps["fps"]:
            self._set("FPS", f"{fps['fps']:.0f}", min(fps["fps"] / 240, 1.0))
        else:
            self._set("FPS", "--", 0)

        if self.app.booster.active:
            n = len(self.app.booster.changes())
            game = self.app.booster.boosted_game
            self._boost_lbl.configure(
                text=f"BOOST ACTIVE - {n} change(s) applied"
                     + (f" for {game}" if game else "")
                     + ". Everything reverts automatically.")
            self._boost_btn.configure(text="Undo Boost", fg_color=theme.SEV["warn"])
        else:
            self._boost_lbl.configure(
                text="Booster is off. It applies only your enabled, reversible "
                     "tweaks - see the Booster tab for full control.")
            self._boost_btn.configure(text="Boost Now", fg_color=theme.ACCENT)
        self.after(2000, self._tick)

    def _slow_tick(self):
        if not self.winfo_exists():
            return
        try:
            net = network_utils.get_connection_type()
            plan = power_utils.get_active_plan()
            admin = "Administrator" if power_utils.is_admin() else \
                "NOT admin (some tweaks limited)"
            self._status_lbl.configure(
                text=f"Network: {net['type']}    |    Power plan: "
                     f"{plan['name'] if plan else '?'}    |    {admin}")
        except Exception:
            pass
        self.after(15000, self._slow_tick)

    def _set(self, key, text, frac):
        val, bar = self._tiles[key]
        val.configure(text=text)
        bar.set(max(0.0, min(frac, 1.0)))

    def _toggle_boost(self):
        if self.app.booster.active:
            self.app.booster.revert()
        else:
            self.app.booster.apply()
