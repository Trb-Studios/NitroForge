"""
Game Booster tab: master toggle, per-sub-feature checkboxes, allowlist
editor, startup-apps manager, and an honest-notes section for things a
desktop app can only advise on (laptop GPU mode, launcher overlays, QoS).

There is deliberately NO control here (or anywhere) that touches
antivirus/security software.
"""
from __future__ import annotations

import shutil
import subprocess
import threading
from tkinter import messagebox

import customtkinter as ctk

from core import config, power_utils
from ui import theme

# (settings_key, label, honest description)
_FEATURES = [
    ("boost_suspend_apps", "Suspend background apps",
     "Freezes only the allowlisted apps below (browsers, cloud sync, RGB "
     "suites). They are resumed on revert - nothing is killed."),
    ("boost_priority", "Raise game priority to High",
     "Windows scheduler favours the game. 'Realtime' is deliberately not "
     "used - it can starve the OS."),
    ("boost_affinity", "CPU affinity tuning (leave core 0 free)",
     "Pins the game to cores 1..N so core 0 stays free for OS/interrupt "
     "work. Helps on some CPUs, neutral on others - off by default."),
    ("boost_power_plan", "High/Ultimate Performance power plan",
     "This is what 'disabling CPU throttling' actually means in practice: "
     "powercfg switches the plan, and your previous plan is restored on "
     "revert."),
    ("boost_game_mode", "Enable Windows Game Mode",
     "Windows' own optimisation (registry toggle). Reverted if we changed it."),
    ("boost_game_bar", "Disable Xbox Game Bar capture/overlay",
     "Removes Game Bar overlay/DVR overhead via its official registry "
     "switches. Steam/GeForce/Adrenalin overlays are third-party apps - "
     "disable those inside each launcher; we won't silently modify them."),
    ("boost_visual_effects", "Reduce Windows visual effects",
     "Sets 'adjust for best performance'. Mostly helps very old PCs; some "
     "of it applies only after you sign out and back in."),
    ("boost_services", "Pause background services",
     "Temporarily stops: " +
     ", ".join(config.BOOST_SERVICES.values()) +
     ". Restarted on revert. Requires Administrator. Security/AV services "
     "are excluded by a hard block in the code, not just by this list."),
]


