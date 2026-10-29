"""Actualizaciones de DeckHub desde GitHub Releases.

DeckHub no está en la tienda de Decky, así que busca versiones nuevas por su cuenta y
le pide a Decky que instale el zip del release (Decky muestra su confirmación y
comprueba la huella SHA-256 del archivo).
"""
import hashlib
import logging
import re
import time

import aiohttp

from .. import VERSION
from . import artwork, custom

log = logging.getLogger("deckhub.updates")
REPO = "lnavarrocarter/deckhub"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
ASSET = "DeckHub.zip"
CHECK_EVERY = 6 * 3600
_cache = {"time": 0, "data": None}


def _ver(v):
    """«v0.12.0» → (0, 12, 0) para comparar versiones."""
    return tuple(int(x) for x in re.findall(r"\d+", v or "")[:3]) or (0,)


async def check(force=False):
    if not force and _cache["data"] and time.time() - _cache["time"] < CHECK_EVERY:
        return _cache["data"]
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20),
                                     headers={"User-Agent": f"DeckHub/{VERSION}", "Accept": "application/vnd.github+json"}) as s:
        try:
            async with s.get(API) as r:
                if r.status == 404:
                    rel = None
                else:
                    r.raise_for_status()
                    rel = await r.json()
        except Exception as e:
            raise RuntimeError(f"GitHub no responde: {artwork.describe(e)}")
    latest = rel["tag_name"].lstrip("v") if rel else None
    asset = next((a for a in (rel or {}).get("assets", []) if a["name"] == ASSET), None)
    data = {"current": VERSION, "latest": latest, "newer": bool(latest and asset and _ver(latest) > _ver(VERSION)),
            "notes": (rel or {}).get("body", ""), "url": (rel or {}).get("html_url"),
            "published": (rel or {}).get("published_at"), "artifact": asset["browser_download_url"] if asset else None,
            "checked": time.time()}
    _cache.update(time=time.time(), data=data)
    return data


async def install():
    """Descarga el zip para calcular su huella y pide a Decky (vía el plugin) que lo instale."""
    info = await check(force=True)
    if not info["newer"]:
        raise ValueError(f"Ya tienes la última versión ({VERSION}).")
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120),
                                     headers={"User-Agent": f"DeckHub/{VERSION}"}) as s:
        try:
            async with s.get(info["artifact"]) as r:
                r.raise_for_status()
                blob = await r.read()
        except Exception as e:
            raise RuntimeError(f"No pude descargar la actualización: {artwork.describe(e)}")
    sha = hashlib.sha256(blob).hexdigest()
    # install_type 2 = UPDATE en Decky
    custom._queue_action({"type": "install", "name": "DeckHub", "version": info["latest"], "hash": sha,
                          "artifact": info["artifact"], "install_type": 2})
    log.info("actualización %s → %s pedida a Decky (sha256 %s)", VERSION, info["latest"], sha[:12])
    return {"version": info["latest"]}
