"""
Resolution tab: enumerate/apply display modes + the "gaming resolution
only while a game is running" toggle.

Applying a mode shows a keep/revert countdown (like Windows does) so a bad
mode can never strand the user.
"""
from __future__ import annotations

import customtkinter as ctk

from core import resolution_utils as res
from ui import theme


def _fmt(m):
    return f"{m[0]} x {m[1]}  @ {m[2]} Hz"


class ResolutionTab(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._modes = res.list_modes()
        labels = [_fmt(m) for m in self._modes]

        cur = theme.card(self)
        cur.pack(fill="x", padx=theme.PAD, pady=theme.PAD)
        theme.heading(cur, "Current display mode").pack(fill="x",
                                                        padx=theme.PAD,
                                                        pady=(theme.GAP, 0))
        self._cur_lbl = ctk.CTkLabel(cur, text="?", font=theme.FONT_HERO,
                                     text_color=theme.INK, anchor="w")
        self._cur_lbl.pack(fill="x", padx=theme.PAD, pady=(0, theme.GAP))

        pick = theme.card(self)
        pick.pack(fill="x", padx=theme.PAD)
        theme.heading(pick, "Switch resolution").pack(fill="x", padx=theme.PAD,
                                                      pady=(theme.GAP, 0))
        theme.body_label(
            pick, "Applies instantly with a 15-second keep-or-revert prompt. "
            "Lower resolutions raise FPS at the cost of sharpness.",
            secondary=True).pack(fill="x", padx=theme.PAD)
        row = ctk.CTkFrame(pick, fg_color="transparent")
        row.pack(fill="x", padx=theme.PAD, pady=theme.GAP)
        self._combo = ctk.CTkComboBox(row, values=labels, width=260,
                                      state="readonly")
        if labels:
            self._combo.set(labels[0])
        self._combo.pack(side="left")
        ctk.CTkButton(row, text="Apply", width=90, fg_color=theme.ACCENT,
                      hover_color=theme.ACCENT_HOVER,
                      command=self._apply).pack(side="left", padx=theme.GAP)

        game = theme.card(self)
        game.pack(fill="x", padx=theme.PAD, pady=theme.PAD)
        theme.heading(game, "Gaming resolution").pack(fill="x", padx=theme.PAD,
                                                      pady=(theme.GAP, 0))
        theme.body_label(
            game, "When enabled, launching a game from the Games tab switches "
            "to this resolution and restores your desktop resolution when the "
            "game exits.", secondary=True).pack(fill="x", padx=theme.PAD)
        row2 = ctk.CTkFrame(game, fg_color="transparent")
        row2.pack(fill="x", padx=theme.PAD, pady=theme.GAP)
        self._game_combo = ctk.CTkComboBox(row2, values=labels, width=260,
                                           state="readonly",
                                           command=self._save_game_res)
        saved = app.settings.get("gaming_resolution")
        if saved and _fmt(tuple(saved)) in labels:
            self._game_combo.set(_fmt(tuple(saved)))
        elif labels:
            self._game_combo.set(labels[0])
        self._game_combo.pack(side="left")
        self._toggle = ctk.CTkSwitch(
            row2, text="Only apply while a game is running",
            command=self._save_toggle)
        if app.settings.get("apply_res_on_game"):
            self._toggle.select()
        self._toggle.pack(side="left", padx=theme.PAD)

        self._refresh_current()

    # -------------------------------------------------------------- events
    def _refresh_current(self):
        cur = res.get_current_mode()
        self._cur_lbl.configure(text=_fmt(cur) if cur else "unknown")

    def _selected(self, combo):
        label = combo.get()
        for m in self._modes:
            if _fmt(m) == label:
                return m
        return None

    def _save_toggle(self):
        self.app.settings.set("apply_res_on_game", bool(self._toggle.get()))
        self._save_game_res()

    def _save_game_res(self, *_):
        m = self._selected(self._game_combo)
        if m:
            self.app.settings.set("gaming_resolution", list(m))

    def _apply(self):
        m = self._selected(self._combo)
        old = res.get_current_mode()
        if not m or not old or m == old:
            return
        if not res.set_mode(*m, persist=True):
            self._cur_lbl.configure(text=f"{_fmt(m)} was rejected by the driver")
            return
        self._refresh_current()
        self._keep_or_revert(old)

    def _keep_or_revert(self, old_mode, seconds=15):
        dlg = ctk.CTkToplevel(self)
        dlg.title("Keep display settings?")
        dlg.attributes("-topmost", True)
        dlg.geometry("380x140")
        lbl = theme.body_label(
            dlg, f"Keep the new resolution?\nReverting to {_fmt(old_mode)} "
            f"in {seconds}s if you don't confirm.")
        lbl.pack(padx=theme.PAD, pady=theme.PAD)
        state = {"decided": False, "left": seconds}

        def keep():
            state["decided"] = True
            dlg.destroy()

        def revert():
            state["decided"] = True
            res.set_mode(*old_mode, persist=True)
            self._refresh_current()
            dlg.destroy()

        row = ctk.CTkFrame(dlg, fg_color="transparent")
        row.pack(pady=theme.GAP)
        ctk.CTkButton(row, text="Keep", width=100, fg_color=theme.ACCENT,
                      command=keep).pack(side="left", padx=theme.GAP)
        ctk.CTkButton(row, text="Revert", width=100, fg_color=theme.SEV["bad"],
                      command=revert).pack(side="left")

        def countdown():
            if state["decided"] or not dlg.winfo_exists():
                return
            state["left"] -= 1
            if state["left"] <= 0:
                revert()
                return
            lbl.configure(text=f"Keep the new resolution?\nReverting to "
                               f"{_fmt(old_mode)} in {state['left']}s "
                               "if you don't confirm.")
            dlg.after(1000, countdown)

        dlg.after(1000, countdown)
        dlg.protocol("WM_DELETE_WINDOW", revert)
