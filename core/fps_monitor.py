"""
Live FPS / frame-time capture by shelling out to Intel PresentMon.

Honesty note: universal in-game FPS measurement requires hooking the render
API (DX/Vulkan/OpenGL present calls) with an injected native DLL - out of
scope and out of bounds for a Python app.  PresentMon is Intel's free,
signed, open-source frame-timing tool built on Windows ETW; it's the
industry-standard, legitimate way to get real frame times without injecting
into game processes.  The user supplies PresentMon.exe (Overlay tab), we run
it with CSV-to-stdout and parse the stream.

Supports both PresentMon 1.x (-output_stdout, MsBetweenPresents column) and
2.x (--output_stdout, FrameTime column).
"""
from __future__ import annotations

import csv
import os
import subprocess
import threading
import time
from collections import defaultdict, deque

from core.logger import get_logger

_IGNORED_APPS = {"dwm.exe", "explorer.exe", "searchhost.exe", "<unknown>"}
_WINDOW_SEC = 2.0          # rolling window for FPS averaging


class FpsMonitor:
    """Wraps a PresentMon subprocess; exposes rolling FPS/frame-time."""

    def __init__(self, settings, logger=None):
        self._settings = settings
        self._log = logger or get_logger()
        self._proc: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        # per-process rolling frametimes: name -> deque[(wallclock, ft_ms)]
        self._frames: dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.target: str | None = None      # process name filter, if any
        self.auto_target: bool = True        # follow the foreground game
        self.last_error: str | None = None

    # ------------------------------------------------------------ control
    @property
    def running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def configured(self) -> bool:
        path = self._settings.get("presentmon_path", "")
        return bool(path) and os.path.isfile(path)

    def start(self, process_name: str | None = None) -> bool:
        """Start capture. Tries PresentMon 2.x args, falls back to 1.x."""
        if self.running:
            return True
        if not self.configured():
            self.last_error = "PresentMon.exe path is not configured."
            return False
        exe = self._settings.get("presentmon_path")
        # An explicit process disables auto-follow; empty means "track whatever
        # game is in the foreground" (see note_foreground()).
        self.target = process_name
        self.auto_target = not process_name
        for style in ("v2", "v1"):
            args = self._build_args(exe, style, process_name)
            try:
                self._proc = subprocess.Popen(
                    args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                    text=True, bufsize=1,
                    creationflags=subprocess.CREATE_NO_WINDOW)
            except OSError as exc:
                self.last_error = f"Could not start PresentMon: {exc}"
                return False
            time.sleep(1.2)
            if self._proc.poll() is None:       # still alive -> args accepted
                self._stop.clear()
                self._thread = threading.Thread(target=self._reader,
                                                daemon=True, name="presentmon")
                self._thread.start()
                self._log.info("PresentMon started (%s args)%s", style,
                               f" for {process_name}" if process_name else "")
                self.last_error = None
                return True
        self.last_error = ("PresentMon exited immediately - it usually needs "
                           "the app to run as Administrator (ETW access).")
        self._log.warning(self.last_error)
        self._proc = None
        return False

    @staticmethod
    def _build_args(exe: str, style: str, process_name: str | None) -> list:
        p = "--" if style == "v2" else "-"
        args = [exe, f"{p}output_stdout", f"{p}stop_existing_session",
                f"{p}session_name", "nitroforge"]
        if process_name:
            args += [f"{p}process_name", process_name]
        return args

    def stop(self) -> None:
        self._stop.set()
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self._proc = None
        with self._lock:
            self._frames.clear()

    # ------------------------------------------------------------- reader
    def _reader(self) -> None:
        proc = self._proc
        app_idx = ft_idx = None
        try:
            for line in proc.stdout:
                if self._stop.is_set():
                    break
                row = next(csv.reader([line.strip()]), None)
                if not row:
                    continue
                if app_idx is None or "application" in row[0].lower():
                    # header row: locate columns (v1: MsBetweenPresents,
                    # v2: FrameTime); may re-appear if session restarts
                    lows = [c.strip().lower() for c in row]
                    if "application" in lows[0]:
                        app_idx = 0
                        for cand in ("msbetweenpresents", "frametime",
                                     "msbetweendisplaychange"):
                            if cand in lows:
                                ft_idx = lows.index(cand)
                                break
                        continue
                if ft_idx is None or len(row) <= ft_idx:
                    continue
                try:
                    ft = float(row[ft_idx])
                except ValueError:
                    continue
                name = row[app_idx].strip().lower()
                if name in _IGNORED_APPS or ft <= 0:
                    continue
                with self._lock:
                    self._frames[name].append((time.time(), ft))
        except (ValueError, OSError):
            pass

    def note_foreground(self, name: str | None) -> None:
        """Auto-follow the foreground game: if auto-target is on and the
        focused app is actively presenting frames, lock the overlay onto it.
        Only switches to an app PresentMon is already seeing, so alt-tabbing to
        the desktop or a browser never blanks a running game's counter."""
        if not self.auto_target or not name:
            return
        low = name.lower()
        with self._lock:
            has_recent = low in self._frames and self._frames[low]
        if has_recent and self.target != low:
            self.target = low
            self._log.info("FPS overlay now following foreground game: %s", low)

    # -------------------------------------------------------------- stats
    def current_stats(self) -> dict:
        """{'fps':float|None,'frametime_ms':float|None,'process':str|None}"""
        now = time.time()
        best_name, best_frames = None, []
        with self._lock:
            candidates = ([self.target.lower()] if self.target
                          else list(self._frames.keys()))
            for name in candidates:
                dq = self._frames.get(name)
                if not dq:
                    continue
                recent = [ft for (t, ft) in dq if now - t <= _WINDOW_SEC]
                if len(recent) > len(best_frames):
                    best_name, best_frames = name, recent
        if not best_frames:
            return {"fps": None, "frametime_ms": None, "process": None}
        avg_ft = sum(best_frames) / len(best_frames)
        return {"fps": 1000.0 / avg_ft if avg_ft > 0 else None,
                "frametime_ms": avg_ft, "process": best_name}
