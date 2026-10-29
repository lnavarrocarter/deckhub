"""Servidor DeckHub: API JSON de solo lectura + panel web en la red local."""
import argparse
import asyncio
import logging
import time
from pathlib import Path

from aiohttp import web

from . import VERSION, auth, config, routes
from .modules import MODULES, artwork, saves, storage

log = logging.getLogger("deckhub")
WEB = Path(__file__).parent / "web"


async def _safe(name, mod):
    try:
        return await mod.collect()
    except Exception as e:  # un módulo roto no debe tumbar el resto
        log.exception("módulo %s falló", name)
        return {"error": str(e)}


async def api_all(request):
    names = list(MODULES)
    results = await asyncio.gather(*(_safe(n, MODULES[n]) for n in names))
    return web.json_response({"version": VERSION, "time": time.time(), **dict(zip(names, results))})


async def api_module(request):
    name = request.match_info["name"]
    if name not in MODULES:
        raise web.HTTPNotFound(text=f"módulo desconocido: {name}")
    return web.json_response(await _safe(name, MODULES[name]))


async def index(request):
    return web.FileResponse(WEB / "index.html")


async def _automount_loop():
    # Al iniciar y cada 30 s, por si la tarjeta se inserta después.
    while True:
        try:
            await storage.automount_all()
        except Exception:
            log.exception("automontaje falló")
        await asyncio.sleep(30)


async def _start_automount(app):
    app["automount"] = asyncio.create_task(_automount_loop())
    app["artwork"] = asyncio.create_task(artwork.loop())
    app["backups"] = asyncio.create_task(saves.daily_loop())


def main():
    ap = argparse.ArgumentParser(prog="deckhub")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    config.token()  # se genera en el primer arranque
    app = web.Application(middlewares=[auth.middleware, routes.errors], client_max_size=64 * 1024**2)
    app.router.add_get("/", index)
    app.router.add_get("/api", api_all)
    app.router.add_get("/api/auth", auth.auth_status)
    app.router.add_post("/api/auth", auth.auth_login)
    routes.setup(app)  # antes de /api/{name} para que sus rutas tengan prioridad
    app.router.add_get("/api/{name}", api_module)
    app.on_startup.append(_start_automount)
    log.info("DeckHub %s en http://%s:%d", VERSION, args.host, args.port)
    web.run_app(app, host=args.host, port=args.port, print=None, access_log=None)


if __name__ == "__main__":
    main()
