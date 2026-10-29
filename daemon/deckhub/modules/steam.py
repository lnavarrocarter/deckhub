"""Biblioteca de Steam: bibliotecas, juegos instalados y juego en ejecución."""
import re
from pathlib import Path

import psutil

from ..util import cached

STEAM = Path.home() / ".local/share/Steam"
_KV = re.compile(r'"([^"]*)"\s*(?:"([^"]*)"|(\{))')


def parse_vdf(text):
    """Parser mínimo de VDF de texto (appmanifest, libraryfolders)."""
    root, stack = {}, []
    cur = root
    pos = 0
    while True:
        m = _KV.search(text, pos)
        close = text.find("}", pos)
        if close != -1 and (m is None or close < m.start()):
            cur = stack.pop() if stack else root
            pos = close + 1
            continue
        if m is None:
            break
        key, val, brace = m.groups()
        if brace:
            new = {}
            cur[key] = new
            stack.append(cur)
            cur = new
        else:
            cur[key] = val
        pos = m.end()
    return root


def _libraries():
    try:
        data = parse_vdf((STEAM / "steamapps/libraryfolders.vdf").read_text(errors="replace"))
    except OSError:
        return [STEAM]
    libs = [Path(v["path"]) for v in data.get("libraryfolders", {}).values()
            if isinstance(v, dict) and "path" in v]
    return libs or [STEAM]


def _running_appid():
    for p in psutil.process_iter(["cmdline"]):
        for arg in p.info["cmdline"] or []:
            if arg.startswith("AppId="):
                return arg.split("=", 1)[1]
    return None


@cached(60)
async def _library():
    libraries, games = [], []
    for lib in _libraries():
        apps = lib / "steamapps"
        count = 0
        for acf in apps.glob("appmanifest_*.acf"):
            try:
                app = parse_vdf(acf.read_text(errors="replace")).get("AppState", {})
            except OSError:
                continue
            count += 1
            games.append({
                "appid": app.get("appid"),
                "name": app.get("name"),
                "size": int(app.get("SizeOnDisk") or 0),
                "last_played": int(app.get("LastPlayed") or 0),
                "library": str(lib),
            })
        libraries.append({"path": str(lib), "games": count, "exists": apps.exists()})
    # Herramientas de Steam (Proton, runtimes) no son juegos.
    games = [g for g in games if g["name"] and not re.match(
        r"(Proton|Steam Linux Runtime|Steamworks Common)", g["name"])]
    games.sort(key=lambda g: g["size"], reverse=True)
    users = [p.name for p in (STEAM / "userdata").glob("*") if p.name.isdigit()]
    return {"libraries": libraries, "games": games, "users": users,
            "total_size": sum(g["size"] for g in games)}


async def collect():
    lib = await _library()
    appid = _running_appid()
    running = next((g for g in lib["games"] if g["appid"] == appid), None) if appid else None
    return {**lib, "running": running or ({"appid": appid} if appid else None)}
