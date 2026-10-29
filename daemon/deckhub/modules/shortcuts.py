"""Accesos directos de Steam para juegos retro.

Solo el cliente de Steam puede crear accesos directos sin reiniciarse, así que el
daemon guarda una cola de peticiones y el plugin de Decky (que corre dentro de
Steam) la aplica con SteamClient y confirma el appid resultante.
"""
import json
import time

from .. import config
from . import emulators, packages, roms

STORE = config.DIR / "shortcuts.json"
FLATPAK = "/usr/bin/flatpak"


def _load():
    try:
        return json.loads(STORE.read_text())
    except (OSError, ValueError):
        return {}


def _save(data):
    config.DIR.mkdir(parents=True, exist_ok=True)
    tmp = STORE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    tmp.replace(STORE)


def _quote(arg):
    return '"' + arg.replace('"', '\\"') + '"' if any(c in arg for c in ' "\'()[]&;') else arg


async def _launchers():
    """Emulador preferido instalado por consola (el orden del catálogo manda)."""
    installed = {a["id"] for a in (await packages.collect())["apps"]}
    out = {}
    for e in emulators.CATALOG:
        if e["id"] in installed and "launch" in e:
            for c in e["consoles"]:
                out.setdefault(c, e)
    return out


async def collect():
    data = _load()
    launchers = await _launchers()
    return {
        "shortcuts": data,
        "supported": {c: e["name"] for c, e in launchers.items()},
    }


async def request_add(paths):
    games = {g["path"]: g for g in (await roms.collect())["games"]}
    launchers = await _launchers()
    data, added, skipped = _load(), 0, []
    for path in paths:
        g = games.get(path)
        if g is None:
            skipped.append(f"{path}: no es un juego detectado")
            continue
        if g.get("kind") in ("update", "dlc"):
            skipped.append(f"{g['title']}: las actualizaciones y DLC no se abren por separado")
            continue
        emu = launchers.get(g["console"])
        if emu is None:
            skipped.append(f"{g['title']}: no hay emulador instalado para {g['console_name']}")
            continue
        cur = data.get(path)
        if cur and cur["status"] in ("added", "pending_add"):
            continue
        args = ["run"] + [a.replace("{rom}", path) for a in emu["launch"]]
        data[path] = {
            "title": g["title"], "console": g["console"], "console_name": g["console_name"],
            "emulator": emu["name"], "exe": FLATPAK, "start_dir": "/usr/bin/",
            "launch_options": " ".join(_quote(a) for a in args),
            "collection": f"{g['console_name']}",
            "appid": cur.get("appid") if cur else None, "art": None,
            "status": "pending_add", "error": None, "requested": time.time(),
        }
        added += 1
    _save(data)
    return {"queued": added, "skipped": skipped}


def request_remove(paths):
    data, n = _load(), 0
    for path in paths:
        cur = data.get(path)
        if not cur:
            continue
        if cur.get("appid"):
            cur["status"], cur["error"] = "pending_remove", None
        else:
            data.pop(path)  # nunca llegó a crearse
        n += 1
    _save(data)
    return {"queued": n}


def pending():
    return [{"key": k, **v} for k, v in _load().items()
            if v["status"] in ("pending_add", "pending_remove")]


def ack(key, appid=None, removed=False, error=None):
    data = _load()
    cur = data.get(key)
    if cur is None:
        return
    if error:
        cur["error"] = error
        cur["status"] = "error"
    elif removed:
        data.pop(key)
    else:
        cur.update(appid=appid, status="added", error=None, added=time.time())
        if config.load().get("auto_artwork"):
            cur["art"] = {"status": "wanted"}
    _save(data)


# --- Portadas -----------------------------------------------------------------
# art.status: wanted (buscar) → ready (descargadas, el plugin las aplica) → applied | error

def items():
    return list(_load().items())


def set_art(key, art):
    data = _load()
    if key in data:
        data[key]["art"] = art
        _save(data)


def request_art(paths=None):
    """Vuelve a buscar portadas (de esos juegos, o de todos los que están en Steam)."""
    data, n = _load(), 0
    for k, v in data.items():
        if v["status"] == "added" and (paths is None or k in paths):
            v["art"] = {"status": "wanted"}
            n += 1
    _save(data)
    return {"queued": n}


def pending_art():
    return [{"key": k, "appid": v["appid"], "title": v["title"], "images": v["art"]["images"]}
            for k, v in _load().items()
            if v["status"] == "added" and (v.get("art") or {}).get("status") == "ready"]


def ack_art(key, error=None):
    data = _load()
    cur = data.get(key)
    if cur and cur.get("art"):
        cur["art"]["status"] = "error" if error else "applied"
        cur["art"]["error"] = error
        _save(data)
