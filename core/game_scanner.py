"""
Installed-game discovery and launcher-aware launching.

Detection sources
  Steam        appmanifest_*.acf in every library folder (appid + real name)
  Epic Games   ProgramData manifests (namespace/item/app -> launch URI)
  Riot         C:/Riot Games product folders -> RiotClientServices launch args
  GOG Galaxy   registry (HKLM/.../GOG.com/Games) - DRM-free, direct exe
  Ubisoft      registry (HKLM/.../Ubisoft/Launcher/Installs) -> uplay:// URI
  Battle.net / EA / Xbox   well-known install roots
  Manual       user-added executables

Launching prefers the platform's own protocol (steam://rungameid/...,
com.epicgames.launcher://..., uplay://launch/...) so DRM, anti-cheat and
cloud saves work exactly as if the user clicked the launcher - the old
"run the biggest exe and hope" approach only remains as the fallback.

Exe paths are still resolved where possible because the Booster uses them
to find the game process for priority/affinity tuning.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
import urllib.parse
import winreg
from dataclasses import dataclass, field

import psutil

from pathlib import Path

from core import config, game_catalog
from core.logger import get_logger


@dataclass
class Game:
    name: str
    exe: str = ""            # best-effort path to the game binary ("" if unknown)
    source: str = "Manual"   # Steam / Epic / Riot / GOG / Ubisoft / Battle.net / EA / Xbox / Manual
    install_dir: str = ""
    launch_uri: str = ""     # platform protocol URI ("" -> launch exe directly)
    appid: int | None = None  # Steam appid when known (drives box art)

    def finalize(self) -> "Game":
        """Fill the appid from the shipped catalog when the store didn't."""
        if self.appid is None:
            self.appid = game_catalog.match_appid(self.name)
        return self


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


def _reg_subkeys(root, path: str):
    try:
        with winreg.OpenKey(root, path) as k:
            n = winreg.QueryInfoKey(k)[0]
            return [winreg.EnumKey(k, i) for i in range(n)]
    except OSError:
        return []


def _reg_value(root, path: str, name: str) -> str:
    try:
        with winreg.OpenKey(root, path) as k:
            return str(winreg.QueryValueEx(k, name)[0])
    except OSError:
        return ""


# --------------------------------------------------------------- scanners
# Steam appids that are tooling, not games
_STEAM_SKIP_APPIDS = {228980}          # Steamworks Common Redistributables


def _scan_steam() -> list[Game]:
    """Read appmanifest_*.acf: real names, appids -> steam:// launching."""
    games = []
    for root in _steam_roots():
        steamapps = root / "steamapps"
        if not steamapps.is_dir():
            continue
        for acf in steamapps.glob("appmanifest_*.acf"):
            try:
                text = acf.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            def _field(key: str) -> str:
                m = re.search(rf'"{key}"\s+"([^"]*)"', text)
                return m.group(1) if m else ""
            appid = int(_field("appid") or 0)
            name = _field("name")
            installdir = _field("installdir")
            if not appid or not name or appid in _STEAM_SKIP_APPIDS:
                continue
            folder = steamapps / "common" / installdir
            games.append(Game(
                name=name,
                exe=_best_exe(str(folder)) if folder.is_dir() else "",
                source="Steam",
                install_dir=str(folder),
                launch_uri=f"steam://rungameid/{appid}",
                appid=appid,
            ))
    return games


def _scan_epic() -> list[Game]:
    """Epic manifests carry everything needed for a proper launcher URI."""
    games = []
    manifests = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / \
        "Epic" / "EpicGamesLauncher" / "Data" / "Manifests"
    if not manifests.is_dir():
        return games
    for item in manifests.glob("*.item"):
        try:
            data = json.loads(item.read_text(encoding="utf-8", errors="ignore"))
        except (json.JSONDecodeError, OSError):
            continue
        loc = data.get("InstallLocation", "")
        name = data.get("DisplayName", item.stem)
        exe = os.path.join(loc, data.get("LaunchExecutable", "")) \
            if data.get("LaunchExecutable") else ""
        ns, item_id, app = (data.get("CatalogNamespace", ""),
                            data.get("CatalogItemId", ""),
                            data.get("AppName", ""))
        uri = ""
        if ns and item_id and app:
            uri = ("com.epicgames.launcher://apps/"
                   f"{ns}%3A{item_id}%3A{urllib.parse.quote(app)}"
                   "?action=launch&silent=true")
        games.append(Game(
            name=name,
            exe=exe if os.path.isfile(exe) else _best_exe(loc),
            source="Epic",
            install_dir=loc,
            launch_uri=uri,
        ))
    return games


