"""
Game catalog + logo pipeline.

core/data/game_catalog.json ships with the app: the top ~2,500 games by
player base (name + Steam appid), generated from public SteamSpy data.
It is used to
  * recognise games found outside Steam (Epic/Riot/manual...) by name, and
  * derive box art without shipping megabytes of images.

Logos resolve in this order (fast -> slow, never blocking a scan):
  1. Steam's local library cache (instant, already on disk for Steam games)
  2. our own disk cache  %LOCALAPPDATA%/NitroForge/logos/<appid>.jpg
  3. lazy download from Steam's public CDN (only when the UI asks for that
     specific image, one at a time - the library grid never stalls on it)

If no appid can be determined the UI shows its "Unverified Game" artwork.
"""
from __future__ import annotations

import json
import re
import threading
import urllib.error
import urllib.request
from functools import lru_cache
from pathlib import Path

from core import config
from core.logger import get_logger

_CDN = "https://cdn.cloudflare.steamstatic.com/steam/apps"
# portrait first (Steam-style grid tile), classic header as fallback
_ART_VARIANTS = ("library_600x900.jpg", "header.jpg")

_dl_lock = threading.Lock()


def _normalize(name: str) -> str:
    """Fold a game title down for fuzzy-ish exact matching."""
    low = name.lower()
    low = re.sub(r"[™®©]", "", low)               # tm/r/c marks
    low = re.sub(r"\b(goty|game of the year|definitive|deluxe|ultimate|"
                 r"complete|remastered|enhanced|standard)( edition)?\b",
                 "", low)
    low = re.sub(r"[^a-z0-9]+", "", low)
    return low


@lru_cache(maxsize=1)
def _catalog() -> dict[str, int]:
    """normalized-name -> appid map, loaded once (~115 KB json)."""
    try:
        entries = json.loads(
            config.GAME_CATALOG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        get_logger().warning("Game catalog unavailable: %s", exc)
        return {}
    out: dict[str, int] = {}
    for e in entries:
        key = _normalize(e["name"])
        if key and key not in out:
            out[key] = int(e["appid"])
    return out


def match_appid(name: str) -> int | None:
    """Look a title up in the shipped catalog (exact normalized match)."""
    return _catalog().get(_normalize(name))


def catalog_size() -> int:
    return len(_catalog())


# ------------------------------------------------------------------- logos
def _steam_library_cache_dirs() -> list[Path]:
    # imported lazily to avoid a circular import at module load
    from core.game_scanner import _steam_roots
    return [r / "appcache" / "librarycache" for r in _steam_roots()]


def logo_path(appid: int, download: bool = True) -> Path | None:
    """Return a local jpg for the appid, fetching/caching it if needed."""
    config.LOGO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached = config.LOGO_CACHE_DIR / f"{appid}.jpg"
    if cached.is_file() and cached.stat().st_size > 0:
        return cached

    # 1. steal from Steam's own library cache (no network, instant)
    for lib in _steam_library_cache_dirs():
        for variant in (f"{appid}_library_600x900.jpg", f"{appid}_header.jpg"):
            src = lib / variant
            if src.is_file():
                try:
                    cached.write_bytes(src.read_bytes())
                    return cached
                except OSError:
                    pass

    if not download:
        return None

    # 2. lazy CDN download (serialised; a burst of <img> loads won't stampede)
    with _dl_lock:
        if cached.is_file() and cached.stat().st_size > 0:
            return cached
        for variant in _ART_VARIANTS:
            req = urllib.request.Request(
                f"{_CDN}/{appid}/{variant}",
                headers={"User-Agent": f"NitroForge/{config.APP_VERSION}"})
            try:
                with urllib.request.urlopen(req, timeout=6) as resp:
                    data = resp.read()
                if data:
                    cached.write_bytes(data)
                    return cached
            except (urllib.error.URLError, OSError):
                continue
    return None
