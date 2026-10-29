"""Portadas desde SteamGridDB para los accesos directos de Steam.

El daemon busca y descarga las imágenes; el plugin las aplica con
SteamClient.Apps.SetCustomArtworkForApp (Steam no las recarga desde disco en vivo).
"""
import asyncio
import logging
import time
from pathlib import Path
from urllib.parse import quote

import aiohttp

from .. import config
from . import shortcuts

log = logging.getLogger("deckhub.artwork")
API = "https://www.steamgriddb.com/api/v2"
CACHE = Path.home() / ".cache/deckhub/art"
# Tipo de recurso de Steam -> (endpoint, parámetros). Steam: 0 portada, 1 fondo, 2 logo, 3 horizontal.
KINDS = {
    "grid": (0, "grids", {"dimensions": "600x900", "types": "static"}),
    "hero": (1, "heroes", {"types": "static"}),
    "logo": (2, "logos", {"types": "static"}),
    "wide": (3, "grids", {"dimensions": "920x430,460x215", "types": "static"}),
}


class ArtError(RuntimeError):
    pass


def _key():
    k = config.load().get("steamgriddb_key", "").strip()
    if not k:
        raise ArtError("Falta la clave de SteamGridDB (pestaña Ajustes).")
    return k


async def _get(session, path, params=None):
    async with session.get(API + path, params=params,
                           headers={"Authorization": f"Bearer {_key()}"}) as r:
        if r.status == 401:
            raise ArtError("La clave de SteamGridDB no es válida.")
        if r.status == 404:
            return []
        r.raise_for_status()
        body = await r.json()
        return body.get("data") or []


async def check_key():
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as s:
        await _get(s, "/search/autocomplete/" + quote("mario"))
    return True


async def fetch(appid, title):
    """Descarga las 4 imágenes de un juego. Devuelve {tipo: {"file", "asset"}}."""
    out = {}
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as s:
        results = await _get(s, "/search/autocomplete/" + quote(title, safe=""))
        if not results:
            raise ArtError(f"SteamGridDB no encontró «{title}».")
        game_id = results[0]["id"]
        folder = CACHE / str(appid)
        folder.mkdir(parents=True, exist_ok=True)
        for name, (asset, endpoint, params) in KINDS.items():
            items = await _get(s, f"/{endpoint}/game/{game_id}", params)
            if not items:
                continue
            url = items[0]["url"]
            ext = "png" if url.lower().endswith(".png") else "jpg"
            dest = folder / f"{name}.{ext}"
            async with s.get(url) as r:
                r.raise_for_status()
                dest.write_bytes(await r.read())
            out[name] = {"file": str(dest), "asset": asset, "ext": ext}
    if not out:
        raise ArtError(f"«{title}» no tiene imágenes en SteamGridDB.")
    return out


def describe(e):
    """Mensaje legible para errores de red (TimeoutError y similares llegan sin texto)."""
    if isinstance(e, (asyncio.TimeoutError, TimeoutError)):
        return ("tiempo de espera agotado al conectar con www.steamgriddb.com: la red del Deck "
                "no llega a SteamGridDB (revisa IPv6, el router o el filtro DNS)")
    if isinstance(e, aiohttp.ClientConnectorError):
        return f"no se pudo conectar con www.steamgriddb.com ({e.os_error or e})"
    return str(e) or type(e).__name__


# Último fallo de red, visible en Ajustes. Con la red caída no se insiste juego por
# juego: se espera cada vez más (1 → 10 min) antes de volver a probar.
NET = {"error": None, "since": None, "retry_at": 0.0, "backoff": 0}


def net_status():
    return {"error": NET["error"], "since": NET["since"]}


async def process_queue():
    """Busca portadas de los accesos directos creados que aún no las tienen."""
    if not config.load().get("steamgriddb_key") or time.time() < NET["retry_at"]:
        return
    for key, s in shortcuts.items():
        art = s.get("art") or {}
        if s["status"] != "added" or art.get("status") not in (None, "wanted"):
            continue
        try:
            images = await fetch(s["appid"], s["title"])
            shortcuts.set_art(key, {"status": "ready", "images": images})
        except ArtError as e:
            shortcuts.set_art(key, {"status": "error", "error": str(e)})
        except Exception as e:  # red o SteamGridDB caído: se reintenta más tarde
            NET["backoff"] = min(600, max(60, NET["backoff"] * 2))
            NET["retry_at"] = time.time() + NET["backoff"]
            if NET["error"] is None:
                NET["since"] = time.time()
            NET["error"] = describe(e)
            log.warning("portadas en pausa %d s: %s", NET["backoff"], NET["error"])
            return
        NET.update(error=None, since=None, backoff=0)


def retry_now():
    NET["retry_at"] = 0.0


async def loop():
    while True:
        try:
            await process_queue()
        except Exception:
            log.exception("cola de portadas")
        await asyncio.sleep(20)