# Riot product folders -> RiotClientServices --launch-product IDs
_RIOT_PRODUCTS = {
    "VALORANT": "valorant",
    "League of Legends": "league_of_legends",
    "Legends of Runeterra": "bacon",
    "2XKO": "spiel",
}


def _riot_client() -> str:
    for base in (r"C:\Riot Games", r"D:\Riot Games"):
        p = Path(base) / "Riot Client" / "RiotClientServices.exe"
        if p.is_file():
            return str(p)
    return ""


def _scan_riot() -> list[Game]:
    games = []
    client = _riot_client()
    for base in (r"C:\Riot Games", r"D:\Riot Games"):
        root = Path(base)
        if not root.is_dir():
            continue
        for d in root.iterdir():
            if not d.is_dir() or d.name in ("Riot Client",):
                continue
            product = _RIOT_PRODUCTS.get(d.name)
            games.append(Game(
                name=d.name,
                exe=_best_exe(str(d)),
                source="Riot",
                install_dir=str(d),
                # handled specially in launch(): client exe + product args
                launch_uri=f"riot:{product}" if product and client else "",
            ))
    return games


def _scan_gog() -> list[Game]:
    """GOG registry: exact names + exe paths, no folder guessing."""
    games = []
    for hive_path in (r"SOFTWARE\WOW6432Node\GOG.com\Games",
                      r"SOFTWARE\GOG.com\Games"):
        for gid in _reg_subkeys(winreg.HKEY_LOCAL_MACHINE, hive_path):
            base = f"{hive_path}\\{gid}"
            name = _reg_value(winreg.HKEY_LOCAL_MACHINE, base, "gameName")
            exe = _reg_value(winreg.HKEY_LOCAL_MACHINE, base, "exe")
            path = _reg_value(winreg.HKEY_LOCAL_MACHINE, base, "path")
            if not name:
                continue
            games.append(Game(
                name=name,
                exe=exe if os.path.isfile(exe) else _best_exe(path),
                source="GOG",
                install_dir=path,
            ))
    return games


def _scan_ubisoft() -> list[Game]:
    """Ubisoft Connect registry installs -> uplay://launch/<id>."""
    games = []
    hive = r"SOFTWARE\WOW6432Node\Ubisoft\Launcher\Installs"
    for gid in _reg_subkeys(winreg.HKEY_LOCAL_MACHINE, hive):
        idir = _reg_value(winreg.HKEY_LOCAL_MACHINE, f"{hive}\\{gid}",
                          "InstallDir").replace("/", "\\")
        if not idir or not os.path.isdir(idir):
            continue
        name = os.path.basename(os.path.normpath(idir))
        games.append(Game(
            name=name,
            exe=_best_exe(idir),
            source="Ubisoft",
            install_dir=idir,
            launch_uri=f"uplay://launch/{gid}/0",
        ))
    return games


