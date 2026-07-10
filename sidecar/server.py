"""
Nitro Forge sidecar: a local-only JSON API over the `core` engine,
consumed by the Tauri desktop shell.

Security model:
  * Binds 127.0.0.1 only, on an ephemeral port (printed as "PORT <n>" on
    stdout for the Rust shell to read).
  * Every request must carry the X-NF-Token header the shell generated
    (image requests, which browsers can't attach headers to, pass the same
    token as a ?t= query parameter instead).  Browsers can't attach custom
    headers cross-origin without passing CORS preflight, and we only ACK
    our own origins - so random websites can't drive this API, and other
    local processes would need the token.
  * All the safety guards live in `core` (security/AV hard-blocks,
    allowlists, revert tracking) - this layer adds no privileged logic.

Run:  py sidecar/server.py --token <secret> [--port 0]
"""
from __future__ import annotations

import argparse
import json
import multiprocessing
import os
import sys
import threading
import time
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psutil

from core import (bottleneck, config, crash_reporter, game_catalog,
                  game_scanner, logger as logmod, network_utils, power_utils,
                  process_utils, resolution_utils, system_info, tweaks)
from core.booster import Booster
from core.db import Database, Sampler
from core.fps_monitor import FpsMonitor

ALLOWED_ORIGINS = {
    "http://localhost:1420",        # vite dev
    "tauri://localhost",            # tauri prod (macOS/Linux)
    "http://tauri.localhost",       # tauri prod (Windows)
    "https://tauri.localhost",
}

# settings keys the frontend may write (everything else is refused)
WRITABLE_SETTINGS = {
    "presentmon_path", "boost_on_launch", "apply_res_on_game",
    "gaming_resolution", "overlay_corner", "overlay_size",
    "boost_suspend_apps", "boost_priority", "boost_affinity",
    "boost_power_plan", "boost_game_mode", "boost_game_bar",
    "boost_visual_effects", "boost_services", "suspend_apps",
    "boost_network_latency", "boost_responsiveness", "boost_games_scheduling",
    "boost_power_latency",
    "mouse_enhance_pointer", "mouse_pointer_speed",
    "fps_auto_target", "overlay_locked",
    "report_enabled", "report_auto_send", "report_discord_webhook",
    "report_site_url", "report_include_logs",
}


class Services:
    """Shared singletons + tiny caches for hot polled endpoints."""

    def __init__(self):
        self.log = logmod.get_logger()
        self.settings = config.Settings.load()
        self.db = Database()
        self.gpu = system_info.GpuMonitor()
        self.fps = FpsMonitor(self.settings, self.log)
        self.booster = Booster(self.settings)
        self.throughput = network_utils.Throughput()
        self._net_cache = (0.0, {"type": "Unknown", "detail": ""})
        self._games_cache: list | None = None
        self.sampler = Sampler(
            self.db,
            get_sys=lambda: (psutil.cpu_percent(None),
                             psutil.virtual_memory().percent),
            get_gpu=lambda: (lambda g: (g["load"], g["mem_percent"]))(
                self.gpu.live()),
            get_fps=lambda: (lambda s: (s["fps"], s["frametime_ms"]))(
                self.fps.current_stats()),
        )
        self.sampler.start()
        self._fg_stop = threading.Event()
        threading.Thread(target=self._foreground_loop, daemon=True,
                         name="fps-autotarget").start()

    def _foreground_loop(self) -> None:
        """While capturing, keep the FPS overlay pointed at the foreground
        game (opt-out via the fps_auto_target setting)."""
        while not self._fg_stop.wait(2.0):
            try:
                if self.fps.running and self.settings.get("fps_auto_target"):
                    self.fps.note_foreground(system_info.foreground_process_name())
            except Exception:      # never let the helper thread die
                pass

    def net_type(self) -> dict:
        """netsh shells out -> cache 30s so /api/live stays fast."""
        ts, val = self._net_cache
        if time.time() - ts > 30:
            val = network_utils.get_connection_type()
            self._net_cache = (time.time(), val)
        return val

    def games(self, rescan=False) -> list[dict]:
        if self._games_cache is None or rescan:
            rows = []
            for g in game_scanner.scan_all(self.settings):
                d = asdict(g)
                d["fso_disabled"] = (power_utils.fullscreen_opt_disabled(g.exe)
                                     if g.exe else False)
                rows.append(d)
            self._games_cache = rows
        return self._games_cache


SVC: Services | None = None
TOKEN = ""
_shutdown = threading.Event()


