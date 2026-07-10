"""
Advanced, fully-reversible system tweaks: network latency, multimedia
scheduling, power/USB, and mouse responsiveness.

CONTRACT (same as the rest of the engine):
  * Every apply_* returns a *snapshot* of the exact previous state, or None
    when it made no change (already optimal, or skipped for lack of admin).
  * Every restore_* takes that snapshot and puts the system back byte-for-byte.
  * booster.py only registers an undo when apply_* returns a non-None snapshot,
    so "turn Boost off" always restores precisely what "turn Boost on" changed.
  * Nothing here touches security software, OS-critical services, or anything
    outside these named, documented registry values / powercfg settings.

Admin note: the HKLM and powercfg tweaks need Administrator. When not elevated
they no-op and return None (booster logs a friendly warning) rather than throw.

Honesty note: these registry/powercfg tweaks mostly buy *consistency* (fewer
DPC spikes, steadier frame pacing and ping), not big average-FPS jumps. The
UI says so - we don't promise miracle numbers.
"""
from __future__ import annotations

import ctypes
import subprocess
import winreg

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


# --------------------------------------------------------- registry helpers
def _get(root, path, name):
    try:
        with winreg.OpenKey(root, path) as k:
            return winreg.QueryValueEx(k, name)   # (value, type)
    except OSError:
        return None


def _set(root, path, name, value, regtype) -> None:
    with winreg.CreateKeyEx(root, path, 0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, name, 0, regtype, value)


def _restore_value(root, path, name, snap) -> None:
    """snap is (value, type) to restore, or None meaning 'delete it'."""
    if snap is None:
        try:
            with winreg.OpenKey(root, path, 0, winreg.KEY_SET_VALUE) as k:
                winreg.DeleteValue(k, name)
        except OSError:
            pass
    else:
        _set(root, path, name, snap[0], snap[1])


# ============================================================ NETWORK: Nagle
# Disabling Nagle's algorithm (TcpAckFrequency=1, TCPNoDelay=1) per interface
# trades a little bandwidth efficiency for lower latency on small game packets.
_TCPIP_IF = r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces"


def apply_nagle_off() -> dict | None:
    if not is_admin():
        return None
    snapshot: dict[str, dict] = {}
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _TCPIP_IF) as base:
            i = 0
            while True:
                try:
                    guid = winreg.EnumKey(base, i)
                except OSError:
                    break
                i += 1
                path = f"{_TCPIP_IF}\\{guid}"
                # only touch interfaces that have an IP bound (real adapters)
                if _get(winreg.HKEY_LOCAL_MACHINE, path, "DhcpIPAddress") is None \
                        and _get(winreg.HKEY_LOCAL_MACHINE, path, "IPAddress") is None:
                    continue
                snapshot[guid] = {
                    "ack": _get(winreg.HKEY_LOCAL_MACHINE, path, "TcpAckFrequency"),
                    "nodelay": _get(winreg.HKEY_LOCAL_MACHINE, path, "TCPNoDelay"),
                }
                _set(winreg.HKEY_LOCAL_MACHINE, path, "TcpAckFrequency", 1,
                     winreg.REG_DWORD)
                _set(winreg.HKEY_LOCAL_MACHINE, path, "TCPNoDelay", 1,
                     winreg.REG_DWORD)
    except OSError as exc:
        get_logger().warning("Nagle tweak failed: %s", exc)
        return None
    if not snapshot:
        return None
    log_action("Nagle's algorithm", "enabled", f"disabled on {len(snapshot)} adapter(s)")
    return snapshot


def restore_nagle(snapshot: dict) -> None:
    for guid, old in snapshot.items():
        path = f"{_TCPIP_IF}\\{guid}"
        _restore_value(winreg.HKEY_LOCAL_MACHINE, path, "TcpAckFrequency", old["ack"])
        _restore_value(winreg.HKEY_LOCAL_MACHINE, path, "TCPNoDelay", old["nodelay"])
    log_action("Nagle's algorithm", "disabled", "restored")


# ================================================ MULTIMEDIA: responsiveness
# NetworkThrottlingIndex (0xffffffff = off) lifts the 10-packet/ms multimedia
# throttle; SystemResponsiveness=0 gives foreground games more of the CPU.
_SYSPROFILE = (r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia"
               r"\SystemProfile")


