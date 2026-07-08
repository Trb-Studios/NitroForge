"""
Power plans, Game Mode / Game Bar registry toggles, visual effects, Windows
services pause/resume, startup apps, fullscreen-optimisation flags.

Every setter returns the OLD value so booster.py can register an exact
revert.  Service control refuses anything matching the security blocklist --
this app never stops or weakens antivirus/security services, full stop.
"""
from __future__ import annotations

import ctypes
import os
import subprocess
import winreg

from core import config
from core.logger import get_logger, log_action

_NOWIN = subprocess.CREATE_NO_WINDOW


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=20,
                          creationflags=_NOWIN)


# -------------------------------------------------------------- power plans
HIGH_PERF_GUID = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
ULTIMATE_GUID = "e9a42b02-d5df-448d-aa00-03f14749eb61"


def get_power_plans() -> list[dict]:
    """[{'guid':..., 'name':..., 'active':bool}] parsed from powercfg /list."""
    plans = []
    out = _run(["powercfg", "/list"]).stdout
    for line in out.splitlines():
        if "GUID" not in line:
            continue
        try:
            guid = line.split(":", 1)[1].split("(")[0].strip()
            name = line.split("(", 1)[1].split(")")[0]
            plans.append({"guid": guid, "name": name,
                          "active": line.rstrip().endswith("*")})
        except IndexError:
            continue
    return plans


def get_active_plan() -> dict | None:
    for p in get_power_plans():
        if p["active"]:
            return p
    return None


def set_power_plan(guid: str) -> bool:
    old = get_active_plan()
    ok = _run(["powercfg", "/setactive", guid]).returncode == 0
    if ok:
        new = next((p["name"] for p in get_power_plans() if p["guid"] == guid), guid)
        log_action("Power plan", old["name"] if old else "?", new)
    return ok


def best_performance_plan() -> dict | None:
    """Prefer Ultimate Performance, then High performance, among installed plans."""
    plans = get_power_plans()
    for guid in (ULTIMATE_GUID, HIGH_PERF_GUID):
        for p in plans:
            if p["guid"].lower() == guid:
                return p
    for p in plans:  # OEM plans often localise the name
        if "high performance" in p["name"].lower() \
                or "ultimate" in p["name"].lower():
            return p
    return None


# ------------------------------------------------------- registry helpers
def _reg_get(root, path, name):
    try:
        with winreg.OpenKey(root, path) as k:
            return winreg.QueryValueEx(k, name)[0]
    except OSError:
        return None


def _reg_set_dword(root, path, name, value) -> None:
    with winreg.CreateKeyEx(root, path, 0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, name, 0, winreg.REG_DWORD, int(value))


_GAMEBAR_KEY = r"Software\Microsoft\GameBar"
_GAMEDVR_KEY = r"Software\Microsoft\Windows\CurrentVersion\GameDVR"
_GAMESTORE_KEY = r"System\GameConfigStore"
_VFX_KEY = r"Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects"
_LAYERS_KEY = r"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers"


def get_game_mode() -> bool:
    val = _reg_get(winreg.HKEY_CURRENT_USER, _GAMEBAR_KEY, "AutoGameModeEnabled")
    return val != 0 if val is not None else True   # Windows default: on


def set_game_mode(enabled: bool) -> bool:
    old = get_game_mode()
    _reg_set_dword(winreg.HKEY_CURRENT_USER, _GAMEBAR_KEY,
                   "AutoGameModeEnabled", 1 if enabled else 0)
    log_action("Windows Game Mode", old, enabled)
    return old


def get_game_bar() -> bool:
    val = _reg_get(winreg.HKEY_CURRENT_USER, _GAMEDVR_KEY, "AppCaptureEnabled")
    return val != 0 if val is not None else True


def set_game_bar(enabled: bool) -> bool:
    """Xbox Game Bar capture/overlay. Returns old state."""
    old = get_game_bar()
    _reg_set_dword(winreg.HKEY_CURRENT_USER, _GAMEDVR_KEY,
                   "AppCaptureEnabled", 1 if enabled else 0)
    _reg_set_dword(winreg.HKEY_CURRENT_USER, _GAMESTORE_KEY,
                   "GameDVR_Enabled", 1 if enabled else 0)
    log_action("Xbox Game Bar capture", old, enabled)
    return old


def get_visual_effects() -> int | None:
    """VisualFXSetting: 0 auto, 1 best appearance, 2 best performance, 3 custom."""
    return _reg_get(winreg.HKEY_CURRENT_USER, _VFX_KEY, "VisualFXSetting")


def set_visual_effects(mode: int) -> int | None:
    """Set 'adjust for best performance' (2) etc. Full effect after re-logon;
    Explorer picks up part of it live. Returns old mode for revert."""
    old = get_visual_effects()
    _reg_set_dword(winreg.HKEY_CURRENT_USER, _VFX_KEY, "VisualFXSetting", mode)
    log_action("Visual effects mode", old, mode)
    return old


