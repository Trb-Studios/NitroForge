"""
Task-manager backend: live process table, priority/affinity, suspend/resume/
kill -- every mutating call is guarded by config.is_critical_process(), so
OS-critical and security processes are untouchable by construction.
"""
from __future__ import annotations

import time

import psutil

from core import config
from core.logger import get_logger, log_action

PRIORITY_LEVELS = {
    "Low": psutil.IDLE_PRIORITY_CLASS,
    "Below Normal": psutil.BELOW_NORMAL_PRIORITY_CLASS,
    "Normal": psutil.NORMAL_PRIORITY_CLASS,
    "Above Normal": psutil.ABOVE_NORMAL_PRIORITY_CLASS,
    "High": psutil.HIGH_PRIORITY_CLASS,
    "Realtime": psutil.REALTIME_PRIORITY_CLASS,   # UI warns before using
}
_PRIORITY_NAMES = {v: k for k, v in PRIORITY_LEVELS.items()}

# per-pid caches so cpu_percent() and disk-rate deltas work across refreshes
_procs: dict[int, psutil.Process] = {}
_io_prev: dict[int, tuple[float, int]] = {}
_ncpu = psutil.cpu_count(logical=True) or 1


class ProtectedProcessError(PermissionError):
    """Raised when something asks us to touch a protected process."""


def _guard(proc: psutil.Process) -> None:
    name = proc.name()
    if config.is_critical_process(name):
        raise ProtectedProcessError(
            f"'{name}' is an OS-critical or security process; "
            "this app never modifies it.")


def list_processes() -> list[dict]:
    """Snapshot for the table: name, pid, cpu%, ram%, disk MB/s, priority."""
    rows, seen = [], set()
    now = time.time()
    for p in psutil.process_iter(["pid", "name", "memory_percent"]):
        pid = p.info["pid"]
        seen.add(pid)
        proc = _procs.get(pid)
        if proc is None or proc.pid != pid:
            proc = _procs[pid] = p
            proc.cpu_percent(None)          # prime; first read is 0
        try:
            cpu = proc.cpu_percent(None) / _ncpu
            disk = 0.0
            try:
                io = proc.io_counters()
                total = io.read_bytes + io.write_bytes
                prev = _io_prev.get(pid)
                if prev:
                    disk = max(0.0, (total - prev[1]) / max(now - prev[0], 1e-3))
                _io_prev[pid] = (now, total)
            except (psutil.AccessDenied, AttributeError):
                pass
            rows.append({
                "pid": pid,
                "name": p.info["name"] or "?",
                "cpu": cpu,
                "ram": p.info["memory_percent"] or 0.0,
                "disk_mbs": disk / 1024**2,
                "protected": config.is_critical_process(p.info["name"] or ""),
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    for pid in list(_procs):                # drop dead pids from caches
        if pid not in seen:
            _procs.pop(pid, None)
            _io_prev.pop(pid, None)
    return rows


def get_priority_name(pid: int) -> str:
    try:
        return _PRIORITY_NAMES.get(psutil.Process(pid).nice(), "Normal")
    except psutil.Error:
        return "?"


def set_priority(pid: int, level: str) -> int:
    """Set priority; returns the OLD priority class (for revert)."""
    proc = psutil.Process(pid)
    _guard(proc)
    old = proc.nice()
    proc.nice(PRIORITY_LEVELS[level])
    log_action(f"Priority of {proc.name()} (pid {pid})",
               _PRIORITY_NAMES.get(old, old), level)
    return old


def set_affinity(pid: int, cores: list[int]) -> list[int]:
    """Set CPU affinity; returns the OLD core list (for revert)."""
    proc = psutil.Process(pid)
    _guard(proc)
    old = proc.cpu_affinity()
    proc.cpu_affinity(cores)
    log_action(f"Affinity of {proc.name()} (pid {pid})", old, cores)
    return old


def suspend(pid: int) -> None:
    proc = psutil.Process(pid)
    _guard(proc)
    proc.suspend()
    log_action(f"Process {proc.name()} (pid {pid})", "running", "suspended")


def resume(pid: int) -> None:
    proc = psutil.Process(pid)
    proc.resume()
    log_action(f"Process {proc.name()} (pid {pid})", "suspended", "running")


def kill(pid: int) -> None:
    proc = psutil.Process(pid)
    _guard(proc)
    name = proc.name()
    proc.kill()
    log_action(f"Process {name} (pid {pid})", "running", "killed")


def find_by_names(names: list[str]) -> list[psutil.Process]:
    wanted = {n.lower() for n in names}
    out = []
    for p in psutil.process_iter(["name"]):
        try:
            if (p.info["name"] or "").lower() in wanted:
                out.append(p)
        except psutil.Error:
            continue
    return out


def top_offenders(min_cpu: float = 10.0, min_disk_mbs: float = 15.0,
                  exclude_pid: int | None = None) -> list[dict]:
    """Plain-English 'what's slowing my game' process findings."""
    findings = []
    for row in list_processes():
        if row["pid"] == exclude_pid or row["protected"]:
            continue
        if row["cpu"] >= min_cpu:
            findings.append({
                "severity": "warn" if row["cpu"] < 25 else "bad",
                "text": f"{row['name']} is using {row['cpu']:.0f}% CPU "
                        f"({row['ram']:.1f}% RAM). Consider closing it before gaming.",
            })
        elif row["disk_mbs"] >= min_disk_mbs:
            findings.append({
                "severity": "warn",
                "text": f"{row['name']} is reading/writing "
                        f"{row['disk_mbs']:.0f} MB/s of disk - heavy disk "
                        "activity causes stutter on HDDs.",
            })
    findings.sort(key=lambda f: 0 if f["severity"] == "bad" else 1)
    return findings[:8]
