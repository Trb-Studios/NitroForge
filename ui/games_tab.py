"""
Games library: scan launcher folders, launch directly, optional
boost-on-launch and per-game fullscreen-optimization toggle.
"""
from __future__ import annotations

import os
import threading
from tkinter import filedialog, messagebox

import customtkinter as ctk

from core import game_scanner, power_utils
from ui import theme


class GamesTab(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._games: list[game_scanner.Game] = []

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=theme.PAD, pady=(theme.PAD, 0))
        ctk.CTkButton(bar, text="Scan for games", fg_color=theme.ACCENT,
                      hover_color=theme.ACCENT_HOVER,
                      command=self._scan).pack(side="left")
        ctk.CTkButton(bar, text="Add game manually...",
                      command=self._add_manual).pack(side="left",
                                                     padx=theme.GAP)
        self._boost_chk = ctk.CTkCheckBox(
            bar, text="Boost when launching (auto-reverts on exit)",
            command=self._save_boost)
        if app.settings.get("boost_on_launch"):
            self._boost_chk.select()
        self._boost_chk.pack(side="left", padx=theme.PAD)
        self._status = theme.body_label(bar, "", secondary=True)
        self._status.pack(side="left", padx=theme.GAP)

        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.pack(fill="both", expand=True, padx=theme.GAP,
                          pady=theme.GAP)
        self._scan()

    # --------------------------------------------------------------- scan
    def _save_boost(self):
        self.app.settings.set("boost_on_launch", bool(self._boost_chk.get()))

    def _scan(self):
        self._status.configure(text="scanning...")
        threading.Thread(target=self._scan_bg, daemon=True).start()

    def _scan_bg(self):
        try:
            games = game_scanner.scan_all(self.app.settings)
        except Exception as exc:
            games = []
            self.app.log.error("Game scan crashed: %s", exc)
        if self.winfo_exists():
            self.after(0, lambda: self._render(games))

    def _add_manual(self):
        path = filedialog.askopenfilename(
            title="Pick the game's .exe",
            filetypes=[("Executable", "*.exe")])
        if path:
            game_scanner.add_manual_game(self.app.settings, path)
            self._scan()

    # ------------------------------------------------------------- render
    def _render(self, games):
        self._games = games
        self._status.configure(text=f"{len(games)} game(s) found")
        for w in self._scroll.winfo_children():
            w.destroy()
        if not games:
            theme.body_label(
                self._scroll, "No games found in the common Steam / Epic / "
                "GOG / Riot / Xbox folders. Use 'Add game manually...' to "
                "point at any .exe.", secondary=True).pack(pady=theme.PAD)
            return
        for g in games:
            row = theme.card(self._scroll)
            row.pack(fill="x", pady=(0, theme.GAP))
            row.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(row, text=g.name, font=theme.FONT_HEAD,
                         text_color=theme.INK, anchor="w"
                         ).grid(row=0, column=0, sticky="ew", padx=theme.PAD,
                                pady=(theme.GAP, 0))
            exe_note = g.exe if g.exe else "no exe matched - add manually"
            ctk.CTkLabel(row, text=f"{g.source}   -   {exe_note}",
                         font=theme.FONT_SMALL, text_color=theme.MUTED,
                         anchor="w").grid(row=1, column=0, sticky="ew",
                                          padx=theme.PAD, pady=(0, theme.GAP))
            btns = ctk.CTkFrame(row, fg_color="transparent")
            btns.grid(row=0, column=1, rowspan=2, padx=theme.PAD)
            if g.exe:
                fso = ctk.CTkCheckBox(btns, text="Disable fullscreen "
                                                 "optimizations", width=60)
                if power_utils.fullscreen_opt_disabled(g.exe):
                    fso.select()
                fso.configure(command=lambda g=g, c=fso: self._toggle_fso(g, c))
                fso.pack(side="left", padx=theme.GAP)
                ctk.CTkButton(btns, text="Launch", width=90,
                              fg_color=theme.ACCENT,
                              hover_color=theme.ACCENT_HOVER,
                              command=lambda g=g: self._launch(g)
                              ).pack(side="left")

    # ------------------------------------------------------------- actions
    def _toggle_fso(self, game, chk):
        power_utils.set_fullscreen_opt_disabled(game.exe, bool(chk.get()))

    def _launch(self, game):
        boost = self.app.settings.get("boost_on_launch")
        if boost and self.app.booster.active:
            messagebox.showinfo("Boost already active",
                                "A boost session is already running; "
                                "launching without re-applying.")
            boost = False
        if boost or (self.app.settings.get("apply_res_on_game")
                     and self.app.settings.get("gaming_resolution")):
            proc = self.app.booster.boost_and_launch(game)
        else:
            proc = game_scanner.launch(game)
        if proc is None:
            messagebox.showerror(
                "Launch failed",
                f"Could not start {game.name}. If it needs its launcher "
                "(Steam DRM etc.), start it from the launcher instead.")
            return
        # if the overlay is configured, focus capture on this game
        if self.app.fps.running:
            self.app.fps.target = os.path.basename(game.exe).lower()
