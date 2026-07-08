"""
Central configuration: paths, safe allowlists/blocklists, persisted settings.

SAFETY CONTRACT (read before editing):
  * The lists below are the ONLY things the app is allowed to suspend, stop,
    or reprioritise.  Nothing in the codebase may enumerate-and-kill.
  * Antivirus / security software is hard-blocked everywhere.  There is no
    toggle, hidden or otherwise, that weakens security software.  See
    is_security_name() / is_security_service() -- every mutating code path
    must call these guards.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

APP_NAME = "FPSBooster"
APP_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / APP_NAME
APP_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = APP_DIR / "app.log"
DB_FILE = APP_DIR / "history.sqlite3"
SETTINGS_FILE = APP_DIR / "settings.json"

SAMPLE_INTERVAL_SEC = 3.0          # background history sampling cadence
PRESENTMON_URL = "https://github.com/GameTechDev/PresentMon/releases"

# ---------------------------------------------------------------------------
# Processes the Booster MAY suspend during a boost session (user-editable in
# the Booster tab).  Conservative by design: browsers, cloud-sync, RGB suites,
# updaters.  Steam/Battle.net themselves are deliberately absent -- suspending
# the launcher that a running game talks to can crash the game.
# ---------------------------------------------------------------------------
DEFAULT_SUSPEND_APPS = [
    "chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe",
    "OneDrive.exe", "Dropbox.exe", "GoogleDriveFS.exe",
    "Slack.exe", "Teams.exe", "ms-teams.exe", "Spotify.exe",
    "iCUE.exe", "LightingService.exe", "RazerAppEngine.exe",
    "EpicGamesLauncher.exe", "CCXProcess.exe", "AdobeIPCBroker.exe",
    "WhatsApp.exe", "Telegram.exe",
]

# Windows services the Booster may PAUSE (stop for the session, restart on
# revert).  Keyed by service name -> human description.  These are all
# non-security, non-critical background workers.
BOOST_SERVICES = {
    "wuauserv": "Windows Update",
    "WSearch": "Windows Search indexing",
    "SysMain": "SysMain / Superfetch prefetching",
    "MapsBroker": "Downloaded Maps Manager",
    "DoSvc": "Delivery Optimization (update downloads)",
    "DiagTrack": "Connected User Experiences and Telemetry",
}

# ---------------------------------------------------------------------------
# HARD BLOCKS.  Never suspend, kill, reprioritise or otherwise touch these.
# ---------------------------------------------------------------------------
CRITICAL_PROCESSES = {
    "system", "registry", "idle", "memory compression", "smss.exe",
    "csrss.exe", "wininit.exe", "winlogon.exe", "services.exe", "lsass.exe",
    "svchost.exe", "dwm.exe", "explorer.exe", "fontdrvhost.exe",
    "audiodg.exe", "conhost.exe", "sihost.exe", "taskhostw.exe",
    "ctfmon.exe", "runtimebroker.exe", "spoolsv.exe", "dllhost.exe",
    "wudfhost.exe", "ntoskrnl.exe", "python.exe", "pythonw.exe",
}

# Substrings that mark a process OR service as security software.  Matching
# anything here makes it untouchable by every code path in the app.
SECURITY_KEYWORDS = [
    "defender", "msmpeng", "securityhealth", "nissrv", "mpssvc", "sense",
    "wscsvc", "windefend", "smartscreen", "antimalware", "firewall",
    "avast", "avg", "avira", "kaspersky", "mcafee", "norton", "symantec",
    "bitdefender", "eset", "nod32", "malwarebytes", "mbam", "sophos",
    "sentinel", "crowdstrike", "falcon", "cylance", "webroot", "trend",
    "comodo", "fsecure", "f-secure", "panda", "gdata", "drweb", "zonealarm",
]


def is_security_name(name: str) -> bool:
    """True if a process/service name looks like security/AV software."""
    low = (name or "").lower()
    return any(k in low for k in SECURITY_KEYWORDS)


def is_critical_process(name: str) -> bool:
    """True if the process must never be touched (OS-critical or security)."""
    low = (name or "").lower()
    return low in CRITICAL_PROCESSES or is_security_name(low)


def is_security_service(name: str, display_name: str = "") -> bool:
    return is_security_name(name) or is_security_name(display_name)


# Executable name fragments that are almost never the actual game binary.
GAME_EXE_BLACKLIST = [
    "unins", "setup", "install", "updater", "update", "patcher", "repair",
    "crash", "report", "diagnost", "redist", "vcredist", "vc_redist",
    "dxsetup", "dxwebsetup", "dotnet", "easyanticheat", "eac", "battleye",
    "beservice", "anticheat", "cef", "helper", "overlay", "activation",
    "touchup", "unitycrashhandler", "ue4prereq", "ueprereq", "benchmark",
]

DEFAULTS = {
    "presentmon_path": "",
    "custom_games": [],                # [{"name":..., "exe":..., "source":"Manual"}]
    "suspend_apps": DEFAULT_SUSPEND_APPS,
    "boost_on_launch": False,
    # Booster sub-feature toggles
    "boost_suspend_apps": True,
    "boost_priority": True,
    "boost_affinity": False,
    "boost_power_plan": True,
    "boost_game_mode": True,
    "boost_game_bar": True,
    "boost_visual_effects": False,
    "boost_services": True,
    # Resolution feature
    "apply_res_on_game": False,
    "gaming_resolution": None,         # [w, h, hz] or None
    # Overlay
    "overlay_corner": "top-left",
    "overlay_size": "medium",
    "appearance_mode": "dark",
}


class Settings:
    """Tiny JSON-backed settings store shared by all tabs."""

    def __init__(self, data: dict):
        self._data = data

    @classmethod
    def load(cls) -> "Settings":
        data = dict(DEFAULTS)
        try:
            if SETTINGS_FILE.exists():
                data.update(json.loads(SETTINGS_FILE.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            pass  # fall back to defaults; a corrupt file must not brick the app
        return cls(data)

    def save(self) -> None:
        try:
            SETTINGS_FILE.write_text(
                json.dumps(self._data, indent=2), encoding="utf-8")
        except OSError:
            pass

    def get(self, key: str, default=None):
        return self._data.get(key, DEFAULTS.get(key, default))

    def set(self, key: str, value) -> None:
        self._data[key] = value
        self.save()