# ---------------------------------------------- fullscreen optimisations
def fullscreen_opt_disabled(exe_path: str) -> bool:
    val = _reg_get(winreg.HKEY_CURRENT_USER, _LAYERS_KEY, exe_path)
    return bool(val and "DISABLEDXMAXIMIZEDWINDOWEDMODE" in str(val))


def set_fullscreen_opt_disabled(exe_path: str, disabled: bool) -> None:
    """Per-exe 'Disable fullscreen optimizations' compatibility flag."""
    old = fullscreen_opt_disabled(exe_path)
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, _LAYERS_KEY, 0,
                            winreg.KEY_ALL_ACCESS) as k:
        cur = _reg_get(winreg.HKEY_CURRENT_USER, _LAYERS_KEY, exe_path) or "~"
        flags = [f for f in str(cur).split() if f not in
                 ("~", "DISABLEDXMAXIMIZEDWINDOWEDMODE")]
        if disabled:
            flags.append("DISABLEDXMAXIMIZEDWINDOWEDMODE")
        if flags:
            winreg.SetValueEx(k, exe_path, 0, winreg.REG_SZ,
                              "~ " + " ".join(flags))
        else:
            try:
                winreg.DeleteValue(k, exe_path)
            except OSError:
                pass
    log_action(f"Fullscreen optimizations for {os.path.basename(exe_path)}",
               f"disabled={old}", f"disabled={disabled}")


# ------------------------------------------------------------- services
class SecurityServiceError(PermissionError):
    pass


def _guard_service(name: str) -> None:
    if config.is_security_service(name):
        raise SecurityServiceError(
            f"Service '{name}' looks like security software - this app "
            "never touches security/AV services.")


def service_status(name: str) -> str:
    """'running' | 'stopped' | 'unknown' via `sc query`."""
    out = _run(["sc", "query", name]).stdout.lower()
    if "running" in out:
        return "running"
    if "stopped" in out:
        return "stopped"
    return "unknown"


def stop_service(name: str) -> bool:
    """Stop (pause-for-session) a service. Needs admin. Guarded."""
    _guard_service(name)
    if name not in config.BOOST_SERVICES:
        raise PermissionError(f"'{name}' is not on the boostable-services "
                              "allowlist; refusing to stop it.")
    old = service_status(name)
    if old != "running":
        return False
    ok = _run(["sc", "stop", name]).returncode == 0
    if ok:
        log_action(f"Service {name} ({config.BOOST_SERVICES[name]})",
                   "running", "stopped for boost session")
    else:
        get_logger().warning("Could not stop service %s (admin needed?)", name)
    return ok


def start_service(name: str) -> bool:
    _guard_service(name)
    ok = _run(["sc", "start", name]).returncode == 0
    if ok:
        log_action(f"Service {name}", "stopped", "restarted")
    return ok


# ---------------------------------------------------------- startup apps
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_APPROVED_KEY = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"


def list_startup_apps() -> list[dict]:
    """Current-user startup entries + enabled/disabled state."""
    apps = []
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as k:
            i = 0
            while True:
                try:
                    name, cmd, _ = winreg.EnumValue(k, i)
                    apps.append({"name": name, "command": cmd,
                                 "enabled": _startup_enabled(name)})
                    i += 1
                except OSError:
                    break
    except OSError:
        pass
    return apps


def _startup_enabled(name: str) -> bool:
    val = _reg_get(winreg.HKEY_CURRENT_USER, _APPROVED_KEY, name)
    if isinstance(val, bytes) and val:
        return val[0] % 2 == 0        # even first byte = enabled (0x02/0x06)
    return True


def set_startup_enabled(name: str, enabled: bool) -> None:
    """Toggle a startup app the same way Task Manager's Startup tab does."""
    old = _startup_enabled(name)
    payload = bytes([2 if enabled else 3]) + bytes(11)
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, _APPROVED_KEY, 0,
                            winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, name, 0, winreg.REG_BINARY, payload)
    log_action(f"Startup app '{name}'", f"enabled={old}", f"enabled={enabled}")


# ------------------------------------------------- vendor control panels
def open_gpu_control_panel() -> str | None:
    """Best-effort open of NVIDIA Control Panel / AMD Adrenalin.
    We only *open* the vendor tool - per-app 'Prefer maximum performance' /
    low-latency settings live there and are not scriptable from Python."""
    candidates = [
        (r"C:\Program Files\NVIDIA Corporation\Control Panel Client\nvcplui.exe",
         "NVIDIA Control Panel"),
        (r"C:\Program Files\AMD\CNext\CNext\RadeonSoftware.exe",
         "AMD Radeon Software"),
    ]
    for path, label in candidates:
        if os.path.exists(path):
            subprocess.Popen([path], creationflags=_NOWIN)
            return label
    try:  # NVIDIA CP is a Store app on newer drivers
        os.startfile("shell:AppsFolder\\NVIDIACorp.NVIDIAControlPanel_56jybvy8sckqj!NVIDIACorp.NVIDIAControlPanel")
        return "NVIDIA Control Panel (Store)"
    except OSError:
        return None
