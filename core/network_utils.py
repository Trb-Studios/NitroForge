"""
Network diagnostics: Wi-Fi vs wired detection and live throughput.

Honesty note: true packet-level QoS/prioritisation needs router support.
This module only *detects and reports* -- the Booster can pause bandwidth-
heavy background apps (cloud sync etc. via the suspend allowlist), which is
the most a desktop app can legitimately do.
"""
from __future__ import annotations

import subprocess
import time

import psutil

_VIRTUAL_HINTS = ("loopback", "vethernet", "virtual", "vmware", "vpn",
                  "tap", "tun", "bluetooth")


def _run(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=6,
                              creationflags=subprocess.CREATE_NO_WINDOW).stdout
    except Exception:
        return ""


def get_connection_type() -> dict:
    """{'type': 'Wi-Fi'|'Wired'|'Unknown', 'detail': str}"""
    out = _run(["netsh", "wlan", "show", "interfaces"])
    ssid = None
    connected_wifi = False
    for line in out.splitlines():
        line = line.strip()
        if line.lower().startswith("state") and "connected" in line.lower() \
                and "disconnected" not in line.lower():
            connected_wifi = True
        if line.lower().startswith("ssid") and "bssid" not in line.lower():
            ssid = line.split(":", 1)[-1].strip()

    wired_up = False
    stats = psutil.net_if_stats()
    for name, st in stats.items():
        low = name.lower()
        if st.isup and "ethernet" in low and not any(h in low for h in _VIRTUAL_HINTS):
            # an "up" ethernet NIC with a plausible speed = cable plugged in
            if st.speed and st.speed >= 100:
                wired_up = True

    if wired_up:
        return {"type": "Wired", "detail": "Ethernet adapter is up"}
    if connected_wifi:
        return {"type": "Wi-Fi", "detail": f"Connected to '{ssid or '?'}' "
                "- a wired connection gives lower, steadier ping"}
    return {"type": "Unknown", "detail": "No active adapter detected"}


class Throughput:
    """Rolling network throughput from psutil counters."""

    def __init__(self):
        self._last = (time.time(), psutil.net_io_counters())

    def sample(self) -> dict:
        now, io = time.time(), psutil.net_io_counters()
        t0, io0 = self._last
        dt = max(now - t0, 1e-3)
        down = (io.bytes_recv - io0.bytes_recv) / dt
        up = (io.bytes_sent - io0.bytes_sent) / dt
        self._last = (now, io)
        return {"down_mbps": down * 8 / 1e6, "up_mbps": up * 8 / 1e6}
