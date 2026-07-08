"""
Crash, bug and feedback reporting for Nitro Forge.

What it does:
  * install() hooks sys.excepthook / threading.excepthook so any unhandled
    exception produces a structured diagnostic report.
  * Every report is written locally to %LOCALAPPDATA%/NitroForge/crashes/
    (kept to the newest MAX_LOCAL_REPORTS files).
  * If the user configured a Discord webhook and/or a website endpoint in
    Settings, reports are delivered there too (auto-send is opt-in).
  * send_feedback() carries user-typed bug reports / feedback through the
    same pipeline.

Privacy contract:
  * Nothing is ever sent unless the user pasted a webhook/endpoint URL AND
    enabled sending.  Reports contain hardware summary + stack traces + the
    recent log tail - no directory listings, no personal files.
"""
from __future__ import annotations

import json
import platform
import threading
import time
import traceback
import urllib.error
import urllib.request

from core import config
from core import logger as logmod

MAX_LOCAL_REPORTS = 25
_SEND_MIN_INTERVAL = 30.0          # seconds between network deliveries
_last_send = 0.0
_send_lock = threading.Lock()


# ------------------------------------------------------------- report body
def _system_summary() -> dict:
    """Cheap, dependency-light hardware/OS snapshot for reports."""
    info = {
        "app": config.APP_DISPLAY_NAME,
        "version": config.APP_VERSION,
        "os": f"{platform.system()} {platform.release()} ({platform.version()})",
        "machine": platform.machine(),
        "python": platform.python_version(),
    }
    try:
        import psutil
        vm = psutil.virtual_memory()
        info["cpu_count"] = psutil.cpu_count(logical=True)
        info["ram_gb"] = round(vm.total / 1024 ** 3, 1)
    except Exception:
        pass
    return info


def build_report(kind: str, title: str, detail: str,
                 feedback: str = "", contact: str = "") -> dict:
    settings = config.Settings.load()
    report = {
        "kind": kind,                       # crash | bug | feedback | frontend-crash
        "title": title[:200],
        "detail": detail[:8000],
        "feedback": feedback[:2000],
        "contact": contact[:200],
        "ts": time.time(),
        "system": _system_summary(),
    }
    if settings.get("report_include_logs"):
        tail = logmod.get_records(0)[-40:]
        report["log_tail"] = [
            f"{logmod.ts_str(r['ts'])} {r['level']:<7} {r['msg']}" for r in tail
        ]
    return report


# ---------------------------------------------------------------- delivery
def _save_local(report: dict) -> str:
    config.CRASH_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(report["ts"]))
    path = config.CRASH_DIR / f"{report['kind']}-{stamp}.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    # keep the folder bounded
    files = sorted(config.CRASH_DIR.glob("*.json"),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    for old in files[MAX_LOCAL_REPORTS:]:
        try:
            old.unlink()
        except OSError:
            pass
    return str(path)


def _post_json(url: str, payload: dict, timeout: float = 8.0) -> bool:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "User-Agent": f"NitroForge/{config.APP_VERSION}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, OSError, ValueError):
        return False


_KIND_META = {
    "crash": ("Crash Report", 0xD03B3B),
    "frontend-crash": ("UI Crash Report", 0xD03B3B),
    "bug": ("Bug Report", 0xFAB219),
    "feedback": ("Feedback", 0x7CC0F4),
}


def _discord_payload(report: dict) -> dict:
    label, color = _KIND_META.get(report["kind"], ("Report", 0x7CC0F4))
    sysinfo = report["system"]
    fields = [
        {"name": "Version", "value": str(sysinfo.get("version", "?")), "inline": True},
        {"name": "OS", "value": str(sysinfo.get("os", "?"))[:100], "inline": True},
        {"name": "Hardware",
         "value": f"{sysinfo.get('cpu_count', '?')} threads / "
                  f"{sysinfo.get('ram_gb', '?')} GB RAM", "inline": True},
    ]
    if report.get("feedback"):
        fields.append({"name": "User feedback",
                       "value": report["feedback"][:1000] or "-"})
    if report.get("contact"):
        fields.append({"name": "Contact", "value": report["contact"][:200],
                       "inline": True})
    detail = report.get("detail", "")
    embed = {
        "title": f"{label}: {report['title']}"[:250],
        "description": f"```\n{detail[:1800]}\n```" if detail else "-",
        "color": color,
        "fields": fields,
        "footer": {"text": config.APP_DISPLAY_NAME},
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                   time.gmtime(report["ts"])),
    }
    return {"username": f"{config.APP_DISPLAY_NAME} Reporter", "embeds": [embed]}


def deliver(report: dict, force_send: bool = False) -> dict:
    """Save locally, then (rate-limited) push to configured sinks.

    Returns {"saved": path|None, "discord": bool, "site": bool}.
    """
    global _last_send
    settings = config.Settings.load()
    result = {"saved": None, "discord": False, "site": False}

    if settings.get("report_enabled"):
        try:
            result["saved"] = _save_local(report)
        except OSError:
            pass

    should_send = force_send or bool(settings.get("report_auto_send"))
    if not should_send:
        return result
    with _send_lock:
        if time.time() - _last_send < _SEND_MIN_INTERVAL and not force_send:
            return result
        _last_send = time.time()

    webhook = (settings.get("report_discord_webhook") or "").strip()
    if webhook.startswith("https://"):
        result["discord"] = _post_json(webhook, _discord_payload(report))
    site = (settings.get("report_site_url") or "").strip()
    if site.startswith(("http://", "https://")):
        result["site"] = _post_json(site, report)
    return result


# ------------------------------------------------------------ entry points
def report_exception(exc_type, exc, tb, context: str = "") -> dict:
    detail = "".join(traceback.format_exception(exc_type, exc, tb))
    title = f"{exc_type.__name__}: {exc}"
    if context:
        title = f"[{context}] {title}"
    try:
        logmod.get_logger().error("UNHANDLED %s", title)
    except Exception:
        pass
    return deliver(build_report("crash", title, detail))


def send_feedback(kind: str, message: str, contact: str = "") -> dict:
    """User-initiated bug report / feedback - always attempts delivery."""
    kind = kind if kind in ("bug", "feedback", "frontend-crash") else "feedback"
    report = build_report(kind, message.splitlines()[0][:120] if message
                          else kind, "", feedback=message, contact=contact)
    return deliver(report, force_send=True)


def install() -> None:
    """Route every unhandled exception (main + worker threads) through us."""
    import sys

    def hook(exc_type, exc, tb):
        report_exception(exc_type, exc, tb)
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = hook

    def thread_hook(args):
        if args.exc_type is SystemExit:
            return
        report_exception(args.exc_type, args.exc_value, args.exc_traceback,
                         context=getattr(args.thread, "name", "thread"))

    threading.excepthook = thread_hook
