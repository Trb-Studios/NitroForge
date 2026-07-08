"""
Display-mode enumeration and switching via raw user32 calls
(EnumDisplaySettingsW / ChangeDisplaySettingsW).

Modes are (width, height, refresh_hz) tuples for the primary display.
set_mode(persist=False) uses CDS_FULLSCREEN so a "gaming resolution" applied
while a game runs is temporary by nature; persist=True writes the registry
like the Windows display settings page does.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes

from core.logger import get_logger, log_action

ENUM_CURRENT_SETTINGS = 0xFFFFFFFF
CDS_UPDATEREGISTRY = 0x00000001
CDS_TEST = 0x00000002
CDS_FULLSCREEN = 0x00000004
DISP_CHANGE_SUCCESSFUL = 0

DM_BITSPERPEL = 0x00040000
DM_PELSWIDTH = 0x00080000
DM_PELSHEIGHT = 0x00100000
DM_DISPLAYFREQUENCY = 0x00400000


class DEVMODEW(ctypes.Structure):
    _fields_ = [
        ("dmDeviceName", ctypes.c_wchar * 32),
        ("dmSpecVersion", wintypes.WORD),
        ("dmDriverVersion", wintypes.WORD),
        ("dmSize", wintypes.WORD),
        ("dmDriverExtra", wintypes.WORD),
        ("dmFields", wintypes.DWORD),
        ("dmPositionX", wintypes.LONG),
        ("dmPositionY", wintypes.LONG),
        ("dmDisplayOrientation", wintypes.DWORD),
        ("dmDisplayFixedOutput", wintypes.DWORD),
        ("dmColor", ctypes.c_short),
        ("dmDuplex", ctypes.c_short),
        ("dmYResolution", ctypes.c_short),
        ("dmTTOption", ctypes.c_short),
        ("dmCollate", ctypes.c_short),
        ("dmFormName", ctypes.c_wchar * 32),
        ("dmLogPixels", wintypes.WORD),
        ("dmBitsPerPel", wintypes.DWORD),
        ("dmPelsWidth", wintypes.DWORD),
        ("dmPelsHeight", wintypes.DWORD),
        ("dmDisplayFlags", wintypes.DWORD),
        ("dmDisplayFrequency", wintypes.DWORD),
        ("dmICMMethod", wintypes.DWORD),
        ("dmICMIntent", wintypes.DWORD),
        ("dmMediaType", wintypes.DWORD),
        ("dmDitherType", wintypes.DWORD),
        ("dmReserved1", wintypes.DWORD),
        ("dmReserved2", wintypes.DWORD),
        ("dmPanningWidth", wintypes.DWORD),
        ("dmPanningHeight", wintypes.DWORD),
    ]


_user32 = ctypes.windll.user32


def _new_devmode() -> DEVMODEW:
    dm = DEVMODEW()
    dm.dmSize = ctypes.sizeof(DEVMODEW)
    return dm


def get_current_mode() -> tuple[int, int, int] | None:
    dm = _new_devmode()
    if _user32.EnumDisplaySettingsW(None, ENUM_CURRENT_SETTINGS,
                                    ctypes.byref(dm)):
        return (dm.dmPelsWidth, dm.dmPelsHeight, dm.dmDisplayFrequency)
    return None


def list_modes(min_width: int = 800) -> list[tuple[int, int, int]]:
    """All supported (w, h, hz) of the primary display, largest first."""
    modes, i = set(), 0
    dm = _new_devmode()
    while _user32.EnumDisplaySettingsW(None, i, ctypes.byref(dm)):
        if dm.dmPelsWidth >= min_width and dm.dmBitsPerPel >= 32:
            modes.add((dm.dmPelsWidth, dm.dmPelsHeight, dm.dmDisplayFrequency))
        i += 1
    return sorted(modes, key=lambda m: (-m[0], -m[1], -m[2]))


def set_mode(width: int, height: int, hz: int, persist: bool = True) -> bool:
    """Switch the primary display. Returns True on success."""
    old = get_current_mode()
    dm = _new_devmode()
    if not _user32.EnumDisplaySettingsW(None, ENUM_CURRENT_SETTINGS,
                                        ctypes.byref(dm)):
        return False
    dm.dmPelsWidth, dm.dmPelsHeight, dm.dmDisplayFrequency = width, height, hz
    dm.dmFields |= DM_PELSWIDTH | DM_PELSHEIGHT | DM_DISPLAYFREQUENCY

    if _user32.ChangeDisplaySettingsW(ctypes.byref(dm), CDS_TEST) \
            != DISP_CHANGE_SUCCESSFUL:
        get_logger().warning("Display mode %sx%s@%s rejected by CDS_TEST",
                             width, height, hz)
        return False
    flags = CDS_UPDATEREGISTRY if persist else CDS_FULLSCREEN
    res = _user32.ChangeDisplaySettingsW(ctypes.byref(dm), flags)
    ok = res == DISP_CHANGE_SUCCESSFUL
    if ok:
        log_action("Display resolution", old, (width, height, hz))
    else:
        get_logger().error("ChangeDisplaySettingsW failed (code %s)", res)
    return ok


def restore_default() -> None:
    """Return to the registry-stored (normal desktop) mode."""
    _user32.ChangeDisplaySettingsW(None, 0)
    log_action("Display resolution", "temporary mode", "restored desktop default")