def _scan_xbox() -> list[Game]:
    """Xbox/Game Pass installs: launch through gamelaunchhelper.exe."""
    games = []
    for base in (r"C:\XboxGames", r"D:\XboxGames"):
        root = Path(base)
        if not root.is_dir():
            continue
        for d in root.iterdir():
            content = d / "Content"
            if not content.is_dir():
                continue
            helper = content / "gamelaunchhelper.exe"
            games.append(Game(
                name=d.name,
                exe=str(helper) if helper.is_file() else _best_exe(str(content)),
                source="Xbox",
                install_dir=str(content),
            ))
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
    t0 = time.monotonic()
    games: list[Game] = []
    for fn in (_scan_steam, _scan_epic, _scan_riot, _scan_gog,
               _scan_ubisoft, _scan_xbox):
        try:
            games += fn()
        except Exception as exc:
            log.warning("Game scan (%s) failed: %s", fn.__name__, exc)
    for root, source in [
        (r"C:\Program Files (x86)\Battle.net Games", "Battle.net"),
        (r"C:\Program Files (x86)\Call of Duty", "Battle.net"),
        (r"C:\Program Files (x86)\Overwatch", "Battle.net"),
        (r"C:\Program Files (x86)\World of Warcraft", "Battle.net"),
        (r"C:\Program Files\EA Games", "EA"),
        (r"C:\Program Files (x86)\EA Games", "EA"),
        (r"C:\Program Files (x86)\Origin Games", "EA"),
        (r"C:\GOG Games", "GOG"),
    ]:
        try:
            games += _scan_folder_root(root, source)
        except Exception as exc:
            log.debug("Scan of %s failed: %s", root, exc)
    for g in settings.get("custom_games", []):
        games.append(Game(g["name"], g["exe"], "Manual",
                          os.path.dirname(g["exe"])))
    # de-dup by (name, source), resolve catalog appids, sort
    seen, unique = set(), []
    for g in games:
        key = (g.name.lower(), g.source)
        if key not in seen:
            seen.add(key)
            unique.append(g.finalize())
    unique.sort(key=lambda g: g.name.lower())
    log.info("Game scan: %d games in %.2fs (catalog: %d titles)",
             len(unique), time.monotonic() - t0, game_catalog.catalog_size())
    return unique


def add_manual_game(settings: config.Settings, exe_path: str) -> Game:
    name = Path(exe_path).stem
    entry = {"name": name, "exe": exe_path, "source": "Manual"}
    customs = list(settings.get("custom_games", []))
    if not any(c["exe"] == exe_path for c in customs):
        customs.append(entry)
        settings.set("custom_games", customs)
    return Game(name, exe_path, "Manual", os.path.dirname(exe_path)).finalize()


def remove_manual_game(settings: config.Settings, exe_path: str) -> None:
    customs = [c for c in settings.get("custom_games", [])
               if c["exe"] != exe_path]
    settings.set("custom_games", customs)


# ---------------------------------------------------------------- launching
@dataclass
class LaunchResult:
    ok: bool
    method: str = ""              # "launcher" | "exe" | ""
    error: str = ""
    proc: subprocess.Popen | None = field(default=None, repr=False)


def launch(game: Game) -> LaunchResult:
    """Launch through the game's own platform when possible, exe otherwise."""
    log = get_logger()

    if game.launch_uri.startswith("riot:"):
        client = _riot_client()
        if client:
            product = game.launch_uri.split(":", 1)[1]
            proc = subprocess.Popen(
                [client, f"--launch-product={product}",
                 "--launch-patchline=live"],
                cwd=os.path.dirname(client))
            log.info("Launched %s via Riot Client (pid %d)", game.name, proc.pid)
            return LaunchResult(True, "launcher", proc=None)

    elif game.launch_uri:
        try:
            os.startfile(game.launch_uri)          # hands off to the launcher
            log.info("Launched %s via %s (%s)", game.name, game.source,
                     game.launch_uri.split(":", 1)[0])
            return LaunchResult(True, "launcher")
        except OSError as exc:
            log.warning("%s URI launch failed (%s), falling back to exe",
                        game.name, exc)

    if game.exe and os.path.isfile(game.exe):
        try:
            proc = subprocess.Popen([game.exe], cwd=os.path.dirname(game.exe))
            log.info("Launched %s directly (%s, pid %d)", game.name,
                     game.source, proc.pid)
            return LaunchResult(True, "exe", proc=proc)
        except OSError as exc:
            return LaunchResult(False, error=f"Could not start exe: {exc}")

    return LaunchResult(False, error=(
        "No launch method available - the platform URI failed and no "
        "executable was matched. Point Nitro Forge at the game's .exe "
        "with 'Add game manually'."))


def wait_for_process(exe_path: str, timeout: float = 120.0,
                     poll: float = 1.5) -> int | None:
    """Wait for a process with the exe's basename to appear; return its pid.

    Used after launcher-URI launches (no child handle) so the Booster can
    still attach priority/affinity tweaks to the real game process.
    """
    target = os.path.basename(exe_path).lower()
    if not target:
        return None
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for p in psutil.process_iter(["name", "pid"]):
            try:
                if (p.info["name"] or "").lower() == target:
                    return p.info["pid"]
            except psutil.Error:
                continue
        time.sleep(poll)
    return None
