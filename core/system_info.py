"""
Hardware & OS inventory: CPU, GPU, RAM, storage, monitors, OS.

Everything here is read-only and best-effort:
  * NVIDIA GPUs get live load/VRAM/temp via pynvml (or GPUtil).
  * AMD/Intel GPUs fall back to WMI (name/VRAM only -- Windows exposes no
    vendor-neutral load/temperature API, so we say "n/a" rather than fake it).
  * WMI calls are wrapped so they work from background threads (COM needs
    per-thread initialisation).
"""
from __future__ import annotations

import ctypes
import platform
import subprocess
import threading
from datetime import datetime, timedelta
from functools import lru_cache

import psutil

from core.logger import get_logger

_wmi_local = threading.local()

# processes that are never "the game" for FPS auto-targeting
_NON_GAME_FOREGROUND = {
    "nitro-forge.exe", "explorer.exe", "searchhost.exe", "shellexperiencehost.exe",
    "applicationframehost.exe", "startmenuexperiencehost.exe", "dwm.exe",
    "textinputhost.exe", "python.exe", "pythonw.exe", "code.exe", "cmd.exe",
    "powershell.exe", "windowsterminal.exe",
}


def foreground_process_name() -> str | None:
    """Executable name (lowercased) of the window the user is focused on, or
    None if it is the desktop / one of our own / a non-game shell window.

    Used to auto-point the FPS overlay at whatever game is in the foreground.
    """
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return None
        name = psutil.Process(pid.value).name().lower()
        return None if name in _NON_GAME_FOREGROUND else name
    except (psutil.Error, OSError, ValueError):
        return None


def _wmi():
    """Per-thread WMI connection (COM must be initialised per thread)."""
    if getattr(_wmi_local, "conn", None) is None:
        import pythoncom
        import wmi
        pythoncom.CoInitialize()
        _wmi_local.conn = wmi.WMI()
    return _wmi_local.conn


# --------------------------------------------------------------------- CPU
@lru_cache(maxsize=1)
def get_cpu_static() -> dict:
    """Name/cores/base clock. cpuinfo is slow (~1s) -> cached, call off-UI."""
    name = platform.processor()
    base_mhz = None
    try:
        import cpuinfo
        info = cpuinfo.get_cpu_info()
        name = info.get("brand_raw", name)
        hz = info.get("hz_advertised", (0,))
        base_mhz = round(hz[0] / 1e6) if isinstance(hz, (list, tuple)) and hz[0] else None
    except Exception:
        pass
    return {
        "name": name,
        "physical_cores": psutil.cpu_count(logical=False),
        "logical_cores": psutil.cpu_count(logical=True),
        "base_mhz": base_mhz,
    }


def get_cpu_live() -> dict:
    freq = psutil.cpu_freq()
    return {
        "percent": psutil.cpu_percent(interval=None),
        "current_mhz": round(freq.current) if freq else None,
        "per_core": psutil.cpu_percent(interval=None, percpu=True),
    }


# --------------------------------------------------------------------- GPU
class GpuMonitor:
    """Live GPU metrics. NVIDIA via NVML; others get static WMI info only."""

    def __init__(self):
        self._nvml = None
        self._handle = None
        self.vendor = "unknown"
        try:
            import pynvml
            pynvml.nvmlInit()
            self._nvml = pynvml
            self._handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            self.vendor = "nvidia"
        except Exception:
            pass

    def live(self) -> dict:
        """{'load':%|None,'mem_used':MB|None,'mem_total':MB|None,'temp':C|None,'mem_percent':%|None}"""
        out = {"load": None, "mem_used": None, "mem_total": None,
               "temp": None, "mem_percent": None}
        if self._nvml and self._handle:
            try:
                util = self._nvml.nvmlDeviceGetUtilizationRates(self._handle)
                mem = self._nvml.nvmlDeviceGetMemoryInfo(self._handle)
                out["load"] = float(util.gpu)
                out["mem_used"] = mem.used / 1024**2
                out["mem_total"] = mem.total / 1024**2
                out["mem_percent"] = 100.0 * mem.used / mem.total if mem.total else None
                try:
                    out["temp"] = float(self._nvml.nvmlDeviceGetTemperature(
                        self._handle, self._nvml.NVML_TEMPERATURE_GPU))
                except Exception:
                    pass
                return out
            except Exception:
                pass
        try:  # GPUtil fallback (also NVIDIA-only under the hood)
            import GPUtil
            gpus = GPUtil.getGPUs()
            if gpus:
                g = gpus[0]
                out.update(load=g.load * 100, mem_used=g.memoryUsed,
                           mem_total=g.memoryTotal, temp=g.temperature,
                           mem_percent=100 * g.memoryUsed / g.memoryTotal
                           if g.memoryTotal else None)
        except Exception:
            pass
        return out