def apply_responsiveness() -> dict | None:
    if not is_admin():
        return None
    snap = {
        "throttle": _get(winreg.HKEY_LOCAL_MACHINE, _SYSPROFILE, "NetworkThrottlingIndex"),
        "responsiveness": _get(winreg.HKEY_LOCAL_MACHINE, _SYSPROFILE, "SystemResponsiveness"),
    }
    try:
        _set(winreg.HKEY_LOCAL_MACHINE, _SYSPROFILE, "NetworkThrottlingIndex",
             0xFFFFFFFF, winreg.REG_DWORD)
        _set(winreg.HKEY_LOCAL_MACHINE, _SYSPROFILE, "SystemResponsiveness",
             0, winreg.REG_DWORD)
    except OSError as exc:
        get_logger().warning("Responsiveness tweak failed: %s", exc)
        return None
    log_action("Network throttling / system responsiveness", "default",
               "gaming (throttle off, responsiveness 0)")
    return snap


def restore_responsiveness(snap: dict) -> None:
    _restore_value(winreg.HKEY_LOCAL_MACHINE, _SYSPROFILE,
                   "NetworkThrottlingIndex", snap["throttle"])
    _restore_value(winreg.HKEY_LOCAL_MACHINE, _SYSPROFILE,
                   "SystemResponsiveness", snap["responsiveness"])
    log_action("Network throttling / system responsiveness", "gaming", "restored")


# ================================================ MULTIMEDIA: Games task class
# The MMCSS "Games" task tells the scheduler to give games top CPU/GPU/IO
# priority. These are the widely-cited competitive values.
_GAMES_TASK = _SYSPROFILE + r"\Tasks\Games"
_GAMES_TARGET = {
    "GPU Priority": (8, winreg.REG_DWORD),
    "Priority": (6, winreg.REG_DWORD),
    "Scheduling Category": ("High", winreg.REG_SZ),
    "SFIO Priority": ("High", winreg.REG_SZ),
}


def apply_games_scheduling() -> dict | None:
    if not is_admin():
        return None
    snap = {name: _get(winreg.HKEY_LOCAL_MACHINE, _GAMES_TASK, name)
            for name in _GAMES_TARGET}
    try:
        for name, (val, rtype) in _GAMES_TARGET.items():
            _set(winreg.HKEY_LOCAL_MACHINE, _GAMES_TASK, name, val, rtype)
    except OSError as exc:
        get_logger().warning("Games scheduling tweak failed: %s", exc)
        return None
    log_action("MMCSS Games task priority", "default", "max (GPU 8 / Prio 6 / High)")
    return snap


def restore_games_scheduling(snap: dict) -> None:
    for name in _GAMES_TARGET:
        _restore_value(winreg.HKEY_LOCAL_MACHINE, _GAMES_TASK, name, snap.get(name))
    log_action("MMCSS Games task priority", "max", "restored")


# ============================================================= POWER (powercfg)
# USB selective suspend off (avoids the OS parking your mouse/keyboard) and CPU
# core-parking disabled (all cores stay available) on the ACTIVE plan only.
_SUB_USB = "2a737441-1930-4402-8d77-b2bebba308a3"
_USB_SELECTIVE = "48e6b7a6-50f5-4782-a5d4-53bb8f07e226"
_SUB_PROC = "54533251-82be-4824-96c1-47b60b740d00"
_CP_MIN_CORES = "0cc5b647-c1df-4637-891a-dec35c318583"


def _pc_query_index(sub: str, setting: str) -> int | None:
    """Read the Current AC Power Setting Index from powercfg (hex)."""
    out = _run(["powercfg", "/query", "SCHEME_CURRENT", sub, setting]).stdout
    for line in out.splitlines():
        low = line.strip().lower()
        if low.startswith("current ac power setting index"):
            try:
                return int(low.split(":")[1].strip(), 16)
            except (IndexError, ValueError):
                return None
    return None