class BoosterTab(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.pack(fill="both", expand=True, padx=theme.GAP,
                          pady=theme.GAP)

        # ------------ master control
        top = theme.card(self._scroll)
        top.pack(fill="x", pady=(0, theme.GAP))
        theme.heading(top, "Game Booster").pack(fill="x", padx=theme.PAD,
                                                pady=(theme.GAP, 0))
        if not power_utils.is_admin():
            theme.body_label(
                top, "! Not running as Administrator: service pausing and "
                "some power tweaks will be skipped. Restart via the header "
                "button for full functionality.",
                secondary=False).pack(fill="x", padx=theme.PAD)
        row = ctk.CTkFrame(top, fg_color="transparent")
        row.pack(fill="x", padx=theme.PAD, pady=theme.GAP)
        self._master_btn = ctk.CTkButton(row, text="Boost Now", width=140,
                                         height=36, fg_color=theme.ACCENT,
                                         hover_color=theme.ACCENT_HOVER,
                                         font=theme.FONT_HEAD,
                                         command=self._toggle)
        self._master_btn.pack(side="left")
        self._on_launch = ctk.CTkCheckBox(
            row, text="Use when launching games (apply before launch, "
                      "auto-revert when the game exits)",
            command=lambda: app.settings.set(
                "boost_on_launch", bool(self._on_launch.get())))
        if app.settings.get("boost_on_launch"):
            self._on_launch.select()
        self._on_launch.pack(side="left", padx=theme.PAD)

        # ------------ sub-feature toggles
        feats = theme.card(self._scroll)
        feats.pack(fill="x", pady=(0, theme.GAP))
        theme.heading(feats, "What Boost is allowed to do").pack(
            fill="x", padx=theme.PAD, pady=(theme.GAP, 0))
        self._checks = {}
        for key, label, desc in _FEATURES:
            chk = ctk.CTkCheckBox(
                feats, text=label,
                command=lambda k=key: self._save_flag(k))
            if app.settings.get(key):
                chk.select()
            chk.pack(anchor="w", padx=theme.PAD, pady=(theme.GAP, 0))
            self._checks[key] = chk
            ctk.CTkLabel(feats, text=desc, font=theme.FONT_SMALL,
                         text_color=theme.MUTED, anchor="w", justify="left",
                         wraplength=780).pack(fill="x", padx=theme.PAD * 3)
        ctk.CTkFrame(feats, height=theme.GAP,
                     fg_color="transparent").pack()

        # ------------ allowlist editor
        allow = theme.card(self._scroll)
        allow.pack(fill="x", pady=(0, theme.GAP))
        theme.heading(allow, "Background-app allowlist (one process name "
                             "per line)").pack(fill="x", padx=theme.PAD,
                                               pady=(theme.GAP, 0))
        theme.body_label(
            allow, "Only these can ever be suspended. OS-critical and "
            "security processes are refused even if typed here.",
            secondary=True).pack(fill="x", padx=theme.PAD)
        self._allow_box = ctk.CTkTextbox(allow, height=140,
                                         font=theme.FONT_MONO)
        self._allow_box.insert("1.0",
                               "\n".join(app.settings.get("suspend_apps")))
        self._allow_box.pack(fill="x", padx=theme.PAD, pady=theme.GAP)
        ctk.CTkButton(allow, text="Save allowlist", width=120,
                      command=self._save_allowlist).pack(
            anchor="w", padx=theme.PAD, pady=(0, theme.GAP))

        # ------------ startup apps
        st = theme.card(self._scroll)
        st.pack(fill="x", pady=(0, theme.GAP))
        theme.heading(st, "Startup apps (current user)").pack(
            fill="x", padx=theme.PAD, pady=(theme.GAP, 0))
        theme.body_label(
            st, "Disabling stops an app from auto-starting at login - same "
            "switch Task Manager uses, per item, with confirmation.",
            secondary=True).pack(fill="x", padx=theme.PAD)
        self._startup_frame = ctk.CTkFrame(st, fg_color="transparent")
        self._startup_frame.pack(fill="x", padx=theme.PAD, pady=theme.GAP)
        self._render_startup()

        # ------------ honest notes / manual tips
        notes = theme.card(self._scroll)
        notes.pack(fill="x", pady=(0, theme.GAP))
        theme.heading(notes, "Things only you (or your drivers) can do").pack(
            fill="x", padx=theme.PAD, pady=(theme.GAP, 0))
        for txt in (
            "- Laptop hybrid graphics: forcing the discrete GPU is an "
            "NVIDIA Optimus / AMD Switchable Graphics driver setting. Set "
            "'High performance' per game in Windows Graphics settings or "
            "the vendor panel - an app can't safely override it generically.",
            "- Driver tips: in NVIDIA Control Panel set Power management to "
            "'Prefer maximum performance' and Low Latency Mode to 'On/Ultra' "
            "for your game (AMD: Radeon Anti-Lag). Button below opens the "
            "panel if installed.",
            "- Network: pausing cloud-sync apps (allowlist above) frees "
            "bandwidth, but true packet prioritisation (QoS) only exists in "
            "your router settings - no desktop app can do it, whatever the "
            "marketing says.",
            "- In-game settings: shadows, anti-aliasing and post-processing "
            "are the usual FPS hogs. This app won't fake an 'apply' button "
            "for settings that live inside each game.",
        ):
            theme.body_label(notes, txt, secondary=True,
                             wraplength=780).pack(fill="x", padx=theme.PAD)
        row2 = ctk.CTkFrame(notes, fg_color="transparent")
        row2.pack(fill="x", padx=theme.PAD, pady=theme.GAP)
        ctk.CTkButton(row2, text="Open GPU control panel",
                      command=self._open_gpu_panel).pack(side="left")
        self._esl_btn = ctk.CTkButton(row2, text="Clear standby RAM",
                                      command=self._clear_standby)
        esl = shutil.which("EmptyStandbyList.exe") or shutil.which("EmptyStandbyList")
        if esl:
            self._esl_btn.pack(side="left", padx=theme.GAP)
        else:
            theme.body_label(
                row2, "Standby-RAM clearing: Windows has no built-in command "
                "for it; the button appears only if you already have "
                "EmptyStandbyList.exe on your PATH (we don't bundle unknown "
                "binaries).", secondary=True).pack(side="left",
                                                   padx=theme.GAP)

        # ------------ live change list
        ch = theme.card(self._scroll)
        ch.pack(fill="x", pady=(0, theme.GAP))
        theme.heading(ch, "Currently applied changes (auto-reverted)").pack(
            fill="x", padx=theme.PAD, pady=(theme.GAP, 0))
        self._changes_lbl = theme.body_label(ch, "none", secondary=True)
        self._changes_lbl.pack(fill="x", padx=theme.PAD, pady=(0, theme.GAP))
        self.after(1500, self._tick)

    # ------------------------------------------------------------- actions
    def _save_flag(self, key):
        self.app.settings.set(key, bool(self._checks[key].get()))

    def _save_allowlist(self):
        names = [ln.strip() for ln in
                 self._allow_box.get("1.0", "end").splitlines() if ln.strip()]
        blocked = [n for n in names if config.is_critical_process(n)]
        names = [n for n in names if not config.is_critical_process(n)]
        self.app.settings.set("suspend_apps", names)
        if blocked:
            messagebox.showwarning(
                "Some entries refused",
                "These are OS-critical or security processes and were "
                "removed from the list:\n" + "\n".join(blocked))

    def _toggle(self):
        if self.app.booster.active:
            n = self.app.booster.revert()
            messagebox.showinfo("Boost reverted",
                                f"{n} change(s) undone. System restored.")
        else:
            changes = self.app.booster.apply()
            messagebox.showinfo(
                "Boost applied",
                ("\n".join(changes[:12]) or
                 "Nothing needed changing (already optimal or features "
                 "disabled).") +
                ("\n..." if len(changes) > 12 else ""))

    def _tick(self):
        if not self.winfo_exists():
            return
        changes = self.app.booster.changes()
        self._changes_lbl.configure(
            text="\n".join(f"- {c}" for c in changes) if changes else "none")
        self._master_btn.configure(
            text="Undo Boost" if self.app.booster.active else "Boost Now",
            fg_color=theme.SEV["warn"] if self.app.booster.active
            else theme.ACCENT)
        self.after(2000, self._tick)

    # ------------------------------------------------------------- startup
    def _render_startup(self):
        for w in self._startup_frame.winfo_children():
            w.destroy()
        apps = power_utils.list_startup_apps()
        if not apps:
            theme.body_label(self._startup_frame,
                             "No per-user startup entries found.",
                             secondary=True).pack(anchor="w")
        for a in apps:
            row = ctk.CTkFrame(self._startup_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)
            state = "enabled" if a["enabled"] else "disabled"
            ctk.CTkLabel(row, text=f"{a['name']}  ({state})",
                         font=theme.FONT_BODY,
                         text_color=theme.INK if a["enabled"] else theme.MUTED,
                         anchor="w").pack(side="left", fill="x", expand=True)
            ctk.CTkButton(
                row, text="Disable" if a["enabled"] else "Enable", width=80,
                command=lambda a=a: self._toggle_startup(a)).pack(side="right")

    def _toggle_startup(self, app_entry):
        target = not app_entry["enabled"]
        verb = "Disable" if not target else "Enable"
        if not messagebox.askyesno(
                f"{verb} startup app",
                f"{verb} '{app_entry['name']}' at login?\n\n"
                f"Command: {app_entry['command']}"):
            return
        power_utils.set_startup_enabled(app_entry["name"], target)
        self._render_startup()

    def _open_gpu_panel(self):
        opened = power_utils.open_gpu_control_panel()
        if not opened:
            messagebox.showinfo(
                "Not found", "Couldn't find NVIDIA Control Panel or AMD "
                "Radeon Software in their usual locations.")

    def _clear_standby(self):
        exe = shutil.which("EmptyStandbyList.exe") or shutil.which("EmptyStandbyList")
        if not exe:
            return
        def run():
            try:
                subprocess.run([exe, "standbylist"], timeout=30,
                               creationflags=subprocess.CREATE_NO_WINDOW)
                self.app.log.info("Standby RAM cleared via %s", exe)
            except OSError as exc:
                self.app.log.error("EmptyStandbyList failed: %s", exc)
        threading.Thread(target=run, daemon=True).start()