# --------------------------------------------------------------- handlers
def h_live(_q, _b):
    g = SVC.gpu.live()
    f = SVC.fps.current_stats()
    vm = psutil.virtual_memory()
    return {
        "cpu": psutil.cpu_percent(None),
        "ram": {"percent": vm.percent, "used_gb": vm.used / 1024**3,
                "total_gb": vm.total / 1024**3},
        "gpu": {"load": g["load"], "mem_percent": g["mem_percent"],
                "temp": g["temp"]},
        "fps": f,
        "fps_running": SVC.fps.running,
        "net": {**SVC.throughput.sample(), **SVC.net_type()},
        "boost": {"active": SVC.booster.active,
                  "changes": SVC.booster.changes(),
                  "game": SVC.booster.boosted_game},
        "admin": system_info.is_admin(),
    }


def h_meta(_q, _b):
    return {
        "name": config.APP_DISPLAY_NAME,
        "version": config.APP_VERSION,
        "admin": system_info.is_admin(),
        "catalog_size": game_catalog.catalog_size(),
        "data_dir": str(config.APP_DIR),
    }


def h_specs(_q, _b):
    gpus = []
    for g in system_info.get_gpu_static():
        d = dict(g)
        if d.get("driver_date"):
            d["driver_date"] = d["driver_date"].strftime("%Y-%m-%d")
        gpus.append(d)
    return {
        "cpu": system_info.get_cpu_static(),
        "cpu_live": system_info.get_cpu_live(),
        "gpus": gpus,
        "gpu_live": SVC.gpu.live(),
        "ram": system_info.get_ram_live(),
        "modules": system_info.get_ram_modules(),
        "storage": system_info.get_storage_info(),
        "monitors": system_info.get_monitors(),
        "os": system_info.get_os_info(),
        "hags": system_info.hags_enabled(),
        "driver_warning": system_info.gpu_driver_age_warning(),
    }


def h_processes(_q, _b):
    return {"rows": process_utils.list_processes(),
            "diagnostics": process_utils.top_offenders()}


def h_process_action(_q, body):
    pid, action = int(body["pid"]), body["action"]
    if action == "kill":
        process_utils.kill(pid)
    elif action == "suspend":
        process_utils.suspend(pid)
    elif action == "resume":
        process_utils.resume(pid)
    elif action == "priority":
        process_utils.set_priority(pid, body["level"])
    elif action == "affinity":
        process_utils.set_affinity(pid, [int(c) for c in body["cores"]])
    else:
        raise ValueError(f"unknown action {action}")
    return {"ok": True}


def h_games(q, _b):
    return {"games": SVC.games(rescan="rescan" in q)}


def h_game_launch(_q, body):
    game = game_scanner.Game(
        name=body["name"],
        exe=body.get("exe", ""),
        source=body.get("source", "Manual"),
        install_dir=body.get("install_dir", ""),
        launch_uri=body.get("launch_uri", ""),
        appid=body.get("appid"),
    )
    boost = SVC.settings.get("boost_on_launch") and not SVC.booster.active
    res = SVC.settings.get("apply_res_on_game") and \
        SVC.settings.get("gaming_resolution")
    if boost or res:
        result = SVC.booster.boost_and_launch(game)
    else:
        result = game_scanner.launch(game)
    if result.ok and SVC.fps.running and game.exe:
        SVC.fps.target = os.path.basename(game.exe).lower()
    return {"ok": result.ok, "method": result.method, "error": result.error}


def h_game_add(_q, body):
    exe = body["exe"]
    if not os.path.isfile(exe):
        return {"ok": False, "error": "File not found."}
    game_scanner.add_manual_game(SVC.settings, exe)
    SVC.games(rescan=True)
    return {"ok": True}


def h_game_remove(_q, body):
    game_scanner.remove_manual_game(SVC.settings, body["exe"])
    SVC.games(rescan=True)
    return {"ok": True}


def h_game_fso(_q, body):
    power_utils.set_fullscreen_opt_disabled(body["exe"], bool(body["disabled"]))
    SVC.games(rescan=True)
    return {"ok": True}


def h_booster(_q, _b):
    s = SVC.settings
    return {
        "active": SVC.booster.active,
        "changes": SVC.booster.changes(),
        "game": SVC.booster.boosted_game,
        "admin": system_info.is_admin(),
        "flags": {k: bool(s.get(k)) for k in WRITABLE_SETTINGS
                  if k.startswith("boost_") and k != "boost_on_launch"},
        "boost_on_launch": bool(s.get("boost_on_launch")),
        "allowlist": s.get("suspend_apps"),
        "services": config.BOOST_SERVICES,
    }


def h_booster_apply(_q, _b):
    return {"changes": SVC.booster.apply()}


def h_booster_revert(_q, _b):
    return {"reverted": SVC.booster.revert()}


def h_settings_get(_q, _b):
    return {k: SVC.settings.get(k) for k in WRITABLE_SETTINGS}


