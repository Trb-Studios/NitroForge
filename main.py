"""
FPSBooster - game-focused PC optimizer.

Entry point: builds the window + tab shell, wires shared services
(settings, db, GPU monitor, PresentMon wrapper, Booster), starts the
background history sampler, and guarantees boost revert on exit.

Run as Administrator for full functionality (services, PresentMon ETW).
"""
from __future__ import annotations

import ctypes
import sys
import threading

import customtkinter as ctk
import psutil

from core import config, network_utils, system_info
from core.booster import Booster
from core.db import Database, Sampler
from core.fps_monitor import FpsMonitor
from core.logger import get_logger
from ui import theme
from ui.analytics_tab import AnalyticsTab
from ui.booster_tab import BoosterTab
from ui.bottleneck_tab import BottleneckTab
from ui.dashboard_tab import DashboardTab
from ui.games_tab import GamesTab
from ui.logs_tab import LogsTab
from ui.overlay_tab import OverlayTab
from ui.resolution_tab import ResolutionTab
from ui.specs_tab import SpecsTab
from ui.taskmanager_tab import TaskManagerTab

_TABS = [
    ("Dashboard", DashboardTab),
    ("Booster", BoosterTab),
    ("Games", GamesTab),
    ("Task Manager", TaskManagerTab),
    ("PC Specs", SpecsTab),
    ("Resolution", ResolutionTab),
    ("FPS Overlay", OverlayTab),
    ("Analytics", AnalyticsTab),
    ("Bottleneck", BottleneckTab),
    ("Logs", LogsTab),
]


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("FPSBooster")
        self.geometry("1080x740")
        self.minsize(900, 620)
        self.configure(fg_color=theme.SURFACE)

        # ---- shared services (tabs reach these via self.app.*)
        self.log = get_logger()
        self.settings = config.Settings.load()
        self.db = Database()
        self.gpu = system_info.GpuMonitor()
        self.fps = FpsMonitor(self.settings, self.log)
        self.booster = Booster(self.settings)
        self.sampler = Sampler(
            self.db,
            get_sys=lambda: (psutil.cpu_percent(None),
                             psutil.virtual_memory().percent),
            get_gpu=lambda: (lambda g: (g["load"], g["mem_percent"]))(
                self.gpu.live()),
            get_fps=lambda: (lambda s: (s["fps"], s["frametime_ms"]))(
                self.fps.current_stats()),
        )
        self.sampler.start()

        # ---- header
        header = ctk.CTkFrame(self, fg_color=theme.CARD, corner_radius=0)
        header.pack(fill="x")
        ctk.CTkLabel(header, text="FPSBooster", font=theme.FONT_TITLE,
                     text_color=theme.INK).pack(side="left", padx=theme.PAD,
                                                pady=theme.GAP)
        appearance = ctk.CTkSwitch(header, text="Dark mode",
                                   command=self._toggle_mode)
        if self.settings.get("appearance_mode") == "dark":
            appearance.select()
        appearance.pack(side="right", padx=theme.PAD)
        if not system_info.is_admin():
            ctk.CTkButton(header, text="Restart as Administrator",
                          fg_color=theme.SEV["warn"], text_color="#0b0b0b",
                          command=self._relaunch_admin
                          ).pack(side="right", padx=theme.GAP)
            ctk.CTkLabel(header,
                         text="Limited mode: not running as Administrator",
                         font=theme.FONT_SMALL,
                         text_color=theme.SEV["warn"]).pack(side="right")

        # ---- tabs
        self.tabs = ctk.CTkTabview(self, fg_color=theme.SURFACE,
                                   segmented_button_selected_color=theme.ACCENT)
        self.tabs.pack(fill="both", expand=True, padx=theme.GAP,
                       pady=(0, theme.GAP))
        for name, cls in _TABS:
            frame = self.tabs.add(name)
            cls(frame, self).pack(fill="both", expand=True)

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        threading.Thread(target=self._startup_diagnostics,
                         daemon=True).start()

    # ------------------------------------------------------------- helpers
    def _startup_diagnostics(self):
        """Plain-English health notes into the Logs tab at launch."""
        try:
            net = network_utils.get_connection_type()
            if net["type"] == "Wi-Fi":
                self.log.warning("You're on Wi-Fi, not a wired connection - "
                                 "expect higher/less stable ping. %s",
                                 net["detail"])
            else:
                self.log.info("Network: %s (%s)", net["type"], net["detail"])
            warn = system_info.gpu_driver_age_warning()
            if warn:
                self.log.warning("%s", warn)
            if not system_info.is_admin():
                self.log.warning("Not running as Administrator: pausing "
                                 "services and PresentMon capture will fail. "
                                 "Restart via the header button.")
        except Exception as exc:
            self.log.debug("Startup diagnostics failed: %s", exc)

    def _toggle_mode(self):
        new = "light" if theme.mode() == "dark" else "dark"
        ctk.set_appearance_mode(new)
        self.settings.set("appearance_mode", new)

    def _relaunch_admin(self):
        try:
            script = str((config.APP_DIR / "..").resolve())  # unused; keep argv
            params = " ".join(f'"{a}"' for a in sys.argv)
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable,
                                                params, None, 1)
            self._on_close()
        except Exception as exc:
            self.log.error("Could not relaunch elevated: %s", exc)

    def _on_close(self):
        """Never leave the system half-boosted: revert before exiting.
        (atexit in booster.py is the backstop for hard crashes.)"""
        try:
            self.booster.revert()
            self.fps.stop()
            self.sampler.stop()
            self.db.close()
        finally:
            self.destroy()


def main():
    ctk.set_appearance_mode(config.Settings.load().get("appearance_mode",
                                                       "dark"))
    ctk.set_default_color_theme("blue")
    log = get_logger()
    log.info("FPSBooster starting (admin=%s)", system_info.is_admin())
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
