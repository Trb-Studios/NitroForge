"""
Better Task Manager: live sortable process table + per-process actions +
a "what's slowing my game" diagnostics panel.

All mutating actions run through process_utils, which refuses OS-critical
and security processes.  Kill and Realtime priority get confirmations.
"""
from __future__ import annotations

from tkinter import messagebox, ttk

import customtkinter as ctk
import psutil

from core import process_utils as pu
from ui import theme

_COLS = ("name", "pid", "cpu", "ram", "disk")
_HEADERS = {"name": "Process", "pid": "PID", "cpu": "CPU %",
            "ram": "RAM %", "disk": "Disk MB/s"}


class TaskManagerTab(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._sort = ("cpu", True)   # column, descending

        diag = theme.card(self)
        diag.pack(fill="x", padx=theme.PAD, pady=(theme.PAD, 0))
        theme.heading(diag, "What's slowing my game").pack(
            fill="x", padx=theme.PAD, pady=(theme.GAP, 0))
        self._diag_lbl = theme.body_label(diag, "analysing...",
                                          secondary=True)
        self._diag_lbl.pack(fill="x", padx=theme.PAD, pady=(0, theme.GAP))

        # ------- actions row
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=theme.PAD, pady=theme.GAP)
        self._prio = ctk.CTkComboBox(bar, values=list(pu.PRIORITY_LEVELS),
                                     width=130, state="readonly")
        self._prio.set("High")
        self._prio.pack(side="left")
        for text, cmd in (("Set priority", self._set_priority),
                          ("Set affinity...", self._set_affinity),
                          ("Suspend", self._suspend),
                          ("Resume", self._resume)):
            ctk.CTkButton(bar, text=text, width=100,
                          command=cmd).pack(side="left", padx=(theme.GAP, 0))
        ctk.CTkButton(bar, text="Kill", width=80, fg_color=theme.SEV["bad"],
                      command=self._kill).pack(side="left", padx=theme.GAP)
        self._action_lbl = theme.body_label(bar, "", secondary=True)
        self._action_lbl.pack(side="left", padx=theme.GAP)

        # ------- table (ttk.Treeview styled for the current mode)
        holder = theme.card(self)
        holder.pack(fill="both", expand=True, padx=theme.PAD,
                    pady=(0, theme.PAD))
        dark = theme.mode() == "dark"
        style = ttk.Style(self)
        style.theme_use("clam")
        bg = "#1a1a19" if dark else "#fcfcfb"
        fg = "#e8e8e3" if dark else "#0b0b0b"
        style.configure("FB.Treeview", background=bg, fieldbackground=bg,
                        foreground=fg, rowheight=24, borderwidth=0,
                        font=(theme.FAMILY, 10))
        style.configure("FB.Treeview.Heading", borderwidth=0,
                        background="#242423" if dark else "#f0efec",
                        foreground="#c3c2b7" if dark else "#52514e",
                        font=(theme.FAMILY, 10, "bold"))
        style.map("FB.Treeview", background=[("selected", "#1c5cab")],
                  foreground=[("selected", "#ffffff")])
        self._tree = ttk.Treeview(holder, columns=_COLS, show="headings",
                                  style="FB.Treeview", selectmode="browse")
        for col in _COLS:
            self._tree.heading(col, text=_HEADERS[col],
                               command=lambda c=col: self._sort_by(c))
            self._tree.column(col, width=90 if col != "name" else 260,
                              anchor="w" if col == "name" else "e")
        vsb = ttk.Scrollbar(holder, orient="vertical",
                            command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True,
                        padx=(theme.GAP, 0), pady=theme.GAP)
        vsb.pack(side="right", fill="y", pady=theme.GAP)

        self.after(600, self._tick)
        self.after(4000, self._diag_tick)

    # ------------------------------------------------------------- refresh
    def _tick(self):
        if not self.winfo_exists():
            return
        rows = pu.list_processes()
        col, desc = self._sort
        key = {"name": lambda r: r["name"].lower(), "pid": lambda r: r["pid"],
               "cpu": lambda r: r["cpu"], "ram": lambda r: r["ram"],
               "disk": lambda r: r["disk_mbs"]}[col]
        rows.sort(key=key, reverse=desc)

        selected = self._tree.selection()
        sel_pid = self._tree.item(selected[0])["values"][1] if selected else None
        self._tree.delete(*self._tree.get_children())
        for r in rows[:250]:
            iid = self._tree.insert("", "end", values=(
                r["name"] + ("  [protected]" if r["protected"] else ""),
                r["pid"], f"{r['cpu']:.1f}", f"{r['ram']:.1f}",
                f"{r['disk_mbs']:.2f}"))
            if r["pid"] == sel_pid:
                self._tree.selection_set(iid)
        self.after(3000, self._tick)

    def _diag_tick(self):
        if not self.winfo_exists():
            return
        try:
            finds = pu.top_offenders()
            ram = psutil.virtual_memory().percent
            if ram > 88:
                finds.insert(0, {"severity": "bad",
                                 "text": f"RAM is {ram:.0f}% full - close "
                                 "apps or expect paging stutter."})
            text = "\n".join(f"- {f['text']}" for f in finds) or \
                "Nothing significant is competing with your game right now."
        except Exception as exc:
            text = f"diagnostics failed: {exc}"
        self._diag_lbl.configure(text=text)
        self.after(8000, self._diag_tick)

    def _sort_by(self, col):
        cur, desc = self._sort
        self._sort = (col, not desc if col == cur else col != "name")

    # ------------------------------------------------------------- actions
    def _selected_pid(self) -> int | None:
        sel = self._tree.selection()
        if not sel:
            self._action_lbl.configure(text="select a process first")
            return None
        return int(self._tree.item(sel[0])["values"][1])

    def _guarded(self, fn, *args, confirm: str | None = None):
        pid = self._selected_pid()
        if pid is None:
            return
        if confirm and not messagebox.askyesno("Confirm", confirm.format(pid=pid)):
            return
        try:
            fn(pid, *args)
            self._action_lbl.configure(text="done", text_color=theme.SEV["ok"])
        except (pu.ProtectedProcessError, PermissionError) as exc:
            self._action_lbl.configure(text=str(exc),
                                       text_color=theme.SEV["warn"])
        except psutil.Error as exc:
            self._action_lbl.configure(text=f"failed: {exc}",
                                       text_color=theme.SEV["warn"])

    def _set_priority(self):
        level = self._prio.get()
        if level == "Realtime" and not messagebox.askyesno(
                "Realtime priority",
                "Realtime can starve Windows itself (audio glitches, input "
                "lag, even hangs). High is almost always the better choice.\n"
                "Set Realtime anyway?"):
            return
        self._guarded(pu.set_priority, level)

    def _suspend(self):
        self._guarded(pu.suspend,
                      confirm="Suspend process {pid}? It will freeze until "
                              "resumed.")

    def _resume(self):
        self._guarded(pu.resume)

    def _kill(self):
        self._guarded(pu.kill,
                      confirm="Kill process {pid}? Unsaved data in it will "
                              "be lost.")

    def _set_affinity(self):
        pid = self._selected_pid()
        if pid is None:
            return
        try:
            current = psutil.Process(pid).cpu_affinity()
        except psutil.Error as exc:
            self._action_lbl.configure(text=f"failed: {exc}")
            return
        ncpu = psutil.cpu_count(logical=True) or 1
        dlg = ctk.CTkToplevel(self)
        dlg.title(f"CPU affinity - pid {pid}")
        dlg.attributes("-topmost", True)
        theme.body_label(dlg, "Pick which logical cores the process may "
                              "run on:").pack(padx=theme.PAD, pady=theme.GAP)
        grid = ctk.CTkFrame(dlg, fg_color="transparent")
        grid.pack(padx=theme.PAD)
        vars_ = []
        for i in range(ncpu):
            v = ctk.BooleanVar(value=i in current)
            vars_.append(v)
            ctk.CTkCheckBox(grid, text=f"Core {i}", variable=v, width=90
                            ).grid(row=i // 4, column=i % 4, sticky="w",
                                   padx=4, pady=4)

        def apply():
            cores = [i for i, v in enumerate(vars_) if v.get()]
            if not cores:
                return
            try:
                pu.set_affinity(pid, cores)
                self._action_lbl.configure(text="affinity set",
                                           text_color=theme.SEV["ok"])
            except (pu.ProtectedProcessError, psutil.Error) as exc:
                self._action_lbl.configure(text=str(exc),
                                           text_color=theme.SEV["warn"])
            dlg.destroy()

        ctk.CTkButton(dlg, text="Apply", fg_color=theme.ACCENT,
                      command=apply).pack(pady=theme.PAD)
