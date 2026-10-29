"""Acceso: el resumen es público en la red local; todo lo demás pide el token.

El token se acepta en la cabecera X-DeckHub-Token o en una cookie que se fija
con POST /api/auth, para que las descargas desde el navegador funcionen.
"""
import hmac

from aiohttp import web

from . import config

COOKIE = "deckhub_token"
PUBLIC_GET = {"/", "/api", "/api/auth", "/api/i18n"}
PUBLIC_MODULES = {"system", "storage", "network", "steam", "services"}


def _is_public(request):
    if request.method != "GET":
        return request.path == "/api/auth"
    if request.path in PUBLIC_GET:
        return True
    parts = request.path.strip("/").split("/")
    return len(parts) == 2 and parts[0] == "api" and parts[1] in PUBLIC_MODULES


def is_authed(request):
    given = request.headers.get("X-DeckHub-Token") or request.cookies.get(COOKIE) or ""
    return hmac.compare_digest(given.encode(), config.token().encode())


@web.middleware
async def middleware(request, handler):
    if not _is_public(request) and not is_authed(request):
        return web.json_response({"error": "token requerido"}, status=401)
    return await handler(request)


async def auth_status(request):
    return web.json_response({"authed": is_authed(request)})


async def auth_login(request):
    body = await request.json()
    if not hmac.compare_digest(str(body.get("token", "")).encode(), config.token().encode()):
        return web.json_response({"error": "token incorrecto"}, status=403)
    resp = web.json_response({"authed": True})
    resp.set_cookie(COOKIE, config.token(), httponly=True, samesite="Strict", max_age=3600 * 24 * 365)
    return resp