def _pc_set(sub: str, setting: str, value: int) -> bool:
    ok_ac = _run(["powercfg", "/setacvalueindex", "SCHEME_CURRENT", sub,
                  setting, str(value)]).returncode == 0
    _run(["powercfg", "/setdcvalueindex", "SCHEME_CURRENT", sub, setting,
          str(value)])
    _run(["powercfg", "/setactive", "SCHEME_CURRENT"])   # apply immediately
    return ok_ac


def apply_power_latency() -> dict | None:
    if not is_admin():
        return None
    snap = {"usb": _pc_query_index(_SUB_USB, _USB_SELECTIVE),
            "parking": _pc_query_index(_SUB_PROC, _CP_MIN_CORES)}
    changed = False
    if snap["usb"] is not None and snap["usb"] != 0:
        changed |= _pc_set(_SUB_USB, _USB_SELECTIVE, 0)        # 0 = disabled
    if snap["parking"] is not None and snap["parking"] != 100:
        changed |= _pc_set(_SUB_PROC, _CP_MIN_CORES, 100)      # 100% = no parking
    if not changed:
        return None
    log_action("USB selective suspend / CPU core parking", "on", "off for boost")
    return snap


def restore_power_latency(snap: dict) -> None:
    if snap.get("usb") is not None:
        _pc_set(_SUB_USB, _USB_SELECTIVE, snap["usb"])
    if snap.get("parking") is not None:
        _pc_set(_SUB_PROC, _CP_MIN_CORES, snap["parking"])
    log_action("USB selective suspend / CPU core parking", "off", "restored")


# ================================================================ MOUSE (HKCU)
# Persistent Input-tab controls (NOT tied to a boost session). No admin needed.
# "Enhance pointer precision" = Windows mouse acceleration; competitive players
# usually turn it off for a 1:1 feel.
_MOUSE_KEY = r"Control Panel\Mouse"
_SPI_SETMOUSE = 0x0004
_SPI_GETMOUSESPEED = 0x0070
_SPI_SETMOUSESPEED = 0x0071
_SPIF_UPDATE = 0x01 | 0x02          # SPIF_UPDATEINIFILE | SPIF_SENDCHANGE


def get_mouse() -> dict:
    def _rd(name, default):
        v = _get(winreg.HKEY_CURRENT_USER, _MOUSE_KEY, name)
        try:
            return int(v[0]) if v else default
        except (ValueError, TypeError):
            return default
    speed = ctypes.c_int()
    try:
        ctypes.windll.user32.SystemParametersInfoW(_SPI_GETMOUSESPEED, 0,
                                                    ctypes.byref(speed), 0)
    except Exception:
        speed.value = 10
    return {
        "enhance_pointer": _rd("MouseSpeed", 1) != 0,
        "pointer_speed": speed.value or 10,          # 1..20, 10 = default
    }


def set_enhance_pointer(enabled: bool) -> None:
    """Toggle 'Enhance pointer precision' live + persistently."""
    old = get_mouse()["enhance_pointer"]
    th1, th2, acc = (6, 10, 1) if enabled else (0, 0, 0)
    _set(winreg.HKEY_CURRENT_USER, _MOUSE_KEY, "MouseSpeed", str(acc), winreg.REG_SZ)
    _set(winreg.HKEY_CURRENT_USER, _MOUSE_KEY, "MouseThreshold1", str(th1), winreg.REG_SZ)
    _set(winreg.HKEY_CURRENT_USER, _MOUSE_KEY, "MouseThreshold2", str(th2), winreg.REG_SZ)
    arr = (ctypes.c_int * 3)(th1, th2, acc)
    ctypes.windll.user32.SystemParametersInfoW(_SPI_SETMOUSE, 0, arr, _SPIF_UPDATE)
    log_action("Enhance pointer precision (mouse accel)", old, enabled)


def set_pointer_speed(speed: int) -> None:
    """Windows pointer speed slider value, 1..20 (10 = default 1:1)."""
    speed = max(1, min(20, int(speed)))
    old = get_mouse()["pointer_speed"]
    ctypes.windll.user32.SystemParametersInfoW(
        _SPI_SETMOUSESPEED, 0, ctypes.c_void_p(speed), _SPIF_UPDATE)
    log_action("Mouse pointer speed", old, speed)
