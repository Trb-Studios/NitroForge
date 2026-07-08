"""
Installed-game discovery across Steam / Epic / GOG / Riot / Battle.net /
Xbox folders, plus manual additions.

Exe matching is heuristic: inside an install dir we pick the largest .exe
that doesn't look like an installer/updater/anti-cheat helper (see
config.GAME_EXE_BLACKLIST).  It won't be perfect for every game - that's why
the Games tab lets the user add/point to an exe manually.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import winreg
from dataclasses import dataclass, asdict
from pathlib import Path

from core import config
from core.logger import get_logger


@dataclass
class Game:
    name: str
    exe: str            # full path to the launch executable ("" if unknown)
    source: str         # Steam / Epic / GOG / Riot / Battle.net / Xbox / Manual
    install_dir: str = ""


# --------------------------------------------------------------- helpers
def _best_exe(install_dir: str, max_depth: int = 3) -> str:
    """Largest plausible game exe under install_dir; '' if none."""
    best, best_size = "", 0
    root = Path(install_dir)
    if not root.is_dir():
        return ""
    base_depth = len(root.parts)
    for dirpath, dirnames, filenames in os.walk(root):
        if len(Path(dirpath).parts) - base_depth >= max_depth:
            dirnames.clear()
        for fn in filenames:
            if not fn.lower().endswith(".exe"):
                continue
            low = fn.lower()
            if any(b in low for b in config.GAME_EXE_BLACKLIST):
                continue
            try:
                size = os.path.getsize(os.path.join(dirpath, fn))
            except OSError:
                continue
            # deprioritise "launcher" exes but keep them as a fallback
            if "launcher" in low:
                size //= 10
            if size > best_size:
                best, best_size = os.path.join(dirpath, fn), size
    return best


def _steam_roots() -> list[Path]:
    roots = []
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
            roots.append(Path(winreg.QueryValueEx(k, "SteamPath")[0]))
    except OSError:
        pass
    for default in (r"C:\Program Files (x86)\Steam", r"C:\Program Files\Steam"):
        p = Path(default)
        if p.is_dir() and p not in roots:
            roots.append(p)
    # extra library folders from libraryfolders.vdf
    extra = []
    for r in roots:
        vdf = r / "steamapps" / "libraryfolders.vdf"
        if vdf.is_file():
            try:
                for m in re.finditer(r'"path"\s+"([^"]+)"', vdf.read_text(
                        encoding="utf-8", errors="ignore")):
                    extra.append(Path(m.group(1).replace("\\\\", "\\")))
            except OSError:
                pass
    return list(dict.fromkeys(roots + extra))


# --------------------------------------------------------------- scanners
def _scan_steam() -> list[Game]:
    games = []
    for root in _steam_roots():
        common = root / "steamapps" / "common"
        if not common.is_dir():
            continue
        for d in common.iterdir():
            if d.is_dir() and d.name not in ("Steamworks Shared",):
                games.append(Game(d.name, _best_exe(str(d)), "Steam", str(d)))
    return games


def _scan_epic() -> list[Game]:
    games = []
    manifests = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / \
        "Epic" / "EpicGamesLauncher" / "Data" / "Manifests"
    if not manifests.is_dir():
        return games
    for item in manifests.glob("*.item"):
        try:
            data = json.loads(item.read_text(encoding="utf-8", errors="ignore"))
            loc = data.get("InstallLocation", "")
            exe = os.path.join(loc, data.get("LaunchExecutable", "")) \
                if data.get("LaunchExecutable") else _best_exe(loc)
            games.append(Game(data.get("DisplayName", item.stem),
                              exe if os.path.isfile(exe) else _best_exe(loc),
                              "Epic", loc))
        except (json.JSONDecodeError, OSError):
            continue
    return games


def _scan_folder_root(root: str, source: str) -> list[Game]:
    games = []
    rp = Path(root)
    if not rp.is_dir():
        return games
    for d in rp.iterdir():
        if d.is_dir():
            exe = _best_exe(str(d))
            if exe:
                games.append(Game(d.name, exe, source, str(d)))
    return games


def scan_all(settings: config.Settings) -> list[Game]:
    log = get_logger()
    games: list[Game] = []
    for fn in (_scan_steam, _scan_epic):
        try:
            games += fn()
        except Exception as exc:
            log.warning("Game scan (%s) failed: %s", fn.__name__, exc)
    for root, source in [
        (r"C:\Program Files (x86)\GOG Galaxy\Games", "GOG"),
        (r"C:\GOG Games", "GOG"),
        (r"C:\Riot Games", "Riot"),
        (r"C:\XboxGames", "Xbox"),
        (r"C:\Program Files (x86)\Call of Duty", "Battle.net"),
        (r"C:\Program Files (x86)\Overwatch", "Battle.net"),
        (r"C:\Program Files (x86)\World of Warcraft", "Battle.net"),
    ]:
        try:
            games += _scan_folder_root(root, source)
        except Exception as exc:
            log.debug("Scan of %s failed: %s", root, exc)
    for g in settings.get("custom_games", []):
        games.append(Game(g["name"], g["exe"], "Manual",
                          os.path.dirname(g["exe"])))
    # de-dup by (name, source)
    seen, unique = set(), []
    for g in games:
        key = (g.name.lower(), g.source)
        if key not in seen:
            seen.add(key)
            unique.append(g)
    unique.sort(key=lambda g: g.name.lower())
    log.info("Game scan found %d games", len(unique))
    return unique


def add_manual_game(settings: config.Settings, exe_path: str) -> Game:
    name = Path(exe_path).stem
    entry = {"name": name, "exe": exe_path, "source": "Manual"}
    customs = list(settings.get("custom_games", []))
    if not any(c["exe"] == exe_path for c in customs):
        customs.append(entry)
        settings.set("custom_games", customs)
    return Game(name, exe_path, "Manual", os.path.dirname(exe_path))


def launch(game: Game) -> subprocess.Popen | None:
    """Start the game exe directly, from its own folder."""
    if not game.exe or not os.path.isfile(game.exe):
        return None
    proc = subprocess.Popen([game.exe], cwd=os.path.dirname(game.exe))
    get_logger().info("Launched %s (%s, pid %d)", game.name, game.source,
                      proc.pid)
    return proc
