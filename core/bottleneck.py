"""
Rule-based "what's holding your rig back" analysis.

Static: compares installed hardware against conservative modern-gaming
baselines and explains anything under-spec in plain English -- deliberately
NOT a fake precise percentage score.

Live: looks at recent CPU%/GPU%/RAM% samples together and says whether the
current session looks CPU-bound, GPU-bound or RAM-limited, and what to do.
Render-settings advice (shadows/AA/etc.) is guidance only: a generic app
cannot and should not force a game's internal graphics settings.
"""
from __future__ import annotations

from dataclasses import dataclass

from core import network_utils, system_info


@dataclass
class Finding:
    severity: str      # "ok" | "warn" | "bad"
    title: str
    detail: str


# Conservative 2026 baselines for comfortable 1080p/1440p gaming.
_MIN_RAM_GB = 16
_MIN_CORES = 6
_MIN_VRAM_GB = 6


def static_findings() -> list[Finding]:
    f: list[Finding] = []

    ram = system_info.get_ram_live()
    if ram["total_gb"] < _MIN_RAM_GB - 0.5:
        f.append(Finding("bad", f"RAM: {ram['total_gb']:.0f} GB installed",
                 f"Modern games comfortably want {_MIN_RAM_GB} GB+. Low RAM "
                 "forces Windows to page to disk mid-game, causing stutter. "
                 "Adding RAM is usually the cheapest big upgrade."))
    else:
        f.append(Finding("ok", f"RAM: {ram['total_gb']:.0f} GB installed",
                 "Meets the comfortable baseline for modern games."))

    cpu = system_info.get_cpu_static()
    cores = cpu["physical_cores"] or 0
    if cores and cores < _MIN_CORES:
        f.append(Finding("warn", f"CPU: {cores} physical cores",
                 f"{cpu['name']} - many recent games scale to {_MIN_CORES}+ "
                 "cores. Expect CPU-bound frame drops in busy scenes."))
    else:
        f.append(Finding("ok", f"CPU: {cpu['name']}",
                 f"{cores} physical / {cpu['logical_cores']} logical cores."))

    gpus = system_info.get_gpu_static()
    if gpus:
        g = gpus[0]
        vram = (g["vram_mb"] or 0) / 1024
        if vram and vram < _MIN_VRAM_GB:
            f.append(Finding("warn", f"GPU: {g['name']} ({vram:.0f} GB VRAM)",
                     f"Under {_MIN_VRAM_GB} GB VRAM means lowering texture "
                     "quality at 1080p+ in recent titles to avoid stutter."))
        else:
            f.append(Finding("ok", f"GPU: {g['name']}",
                     f"{vram:.0f} GB VRAM detected." if vram else
                     "VRAM size could not be read (non-NVIDIA fallback)."))
    else:
        f.append(Finding("warn", "GPU: not detected",
                 "Could not identify a dedicated GPU."))

    drv = system_info.gpu_driver_age_warning()
    if drv:
        f.append(Finding("warn", "GPU driver looks old", drv))

    drives = system_info.get_storage_info()
    hdd_like = [d for d in drives if d["kind"] == "HDD"]
    if hdd_like:
        f.append(Finding("warn", "Mechanical hard drive detected",
                 "Games installed on an HDD load slowly and can hitch while "
                 "streaming assets. Install your main games on an SSD."))
    elif drives:
        f.append(Finding("ok", "Storage",
                 f"{len(drives)} drive(s); type: {drives[0]['kind']} "
                 "(best-effort detection)."))
    full = [d for d in drives if d["used_percent"] > 90]
    if full:
        f.append(Finding("warn",
                 f"Drive {full[0]['mount']} is {full[0]['used_percent']:.0f}% full",
                 "Windows and games need free scratch space; keep 10-15% free."))

    mons = system_info.get_monitors()
    prim = next((m for m in mons if m["primary"]), mons[0] if mons else None)
    if prim and prim.get("refresh_hz"):
        hz = prim["refresh_hz"]
        sev = "ok" if hz >= 120 else "warn" if hz >= 75 else "warn"
        note = ("High-refresh panel - make sure Windows display settings "
                "actually run it at this rate." if hz >= 120 else
                f"Your monitor tops out at {hz} Hz, so FPS beyond {hz} isn't "
                "visible. Smoothness upgrades start with a 120 Hz+ panel.")
        f.append(Finding(sev, f"Monitor: {prim['width']}x{prim['height']} "
                              f"@ {hz} Hz", note))

    net = network_utils.get_connection_type()
    if net["type"] == "Wi-Fi":
        f.append(Finding("warn", "Network: Wi-Fi", net["detail"]))
    elif net["type"] == "Wired":
        f.append(Finding("ok", "Network: Wired", net["detail"]))

    order = {"bad": 0, "warn": 1, "ok": 2}
    f.sort(key=lambda x: order[x.severity])
    return f


def live_findings(samples: list[tuple]) -> list[Finding]:
    """samples: recent (ts,cpu,ram,gpu,gpu_mem,fps,frametime) rows (~5 min)."""
    if len(samples) < 4:
        return [Finding("warn", "Not enough live data yet",
                "Leave the app running (and ideally a game + PresentMon) for "
                "a few minutes, then check back.")]
    cpus = [s[1] for s in samples if s[1] is not None]
    rams = [s[2] for s in samples if s[2] is not None]
    gpus = [s[3] for s in samples if s[3] is not None]
    avg = lambda xs: sum(xs) / len(xs) if xs else None
    a_cpu, a_ram, a_gpu = avg(cpus), avg(rams), avg(gpus)

    f: list[Finding] = []
    if a_ram is not None and a_ram > 90:
        f.append(Finding("bad", f"RAM-limited: {a_ram:.0f}% in use",
                 "Windows is likely paging to disk. Close background apps "
                 "(Booster tab) or add RAM."))
    if a_gpu is not None and a_cpu is not None:
        if a_gpu > 85 and a_cpu < 60:
            f.append(Finding("warn", f"GPU-bound (GPU {a_gpu:.0f}%, CPU {a_cpu:.0f}%)",
                     "Your GPU is the limiter right now. Lower the heaviest "
                     "render settings first: resolution/render scale, shadows, "
                     "anti-aliasing, post-processing. (Advice only - this app "
                     "can't change in-game settings for you.)"))
        elif a_cpu > 80 and a_gpu < 60:
            f.append(Finding("warn", f"CPU-bound (CPU {a_cpu:.0f}%, GPU {a_gpu:.0f}%)",
                     "Your CPU is the limiter. Close background CPU users "
                     "(see Task Manager tab), lower crowd/physics/draw-distance "
                     "settings; raising resolution won't cost FPS here."))
        elif a_gpu > 85 and a_cpu > 80:
            f.append(Finding("warn", "Both CPU and GPU near limits",
                     f"CPU {a_cpu:.0f}%, GPU {a_gpu:.0f}% - the whole system "
                     "is working hard; lower overall quality preset a notch."))
        else:
            f.append(Finding("ok", f"Headroom available (CPU {a_cpu:.0f}%, "
                     f"GPU {a_gpu:.0f}%)",
                     "Nothing looks saturated over the last few minutes."))
    elif a_cpu is not None:
        f.append(Finding("warn" if a_cpu > 80 else "ok",
                 f"CPU average {a_cpu:.0f}%",
                 "GPU load unavailable (non-NVIDIA GPU without NVML) - "
                 "judging CPU only."))
    return f
