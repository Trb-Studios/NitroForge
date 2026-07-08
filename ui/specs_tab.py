"""PC Specs tab: hardware inventory laid out as cards (WMI work off-thread)."""
from __future__ import annotations

import threading

import customtkinter as ctk

from core import system_info as si
from ui import theme


class SpecsTab(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=theme.PAD, pady=(theme.PAD, 0))
        ctk.CTkButton(bar, text="Refresh", width=90, fg_color=theme.ACCENT,
                      hover_color=theme.ACCENT_HOVER,
                      command=self._reload).pack(side="left")
        self._loading = theme.body_label(bar, "  loading hardware info...",
                                         secondary=True)
        self._loading.pack(side="left")
        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.pack(fill="both", expand=True, padx=theme.GAP,
                          pady=theme.GAP)
        self._reload()

    def _reload(self):
        self._loading.configure(text="  loading hardware info...")
        threading.Thread(target=self._gather, daemon=True).start()

    def _gather(self):
        """WMI/cpuinfo are slow -> collect off the UI thread, then render."""
        try:
            data = {
                "cpu": si.get_cpu_static(), "cpu_live": si.get_cpu_live(),
                "gpus": si.get_gpu_static(), "gpu_live": self.app.gpu.live(),
                "ram": si.get_ram_live(), "modules": si.get_ram_modules(),
                "storage": si.get_storage_info(), "monitors": si.get_monitors(),
                "os": si.get_os_info(), "hags": si.hags_enabled(),
                "driver_warning": si.gpu_driver_age_warning(),
            }
        except Exception as exc:
            data = {"error": str(exc)}
        if self.winfo_exists():
            self.after(0, lambda: self._render(data))

    # ------------------------------------------------------------ rendering
    def _card(self, title: str, lines: list[str]) -> None:
        c = theme.card(self._scroll)
        c.pack(fill="x", pady=(0, theme.GAP))
        theme.heading(c, title).pack(fill="x", padx=theme.PAD,
                                     pady=(theme.GAP, 0))
        for line in lines:
            theme.body_label(c, line, secondary=True).pack(
                fill="x", padx=theme.PAD)
        ctk.CTkFrame(c, height=theme.GAP,
                     fg_color="transparent").pack()

    def _render(self, d: dict) -> None:
        for w in self._scroll.winfo_children():
            w.destroy()
        self._loading.configure(text="")
        if "error" in d:
            self._card("Error", [d["error"]])
            return

        cpu, live = d["cpu"], d["cpu_live"]
        self._card("CPU", [
            cpu["name"],
            f"{cpu['physical_cores']} physical / {cpu['logical_cores']} "
            "logical cores",
            f"Base clock: {cpu['base_mhz'] or '?'} MHz    "
            f"Current: {live['current_mhz'] or '?'} MHz    "
            f"Usage now: {live['percent']:.0f}%",
        ])

        gl = d["gpu_live"]
        for g in d["gpus"] or [{"name": "No GPU detected", "vram_mb": None,
                                "driver_version": None}]:
            lines = [g["name"] or "?"]
            vram = g.get("vram_mb")
            if gl["mem_total"]:
                lines.append(f"VRAM: {gl['mem_used']:.0f} / "
                             f"{gl['mem_total']:.0f} MB used")
            elif vram:
                lines.append(f"VRAM: {vram:.0f} MB (load/temp need an NVIDIA "
                             "GPU - Windows has no generic API for others)")
            lines.append("Live load: " + (f"{gl['load']:.0f}%" if gl["load"]
                         is not None else "n/a") + "    Temp: " +
                         (f"{gl['temp']:.0f} C" if gl["temp"] is not None
                          else "n/a (driver-dependent)"))
            if g.get("driver_version"):
                lines.append(f"Driver: {g['driver_version']}")
            if d["driver_warning"]:
                lines.append("! " + d["driver_warning"])
            if d["hags"] is not None:
                lines.append("Hardware-accelerated GPU scheduling: "
                             + ("on" if d["hags"] else "off")
                             + " (change in Windows Graphics settings)")
            self._card("GPU", lines)

        ram = d["ram"]
        lines = [f"{ram['total_gb']:.1f} GB total - {ram['used_gb']:.1f} GB "
                 f"used ({ram['percent']:.0f}%), "
                 f"{ram['available_gb']:.1f} GB available"]
        for m in d["modules"]:
            lines.append(f"{m['slot']}: {m['capacity_gb']:.0f} GB @ "
                         f"{m['speed_mhz'] or '?'} MHz ({m['manufacturer']})")
        self._card("RAM", lines)

        self._card("Storage", [
            f"{s['mount']}  {s['total_gb']:.0f} GB - {s['used_percent']:.0f}% "
            f"used - type: {s['kind']} (best-effort)"
            for s in d["storage"]] or ["No drives found"])

        self._card("Monitors", [
            f"{m['name'] or '?'}: {m['width']} x {m['height']}"
            + (f" @ {m['refresh_hz']} Hz" if m.get("refresh_hz") else "")
            + ("   [primary]" if m["primary"] else "")
            for m in d["monitors"]] or ["No monitors enumerated"])

        o = d["os"]
        self._card("System", [
            f"{o['os']} ({o['machine']})", f"Build: {o['version']}",
            f"Computer: {o['hostname']}",
            "Running as Administrator" if o["admin"] else
            "Not running as Administrator - service and power tweaks are "
            "limited (see README)",
        ])
