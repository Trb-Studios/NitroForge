"""
SQLite storage for historical performance samples + the background sampler
thread that feeds it.

The sampler collects CPU/RAM/GPU/FPS every SAMPLE_INTERVAL_SEC and inserts a
row; the Analytics tab queries windows of it (hour/day/week).  One connection
with check_same_thread=False guarded by a lock keeps things simple and safe.
"""
from __future__ import annotations

import sqlite3
import threading
import time
from typing import Callable, Optional

from core import config
from core.logger import get_logger

_SCHEMA = """
CREATE TABLE IF NOT EXISTS samples (
    ts        REAL NOT NULL,
    cpu       REAL,
    ram       REAL,
    gpu       REAL,
    gpu_mem   REAL,
    fps       REAL,
    frametime REAL
);
CREATE INDEX IF NOT EXISTS idx_samples_ts ON samples(ts);
"""


class Database:
    def __init__(self, path=None):
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path or config.DB_FILE),
                                     check_same_thread=False)
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def insert_sample(self, cpu, ram, gpu, gpu_mem, fps, frametime) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO samples VALUES (?,?,?,?,?,?,?)",
                (time.time(), cpu, ram, gpu, gpu_mem, fps, frametime))
            self._conn.commit()

    def query_samples(self, since_sec: float) -> list[tuple]:
        """Rows (ts, cpu, ram, gpu, gpu_mem, fps, frametime) newer than now-since_sec."""
        cutoff = time.time() - since_sec
        with self._lock:
            cur = self._conn.execute(
                "SELECT ts, cpu, ram, gpu, gpu_mem, fps, frametime "
                "FROM samples WHERE ts >= ? ORDER BY ts", (cutoff,))
            return cur.fetchall()

    def summary_stats(self, since_sec: float) -> dict:
        cutoff = time.time() - since_sec
        with self._lock:
            cur = self._conn.execute(
                "SELECT AVG(cpu), AVG(gpu), AVG(fps), MIN(fps), MAX(fps), "
                "AVG(ram), COUNT(*) FROM samples WHERE ts >= ? ", (cutoff,))
            row = cur.fetchone()
        keys = ("avg_cpu", "avg_gpu", "avg_fps", "min_fps", "max_fps",
                "avg_ram", "count")
        return dict(zip(keys, row or [None] * 7))

    def prune(self, keep_days: int = 30) -> None:
        cutoff = time.time() - keep_days * 86400
        with self._lock:
            self._conn.execute("DELETE FROM samples WHERE ts < ?", (cutoff,))
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()


class Sampler:
    """Background thread: pulls live metrics via callables, writes samples."""

    def __init__(self, db: Database,
                 get_sys: Callable[[], tuple],       # -> (cpu%, ram%)
                 get_gpu: Callable[[], tuple],       # -> (load%|None, mem%|None)
                 get_fps: Callable[[], tuple]):      # -> (fps|None, frametime|None)
        self._db = db
        self._get_sys, self._get_gpu, self._get_fps = get_sys, get_gpu, get_fps
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name="sampler")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        log = get_logger()
        self._db.prune()
        while not self._stop.wait(config.SAMPLE_INTERVAL_SEC):
            try:
                cpu, ram = self._get_sys()
                gpu, gpu_mem = self._get_gpu()
                fps, ft = self._get_fps()
                self._db.insert_sample(cpu, ram, gpu, gpu_mem, fps, ft)
            except Exception as exc:      # sampler must never die silently
                log.debug("Sampler tick failed: %s", exc)
