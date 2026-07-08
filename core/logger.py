"""
Central logging.

One shared logger feeds three sinks:
  * a rotating app.log on disk,
  * stderr (useful when run from a terminal),
  * an in-memory ring buffer the Logs tab polls (thread-safe, no callbacks
    into Tk from worker threads).

log_action() is the audit-trail helper: every system-level change the app
makes (registry value, service state, power plan, priority...) must go
through it so the user can always see what changed, old -> new.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import deque
from logging.handlers import RotatingFileHandler

from core import config

_LOCK = threading.Lock()
_RECORDS: deque = deque(maxlen=4000)   # dicts: {"n","ts","level","msg"}
_COUNTER = 0


class _FeedHandler(logging.Handler):
    """Stores records in a ring buffer for the Logs tab to poll."""

    def emit(self, record: logging.LogRecord) -> None:
        global _COUNTER
        with _LOCK:
            _COUNTER += 1
            _RECORDS.append({
                "n": _COUNTER,
                "ts": record.created,
                "level": record.levelname,
                "msg": record.getMessage(),
            })


def get_records(since: int = 0) -> list[dict]:
    """Return all buffered records with sequence number > `since`."""
    with _LOCK:
        return [r for r in _RECORDS if r["n"] > since]


_logger: logging.Logger | None = None


def get_logger() -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger
    lg = logging.getLogger("nitroforge")
    lg.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(message)s",
                            "%H:%M:%S")
    fh = RotatingFileHandler(config.LOG_FILE, maxBytes=1_000_000,
                             backupCount=3, encoding="utf-8")
    fh.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)-7s %(message)s"))
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    feed = _FeedHandler()
    for h in (fh, sh, feed):
        h.setLevel(logging.DEBUG)
        lg.addHandler(h)
    _logger = lg
    lg.info("Logger initialised. Log file: %s", config.LOG_FILE)
    return lg


def log_action(what: str, old, new) -> None:
    """Audit-trail entry for any system-level change."""
    get_logger().info("CHANGE  %s | old=%r -> new=%r", what, old, new)


def ts_str(ts: float) -> str:
    return time.strftime("%H:%M:%S", time.localtime(ts))
