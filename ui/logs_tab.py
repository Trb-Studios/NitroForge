"""Logs tab: filterable live feed from the shared logger + export/copy."""
from __future__ import annotations

import shutil
from tkinter import filedialog

import customtkinter as ctk

from core import config, logger as logmod
from ui import theme

_LEVELS = ["All", "Info", "Warning", "Error"]
_LEVEL_MAP = {"Info": ("DEBUG", "INFO"), "Warning": ("WARNING",),
              "Error": ("ERROR", "CRITICAL")}
_TAG_COLOR = {"DEBUG": "#898781", "INFO": None, "WARNING": "#fab219",
              "ERROR": "#d03b3b", "CRITICAL": "#d03b3b"}


class LogsTab(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._records: list[dict] = []
        self._last_n = 0

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=theme.PAD, pady=(theme.PAD, 0))
        self._filter = ctk.CTkSegmentedButton(bar, values=_LEVELS,
                                              command=lambda *_: self._redraw())
        self._filter.set("All")
        self._filter.pack(side="left")
        self._search = ctk.CTkEntry(bar, width=220,
                                    placeholder_text="search...")
        self._search.pack(side="left", padx=theme.GAP)
        self._search.bind("<KeyRelease>", lambda *_: self._redraw())
        ctk.CTkButton(bar, text="Copy", width=70,
                      command=self._copy).pack(side="left", padx=(0, theme.GAP))
        ctk.CTkButton(bar, text="Export log...", width=100,
                      command=self._export).pack(side="left")

        self._box = ctk.CTkTextbox(self, font=theme.FONT_MONO, wrap="none")
        self._box.pack(fill="both", expand=True, padx=theme.PAD,
                       pady=theme.PAD)
        for lvl, color in _TAG_COLOR.items():
            if color:
                self._box.tag_config(lvl, foreground=color)
        self._box.configure(state="disabled")
        self.after(500, self._tick)

    # -------------------------------------------------------------- events
    def _visible(self, rec: dict) -> bool:
        f = self._filter.get()
        if f != "All" and rec["level"] not in _LEVEL_MAP[f]:
            return False
        q = self._search.get().strip().lower()
        return not q or q in rec["msg"].lower()

    def _append(self, rec: dict) -> None:
        line = f"{logmod.ts_str(rec['ts'])} {rec['level']:<7} {rec['msg']}\n"
        self._box.configure(state="normal")
        self._box.insert("end", line, rec["level"])
        self._box.configure(state="disabled")

    def _tick(self):
        if not self.winfo_exists():
            return
        new = logmod.get_records(self._last_n)
        if new:
            self._last_n = new[-1]["n"]
            self._records.extend(new)
            self._records = self._records[-4000:]
            at_bottom = self._box.yview()[1] > 0.95
            for rec in new:
                if self._visible(rec):
                    self._append(rec)
            if at_bottom:
                self._box.see("end")
        self.after(800, self._tick)

    def _redraw(self):
        self._box.configure(state="normal")
        self._box.delete("1.0", "end")
        self._box.configure(state="disabled")
        for rec in self._records:
            if self._visible(rec):
                self._append(rec)
        self._box.see("end")

    def _copy(self):
        text = "\n".join(
            f"{logmod.ts_str(r['ts'])} {r['level']:<7} {r['msg']}"
            for r in self._records if self._visible(r))
        self.clipboard_clear()
        self.clipboard_append(text)

    def _export(self):
        dest = filedialog.asksaveasfilename(
            defaultextension=".log", initialfile="fpsbooster-support.log",
            filetypes=[("Log file", "*.log"), ("All files", "*.*")])
        if dest:
            try:
                shutil.copyfile(config.LOG_FILE, dest)
            except OSError as exc:
                logmod.get_logger().error("Log export failed: %s", exc)
