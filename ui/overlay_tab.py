"""
FPS overlay tab: PresentMon setup + overlay toggle/position/size.

Honesty by design: FPS comes from Intel PresentMon (ETW frame timing), not a
render-API hook.  If it's not configured we explain what it is and where to
get it instead of failing silently.
"""
from __future__ import annotations

import os
from tkinter import filedialog

import customtkinter as ctk

from core import config
from overlay.fps_overlay_window import FpsOverlayWindow
from ui import theme

_CORNERS = ["top-left", "top-right", "bottom-left", "bottom-right"]
_SIZES = ["small", "medium", "large"]


class OverlayTab(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._window: FpsOverlayWindow | None = None

        setup = theme.card(self)
        setup.pack(fill="x", padx=theme.PAD, pady=theme.PAD)
        theme.heading(setup, "PresentMon setup").pack(fill="x", padx=theme.PAD,
                                                      pady=(theme.GAP, 0))
        theme.body_label(
            setup,
            "Real FPS measurement needs frame-timing data from Windows. This "
            "app uses Intel PresentMon - a free, signed, open-source tool and "
            "the industry-standard way overlays measure FPS (no code is "
            "injected into your games).\nDownload PresentMon from:\n"
            f"{config.PRESENTMON_URL}\nthen point the app at PresentMon.exe "
            "below. Run this app as Administrator for capture to work.",
            secondary=True).pack(fill="x", padx=theme.PAD)
        row = ctk.CTkFrame(setup, fg_color="transparent")
        row.pack(fill="x", padx=theme.PAD, pady=theme.GAP)
        self._path_entry = ctk.CTkEntry(row, width=420,
                                        placeholder_text="C:\\...\\PresentMon.exe")
        saved = app.settings.get("presentmon_path", "")
        if saved:
            self._path_entry.insert(0, saved)
        self._path_entry.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(row, text="Browse...", width=90,
                      command=self._browse).pack(side="left", padx=theme.GAP)

        opts = theme.card(self)
        opts.pack(fill="x", padx=theme.PAD)
        theme.heading(opts, "Overlay").pack(fill="x", padx=theme.PAD,
                                            pady=(theme.GAP, 0))
        row2 = ctk.CTkFrame(opts, fg_color="transparent")
        row2.pack(fill="x", padx=theme.PAD, pady=theme.GAP)
        ctk.CTkLabel(row2, text="Corner", font=theme.FONT_SMALL,
                     text_color=theme.MUTED).pack(side="left")
        self._corner = ctk.CTkSegmentedButton(row2, values=_CORNERS,
                                              command=self._recreate)
        self._corner.set(app.settings.get("overlay_corner", "top-left"))
        self._corner.pack(side="left", padx=theme.GAP)
        ctk.CTkLabel(row2, text="Size", font=theme.FONT_SMALL,
                     text_color=theme.MUTED).pack(side="left",
                                                  padx=(theme.PAD, 0))
        self._size = ctk.CTkSegmentedButton(row2, values=_SIZES,
                                            command=self._recreate)
        self._size.set(app.settings.get("overlay_size", "medium"))
        self._size.pack(side="left", padx=theme.GAP)

        self._switch = ctk.CTkSwitch(opts, text="Show FPS overlay "
                                     "(always on top, drag to move)",
                                     command=self._toggle)
        self._switch.pack(anchor="w", padx=theme.PAD, pady=theme.GAP)
        theme.body_label(
            opts, "Note: games in exclusive fullscreen bypass every desktop "
            "overlay (including this one) - use borderless/windowed mode.",
            secondary=True).pack(fill="x", padx=theme.PAD, pady=(0, theme.GAP))

        self._status = theme.body_label(self, "", secondary=True)
        self._status.pack(fill="x", padx=theme.PAD * 2, pady=theme.GAP)
        self.after(1000, self._tick)

    # -------------------------------------------------------------- events
    def _browse(self):
        path = filedialog.askopenfilename(
            title="Locate PresentMon.exe",
            filetypes=[("PresentMon", "*.exe")])
        if path:
            self._path_entry.delete(0, "end")
            self._path_entry.insert(0, path)
            self.app.settings.set("presentmon_path", path)

    def _save_path(self):
        self.app.settings.set("presentmon_path",
                              self._path_entry.get().strip())

    def _toggle(self):
        if self._switch.get():
            self._save_path()
            if not self.app.fps.configured():
                self._switch.deselect()
                self._status.configure(
                    text="PresentMon.exe not found at that path. See the "
                         "setup card above - the overlay needs it.",
                    text_color=theme.SEV["warn"])
                return
            if not self.app.fps.running and not self.app.fps.start():
                self._switch.deselect()
                self._status.configure(text=self.app.fps.last_error or
                                       "PresentMon failed to start.",
                                       text_color=theme.SEV["warn"])
                return
            self._make_window()
        else:
            self._close_window()
            if self.app.fps.running:
                self.app.fps.stop()

    def _make_window(self):
        self._close_window()
        corner, size = self._corner.get(), self._size.get()
        self.app.settings.set("overlay_corner", corner)
        self.app.settings.set("overlay_size", size)
        self._window = FpsOverlayWindow(self.winfo_toplevel(), self.app.fps,
                                        corner=corner, size=size)

    def _recreate(self, *_):
        if self._window:
            self._make_window()

    def _close_window(self):
        if self._window:
            self._window.close()
            self._window = None

    def _tick(self):
        if not self.winfo_exists():
            return
        if self.app.fps.running:
            s = self.app.fps.current_stats()
            if s["fps"]:
                self._status.configure(
                    text=f"Capturing: {s['process']} - {s['fps']:.0f} FPS "
                         f"({s['frametime_ms']:.1f} ms)",
                    text_color=theme.SEV["ok"])
            else:
                self._status.configure(
                    text="PresentMon running - waiting for a 3D app to "
                         "present frames...", text_color=theme.INK_2)
        self.after(1000, self._tick)