def h_settings_set(_q, body):
    key, value = body["key"], body["value"]
    if key not in WRITABLE_SETTINGS:
        raise PermissionError(f"setting '{key}' is not writable via the API")
    if key == "suspend_apps":
        value = [n for n in value if not config.is_critical_process(n)]
    if key == "presentmon_path" and value and not os.path.isfile(value):
        return {"ok": False, "error": "No file at that path."}
    SVC.settings.set(key, value)
    return {"ok": True, "value": value}


def h_resolution(_q, _b):
    return {"current": resolution_utils.get_current_mode(),
            "modes": resolution_utils.list_modes()}


def h_resolution_set(_q, body):
    ok = resolution_utils.set_mode(int(body["w"]), int(body["h"]),
                                   int(body["hz"]),
                                   persist=bool(body.get("persist", True)))
    return {"ok": ok, "current": resolution_utils.get_current_mode()}


def h_analytics(q, _b):
    secs = float(q.get("secs", ["3600"])[0])
    rows = [{"t": r[0], "cpu": r[1], "ram": r[2], "gpu": r[3],
             "fps": r[5], "ft": r[6]} for r in SVC.db.query_samples(secs)]
    return {"rows": rows, "stats": SVC.db.summary_stats(secs)}


def h_bottleneck_static(_q, _b):
    return {"findings": [asdict(f) for f in bottleneck.static_findings()]}


def h_bottleneck_live(_q, _b):
    return {"findings": [asdict(f) for f in
                         bottleneck.live_findings(SVC.db.query_samples(300))]}


def h_logs(q, _b):
    since = int(q.get("since", ["0"])[0])
    recs = logmod.get_records(since)
    return {"records": recs, "last": recs[-1]["n"] if recs else since}


def h_fps_start(_q, body):
    ok = SVC.fps.start((body or {}).get("process"))
    return {"ok": ok, "error": SVC.fps.last_error}


def h_fps_stop(_q, _b):
    SVC.fps.stop()
    return {"ok": True}


def h_startup(_q, _b):
    return {"apps": power_utils.list_startup_apps()}


def h_startup_toggle(_q, body):
    power_utils.set_startup_enabled(body["name"], bool(body["enabled"]))
    return {"ok": True}


def h_gpu_panel(_q, _b):
    return {"opened": power_utils.open_gpu_control_panel()}


# ------------------------------------------------------------- input / mouse
def h_input(_q, _b):
    """Current mouse state (persistent settings, applied immediately)."""
    return {"mouse": tweaks.get_mouse(),
            "admin": system_info.is_admin()}


def h_input_mouse(_q, body):
    if "enhance_pointer" in body:
        tweaks.set_enhance_pointer(bool(body["enhance_pointer"]))
        SVC.settings.set("mouse_enhance_pointer", bool(body["enhance_pointer"]))
    if "pointer_speed" in body:
        tweaks.set_pointer_speed(int(body["pointer_speed"]))
        SVC.settings.set("mouse_pointer_speed", int(body["pointer_speed"]))
    return {"ok": True, "mouse": tweaks.get_mouse()}


# ------------------------------------------------- crash / feedback routes
def h_report_crash(_q, body):
    """Frontend error-boundary reports land here."""
    report = crash_reporter.build_report(
        "frontend-crash",
        str(body.get("title", "UI crash"))[:200],
        str(body.get("detail", ""))[:8000],
        feedback=str(body.get("feedback", "")),
    )
    return crash_reporter.deliver(report,
                                  force_send=bool(body.get("send", False)))


def h_report_feedback(_q, body):
    return crash_reporter.send_feedback(
        str(body.get("kind", "feedback")),
        str(body.get("message", "")),
        contact=str(body.get("contact", "")),
    )


def h_report_test(_q, _b):
    """'Send test report' button in Settings - verifies webhook/site config."""
    report = crash_reporter.build_report(
        "feedback", "Test report",
        "If you can read this, Nitro Forge reporting is wired up correctly.")
    return crash_reporter.deliver(report, force_send=True)


def h_shutdown(_q, _b):
    _shutdown.set()
    return {"ok": True}