@lru_cache(maxsize=1)
def get_gpu_static() -> list[dict]:
    """All video controllers via WMI: name, VRAM, driver version/date."""
    gpus = []
    try:
        for vc in _wmi().Win32_VideoController():
            drv_date = None
            try:
                raw = vc.DriverDate  # e.g. 20240115000000.000000-000
                drv_date = datetime.strptime(raw.split(".")[0], "%Y%m%d%H%M%S")
            except Exception:
                pass
            vram_mb = None
            try:
                if vc.AdapterRAM:  # 32-bit field: caps at 4GB, best-effort
                    vram_mb = int(vc.AdapterRAM) / 1024**2
                    if vram_mb < 0:
                        vram_mb += 4096
            except Exception:
                pass
            gpus.append({
                "name": vc.Name,
                "vram_mb": vram_mb,
                "driver_version": vc.DriverVersion,
                "driver_date": drv_date,
            })
    except Exception as exc:
        get_logger().debug("WMI GPU query failed: %s", exc)
    # NVML gives an accurate VRAM total when available (AdapterRAM lies >4GB)
    try:
        import pynvml
        pynvml.nvmlInit()
        h = pynvml.nvmlDeviceGetHandleByIndex(0)
        total = pynvml.nvmlDeviceGetMemoryInfo(h).total / 1024**2
        name = pynvml.nvmlDeviceGetName(h)
        if isinstance(name, bytes):
            name = name.decode()
        for g in gpus:
            if name.lower() in (g["name"] or "").lower() or not gpus:
                g["vram_mb"] = total
        if not gpus:
            gpus.append({"name": name, "vram_mb": total,
                         "driver_version": None, "driver_date": None})
    except Exception:
        pass
    return gpus


def gpu_driver_age_warning() -> str | None:
    """Plain-English note if the newest GPU driver looks > 12 months old."""
    dates = [g["driver_date"] for g in get_gpu_static() if g.get("driver_date")]
    if not dates:
        return None
    newest = max(dates)
    if datetime.now() - newest > timedelta(days=365):
        return (f"GPU driver appears outdated (installed {newest:%Y-%m-%d}). "
                "Updating drivers is one of the highest-impact FPS fixes.")
    return None


# --------------------------------------------------------------------- RAM
def get_ram_live() -> dict:
    vm = psutil.virtual_memory()
    return {"total_gb": vm.total / 1024**3, "used_gb": vm.used / 1024**3,
            "available_gb": vm.available / 1024**3, "percent": vm.percent}


@lru_cache(maxsize=1)
def get_ram_modules() -> list[dict]:
    mods = []
    try:
        for m in _wmi().Win32_PhysicalMemory():
            mods.append({
                "capacity_gb": int(m.Capacity or 0) / 1024**3,
                "speed_mhz": m.Speed,
                "manufacturer": (m.Manufacturer or "?").strip(),
                "slot": m.DeviceLocator,
            })
    except Exception as exc:
        get_logger().debug("WMI RAM query failed: %s", exc)
    return mods


# ----------------------------------------------------------------- Storage
@lru_cache(maxsize=1)
def _physical_disk_types() -> dict[str, str]:
    """Map disk FriendlyName -> 'SSD'/'HDD' via the Storage WMI namespace."""
    types = {}
    try:
        import pythoncom
        import wmi
        pythoncom.CoInitialize()
        st = wmi.WMI(namespace=r"root\Microsoft\Windows\Storage")
        for d in st.MSFT_PhysicalDisk():
            media = {3: "HDD", 4: "SSD", 5: "SCM"}.get(d.MediaType, "Unknown")
            types[d.FriendlyName] = media
    except Exception:
        pass
    return types


def get_storage_info() -> list[dict]:
    drives = []
    disk_types = list(_physical_disk_types().values())
    # best-effort: with one physical disk we can label partitions confidently;
    # with several we report the set of types (mapping partition->disk needs
    # more plumbing than the value it adds).
    uniform = disk_types[0] if len(set(disk_types)) == 1 and disk_types else None
    for part in psutil.disk_partitions(all=False):
        if "cdrom" in part.opts or not part.fstype:
            continue
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except OSError:
            continue
        drives.append({
            "mount": part.mountpoint,
            "total_gb": usage.total / 1024**3,
            "used_percent": usage.percent,
            "kind": uniform or ("/".join(sorted(set(disk_types))) or "Unknown"),
        })
    return drives


# ---------------------------------------------------------------- Monitors
def get_monitors() -> list[dict]:
    mons = []
    try:
        from screeninfo import get_monitors as _sm
        for m in _sm():
            mons.append({"name": m.name, "width": m.width, "height": m.height,
                         "primary": bool(m.is_primary), "refresh_hz": None})
    except Exception:
        pass
    try:  # refresh rate of primary display via EnumDisplaySettingsW
        from core.resolution_utils import get_current_mode
        cur = get_current_mode()
        if cur:
            for m in mons:
                if m["primary"]:
                    m["refresh_hz"] = cur[2]
        if not mons and cur:
            mons.append({"name": "Primary", "width": cur[0], "height": cur[1],
                         "primary": True, "refresh_hz": cur[2]})
    except Exception:
        pass
    return mons


# ---------------------------------------------------------------------- OS
@lru_cache(maxsize=1)
def get_os_info() -> dict:
    uname = platform.uname()
    return {
        "os": f"{uname.system} {uname.release}",
        "version": uname.version,
        "machine": uname.machine,
        "hostname": uname.node,
        "admin": is_admin(),
    }


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def hags_enabled() -> bool | None:
    """Hardware-Accelerated GPU Scheduling registry state (read-only info)."""
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers") as k:
            val, _ = winreg.QueryValueEx(k, "HwSchMode")
            return val == 2
    except OSError:
        return None
