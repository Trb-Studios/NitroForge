"""
Game Booster orchestrator.

Design contract (Hard Safety Rules):
  * Every change is pushed onto an undo stack as (description, revert_fn)
    the moment it is made, so revert() always has something concrete to undo.
  * revert() runs: when the boosted game exits, when the user clicks Undo,
    and via atexit if the app dies unexpectedly.  It is idempotent.
  * Only allowlisted apps/services are ever touched (guards live in
    process_utils/power_utils; this file adds its own checks anyway).
  * Nothing here touches antivirus/security software - guards raise if a
    list is ever misconfigured to include one.
"""
from __future__ import annotations

import atexit
import os
import threading

import psutil

from core import config, game_scanner, power_utils, process_utils, resolution_utils
from core.logger import get_logger


class Booster:
    def __init__(self, settings: config.Settings):
        self._settings = settings
        self._log = get_logger()
        self._lock = threading.RLock()
        self._undo: list[tuple[str, callable]] = []
        self.active = False
        self.boosted_game: str | None = None
        atexit.register(self.revert)   # never leave a half-boosted system

    # ------------------------------------------------------------ helpers
    def _track(self, desc: str, revert_fn) -> None:
        with self._lock:
            self._undo.append((desc, revert_fn))
        self._log.info("BOOST   %s", desc)

    def changes(self) -> list[str]:
        with self._lock:
            return [d for d, _ in self._undo]

    # ------------------------------------------------------------- apply
    def apply(self, game_pid: int | None = None,
              game_exe: str | None = None) -> list[str]:
        """Apply all enabled sub-features. Returns list of change texts."""
        s = self._settings
        with self._lock:
            if self.active:
                return self.changes()
            self.active = True
        self.boosted_game = os.path.basename(game_exe) if game_exe else None

        if s.get("boost_suspend_apps"):
            self._suspend_background_apps()
        if s.get("boost_power_plan"):
            self._switch_power_plan()
        if s.get("boost_game_mode"):
            self._enable_game_mode()
        if s.get("boost_game_bar"):
            self._disable_game_bar()
        if s.get("boost_visual_effects"):
            self._reduce_visual_effects()
        if s.get("boost_services"):
            self._pause_services()
        if game_pid:
            if s.get("boost_priority"):
                self._raise_game_priority(game_pid)
            if s.get("boost_affinity"):
                self._tune_affinity(game_pid)
        self._log.info("Boost applied: %d change(s)", len(self._undo))
        return self.changes()

    # --------------------------------------------------------- sub-steps
    def _suspend_background_apps(self) -> None:
        names = self._settings.get("suspend_apps", [])
        for proc in process_utils.find_by_names(names):
            try:
                name, pid = proc.name(), proc.pid
                if config.is_critical_process(name):   # belt-and-braces
                    continue
                proc.suspend()
                self._track(f"Suspended {name} (pid {pid})",
                            lambda p=proc: self._safe_resume(p))
            except psutil.Error as exc:
                self._log.debug("Could not suspend %s: %s", proc, exc)

    def _safe_resume(self, proc: psutil.Process) -> None:
        try:
            proc.resume()
        except psutil.NoSuchProcess:
            pass    # it exited while suspended-resumed by definition

    def _switch_power_plan(self) -> None:
        old = power_utils.get_active_plan()
        best = power_utils.best_performance_plan()
        if not best or not old or best["guid"] == old["guid"]:
            return
        if power_utils.set_power_plan(best["guid"]):
            self._track(f"Power plan -> {best['name']} (was {old['name']})",
                        lambda g=old["guid"]: power_utils.set_power_plan(g))

    def _enable_game_mode(self) -> None:
        if not power_utils.get_game_mode():
            old = power_utils.set_game_mode(True)
            self._track("Enabled Windows Game Mode",
                        lambda o=old: power_utils.set_game_mode(o))

    def _disable_game_bar(self) -> None:
        if power_utils.get_game_bar():
            old = power_utils.set_game_bar(False)
            self._track("Disabled Xbox Game Bar capture/overlay",
                        lambda o=old: power_utils.set_game_bar(o))

    def _reduce_visual_effects(self) -> None:
        old = power_utils.get_visual_effects()
        if old != 2:
            power_utils.set_visual_effects(2)
            self._track("Visual effects -> best performance",
                        lambda o=(old if old is not None else 0):
                        power_utils.set_visual_effects(o))

    def _pause_services(self) -> None:
        if not power_utils.is_admin():
            self._log.warning("Not running as Administrator - skipping "
                              "service pausing (Windows Update, Search...).")
            return
        for svc, desc in config.BOOST_SERVICES.items():
            if config.is_security_service(svc, desc):  # can't happen; enforce anyway
                continue
            try:
                if power_utils.stop_service(svc):
                    self._track(f"Paused service: {desc} ({svc})",
                                lambda n=svc: power_utils.start_service(n))
            except PermissionError as exc:
                self._log.warning("%s", exc)

    def _raise_game_priority(self, pid: int) -> None:
        try:
            old = process_utils.set_priority(pid, "High")
            self._track(f"Game priority -> High (pid {pid})",
                        lambda p=pid, o=old: self._restore_priority(p, o))
        except (psutil.Error, process_utils.ProtectedProcessError) as exc:
            self._log.warning("Could not raise game priority: %s", exc)

    @staticmethod
    def _restore_priority(pid: int, old) -> None:
        try:
            psutil.Process(pid).nice(old)
        except psutil.Error:
            pass    # game already exited

    def _tune_affinity(self, pid: int) -> None:
        """Leave core 0 to the OS/interrupt handlers; game gets the rest."""
        ncpu = psutil.cpu_count(logical=True) or 1
        if ncpu < 4:
            return
        try:
            old = process_utils.set_affinity(pid, list(range(1, ncpu)))
            self._track(f"Game affinity -> cores 1-{ncpu - 1} (core 0 left "
                        "free for OS)",
                        lambda p=pid, o=old: self._restore_affinity(p, o))
        except (psutil.Error, process_utils.ProtectedProcessError) as exc:
            self._log.warning("Could not set affinity: %s", exc)

    @staticmethod
    def _restore_affinity(pid: int, old: list[int]) -> None:
        try:
            psutil.Process(pid).cpu_affinity(old)
        except psutil.Error:
            pass

    # ------------------------------------------------------------- revert
    def revert(self) -> int:
        """Undo everything, LIFO. Idempotent; safe from atexit."""
        with self._lock:
            undo, self._undo = self._undo, []
            self.active = False
            self.boosted_game = None
        for desc, fn in reversed(undo):
            try:
                fn()
                self._log.info("REVERT  %s", desc)
            except Exception as exc:
                self._log.error("Revert failed for '%s': %s", desc, exc)
        if undo:
            self._log.info("Boost reverted (%d change(s) undone)", len(undo))
        return len(undo)

    # ------------------------------------------- boost + launch + watch
    def attach_game(self, pid: int, name: str | None = None) -> None:
        """Apply per-process tweaks once the real game process exists."""
        with self._lock:
            if not self.active:
                return
        if name:
            self.boosted_game = name
        if self._settings.get("boost_priority"):
            self._raise_game_priority(pid)
        if self._settings.get("boost_affinity"):
            self._tune_affinity(pid)

    def boost_and_launch(self, game: game_scanner.Game,
                         on_exit=None) -> game_scanner.LaunchResult:
        """Apply gaming resolution + boost, launch, auto-revert on exit.

        Launcher-URI launches (Steam/Epic/Ubisoft/Riot) give us no child
        handle, so a watcher thread waits for the game's process to appear,
        attaches priority/affinity to it, and reverts when it exits.
        """
        s = self._settings
        res_switched = False
        if s.get("apply_res_on_game") and s.get("gaming_resolution"):
            w, h, hz = s.get("gaming_resolution")
            # CDS_FULLSCREEN (persist=False): temporary by nature, and we
            # also explicitly restore on exit below.
            res_switched = resolution_utils.set_mode(w, h, hz, persist=False)

        result = game_scanner.launch(game)
        if not result.ok:
            if res_switched:
                resolution_utils.restore_default()
            self._log.error("Could not launch %s: %s", game.name, result.error)
            return result

        # system-level tweaks right away; per-process ones when it appears
        self.apply(game_exe=game.exe or game.name)

        def _watch():
            pid = result.proc.pid if result.proc else None
            if pid is None and game.exe:
                pid = game_scanner.wait_for_process(game.exe, timeout=120)
            if pid is None:
                self._log.warning(
                    "%s: game process not found - boost stays active until "
                    "you press Undo.", game.name)
                return
            self.attach_game(pid, os.path.basename(game.exe) or game.name)
            try:
                psutil.Process(pid).wait()
            except psutil.Error:
                pass
            self._log.info("%s exited - auto-reverting boost", game.name)
            self.revert()
            if res_switched:
                resolution_utils.restore_default()
            if on_exit:
                on_exit()

        threading.Thread(target=_watch, daemon=True,
                         name=f"watch-{game.name}").start()
        return result