ROUTES = {
    ("GET", "/api/live"): h_live,
    ("GET", "/api/meta"): h_meta,
    ("GET", "/api/specs"): h_specs,
    ("GET", "/api/processes"): h_processes,
    ("POST", "/api/process/action"): h_process_action,
    ("GET", "/api/games"): h_games,
    ("POST", "/api/games/launch"): h_game_launch,
    ("POST", "/api/games/add"): h_game_add,
    ("POST", "/api/games/remove"): h_game_remove,
    ("POST", "/api/games/fso"): h_game_fso,
    ("GET", "/api/booster"): h_booster,
    ("POST", "/api/booster/apply"): h_booster_apply,
    ("POST", "/api/booster/revert"): h_booster_revert,
    ("GET", "/api/settings"): h_settings_get,
    ("POST", "/api/settings"): h_settings_set,
    ("GET", "/api/resolution"): h_resolution,
    ("POST", "/api/resolution/set"): h_resolution_set,
    ("GET", "/api/analytics"): h_analytics,
    ("GET", "/api/bottleneck/static"): h_bottleneck_static,
    ("GET", "/api/bottleneck/live"): h_bottleneck_live,
    ("GET", "/api/logs"): h_logs,
    ("POST", "/api/fps/start"): h_fps_start,
    ("POST", "/api/fps/stop"): h_fps_stop,
    ("GET", "/api/startup"): h_startup,
    ("POST", "/api/startup/toggle"): h_startup_toggle,
    ("POST", "/api/gpu-panel"): h_gpu_panel,
    ("GET", "/api/input"): h_input,
    ("POST", "/api/input/mouse"): h_input_mouse,
    ("POST", "/api/report/crash"): h_report_crash,
    ("POST", "/api/report/feedback"): h_report_feedback,
    ("POST", "/api/report/test"): h_report_test,
    ("POST", "/api/shutdown"): h_shutdown,
}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_):        # keep stdout clean (Rust reads it)
        pass

    def _cors(self):
        origin = self.headers.get("Origin", "")
        if origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Headers",
                             "Content-Type, X-NF-Token")
            self.send_header("Access-Control-Allow-Methods", "GET, POST")

    def _reply(self, code: int, payload: dict):
        raw = json.dumps(payload).encode()
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _serve_logo(self, path: str, query: dict):
        """GET /api/logo/<appid> -> jpeg bytes (token via ?t=, since <img>
        tags cannot set headers). Appid is strictly numeric - no path games."""
        if query.get("t", [""])[0] != TOKEN:
            self._reply(401, {"error": "bad token"})
            return
        appid = path.rsplit("/", 1)[-1]
        if not appid.isdigit():
            self._reply(400, {"error": "bad appid"})
            return
        logo = game_catalog.logo_path(int(appid))
        if logo is None:
            self._reply(404, {"error": "no logo"})
            return
        data = logo.read_bytes()
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "max-age=86400")
        self.end_headers()
        self.wfile.write(data)

    def _handle(self, method: str):
        url = urlparse(self.path)
        query = parse_qs(url.query)
        if method == "GET" and url.path.startswith("/api/logo/"):
            try:
                self._serve_logo(url.path, query)
            except Exception as exc:                  # noqa: BLE001
                SVC.log.debug("Logo request failed: %s", exc)
            return
        if self.headers.get("X-NF-Token", "") != TOKEN:
            self._reply(401, {"error": "bad token"})
            return
        fn = ROUTES.get((method, url.path))
        if fn is None:
            self._reply(404, {"error": f"no route {method} {url.path}"})
            return
        body = {}
        if method == "POST":
            n = int(self.headers.get("Content-Length", 0) or 0)
            if n:
                try:
                    body = json.loads(self.rfile.read(n))
                except json.JSONDecodeError:
                    self._reply(400, {"error": "bad json"})
                    return
        try:
            self._reply(200, fn(query, body))
        except (PermissionError, process_utils.ProtectedProcessError) as exc:
            self._reply(403, {"error": str(exc)})
        except Exception as exc:                     # noqa: BLE001
            SVC.log.error("API %s %s failed: %s", method, url.path, exc)
            crash_reporter.report_exception(type(exc), exc, exc.__traceback__,
                                            context=f"{method} {url.path}")
            self._reply(500, {"error": str(exc)})
        if _shutdown.is_set():
            threading.Thread(target=self.server.shutdown,
                             daemon=True).start()

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")


def main():
    global SVC, TOKEN
    ap = argparse.ArgumentParser()
    ap.add_argument("--token", required=True)
    ap.add_argument("--port", type=int, default=0)
    args = ap.parse_args()
    TOKEN = args.token

    crash_reporter.install()
    SVC = Services()
    SVC.log.info("%s %s sidecar starting (admin=%s)",
                 config.APP_DISPLAY_NAME, config.APP_VERSION,
                 system_info.is_admin())
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"PORT {server.server_address[1]}", flush=True)
    SVC.log.info("Sidecar listening on 127.0.0.1:%d",
                 server.server_address[1])
    try:
        server.serve_forever()
    finally:
        # graceful shutdown: never leave a half-boosted system behind
        SVC.booster.revert()
        SVC.fps.stop()
        SVC.sampler.stop()
        SVC.db.close()
        SVC.log.info("Sidecar stopped cleanly.")


if __name__ == "__main__":
    # CRITICAL for the frozen exe: py-cpuinfo & friends use multiprocessing;
    # without this, every child spawn re-runs the whole app (the old
    # "opens hundreds of windows" bug).
    multiprocessing.freeze_support()
    main()
