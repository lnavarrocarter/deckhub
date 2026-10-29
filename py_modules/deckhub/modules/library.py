"""Biblioteca unificada: juegos de Steam, ROMs detectadas y accesos directos, con el
detalle de cada uno y las acciones que el plugin aplica dentro de Steam.
"""
import json
import time
from pathlib import Path

import aiohttp

from . import custom, playtime, roms, shortcuts, steam

STEAM = steam.STEAM
# Estados de compatibilidad con Steam Deck (SteamAppOverview.steam_deck_compat_category).
DECK_COMPAT = {0: "Desconocido", 1: "No compatible", 2: "Jugable", 3: "Verificado"}
_vdf_cache = {}


def _vdf(path):
    """VDF de texto parseado y cacheado por fecha de modificación."""
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return {}
    hit = _vdf_cache.get(path)
    if hit and hit[0] == mtime:
        return hit[1]
    data = steam.parse_vdf(path.read_text(errors="replace"))
    _vdf_cache[path] = (mtime, data)
    return data


def _ci(d, *keys):
    """Navega claves de VDF sin distinguir mayúsculas (Steam mezcla «Apps» y «apps»)."""
    for k in keys:
        if not isinstance(d, dict):
            return {}
        d = next((v for kk, v in d.items() if kk.lower() == k.lower()), {})
    return d


def _localconfig():
    users = sorted((STEAM / "userdata").glob("*/config/localconfig.vdf"),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    return _vdf(users[0]) if users else {}


def _manifests():
    out = {}
    for lib in steam._libraries():
        for acf in (lib / "steamapps").glob("appmanifest_*.acf"):
            app = _vdf(acf).get("AppState", {})
            if app.get("appid"):
                out[int(app["appid"])] = {**app, "library": str(lib)}
    return out


def _compat_tools(manifests):
    """Versiones de Proton instaladas, con el nombre interno que usa Steam
    (proton_experimental, proton_10, proton_63…) y las de compatibilitytools.d."""
    tools = []
    for m in manifests.values():
        name = m.get("name", "")
        if name in ("Proton Experimental", "Proton - Experimental"):
            tools.append(("proton_experimental", name))
        elif name == "Proton Hotfix":
            tools.append(("proton_hotfix", name))
        elif name.startswith("Proton ") and name[7:].replace(".", "").isdigit():
            major, _, minor = name[7:].partition(".")
            tools.append((f"proton_{major}" if int(major) >= 7 else f"proton_{major}{minor}", name))
    for vdf in (STEAM / "compatibilitytools.d").glob("*/compatibilitytool.vdf"):
        for key, info in _ci(_vdf(vdf), "compatibilitytools", "compat_tools").items():
            if isinstance(info, dict):
                tools.append((key, info.get("display_name", key)))
    return [{"name": n, "display": d} for n, d in sorted(set(tools), key=lambda t: t[1], reverse=True)]


async def collect():
    pt = playtime.load()
    apps = {a["appid"]: a for a in pt["apps"]}
    manifests = _manifests()
    sc = dict(shortcuts.items())
    sc_by_appid = {s["appid"]: path for path, s in sc.items() if s.get("appid")}
    items = []
    for a in apps.values():
        if a["shortcut"]:
            if a["appid"] in sc_by_appid:
                continue  # se muestra como ROM
            items.append({"key": f"sc:{a['appid']}", "source": "shortcut", "title": a["name"], "appid": a["appid"],
                          "installed": True, "minutes": a["minutes"], "last_played": a["last_played"],
                          "hidden": a.get("hidden", False), "size": None})
            continue
        m = manifests.get(a["appid"], {})
        items.append({"key": f"steam:{a['appid']}", "source": "steam", "title": a["name"], "appid": a["appid"],
                      "installed": a["installed"], "minutes": a["minutes"], "last_played": a["last_played"],
                      "hidden": a.get("hidden", False), "deck_compat": a.get("deck_compat"),
                      "size": int(m.get("SizeOnDisk") or 0) or None})
    for g in (await roms.collect())["games"]:
        s = sc.get(g["path"]) or {}
        appid = s.get("appid") if s.get("status") == "added" else None
        p = apps.get(appid, {}) if appid else {}
        items.append({"key": f"rom:{g['path']}", "source": "rom", "title": g["title"], "appid": appid,
                      "installed": True, "minutes": p.get("minutes", 0), "last_played": p.get("last_played", 0),
                      "hidden": p.get("hidden", False), "size": g.get("size"), "console": g["console"],
                      "console_name": g["console_name"], "kind": g.get("kind"), "path": g["path"],
                      "steam_status": s.get("status"), "has_updates": bool(g.get("updates") or g.get("dlc"))})
    return {"items": items, "updated": pt["updated"], "compat_tools": pt.get("compat_tools") or _compat_tools(manifests)}


_protondb = {}


async def _protondb_summary(appid):
    hit = _protondb.get(appid)
    if hit and time.time() - hit[0] < 86400:
        return hit[1]
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as s:
            async with s.get(f"https://www.protondb.com/api/v1/reports/summaries/{appid}.json") as r:
                data = await r.json() if r.status == 200 else None
    except Exception:
        data = None
    _protondb[appid] = (time.time(), data)
    return data


async def detail(key):
    kind, _, ident = key.partition(":")
    pt = {a["appid"]: a for a in playtime.load()["apps"]}
    if kind == "steam":
        appid = int(ident)
        a = pt.get(appid, {})
        m = _manifests().get(appid, {})
        launch = _ci(_localconfig(), "UserLocalConfigStore", "Software", "Valve", "Steam", "apps", str(appid))
        compat = _ci(_vdf(STEAM / "config/config.vdf"), "InstallConfigStore", "Software", "Valve", "Steam",
                     "CompatToolMapping", str(appid))
        install_dir = Path(m["library"]) / "steamapps/common" / m["installdir"] if m.get("installdir") else None
        flags = int(m.get("StateFlags") or 0)
        return {
            "key": key, "source": "steam", "appid": appid, "title": a.get("name") or m.get("name"),
            "installed": bool(m), "minutes": a.get("minutes", 0), "minutes_2w": a.get("minutes_2w", 0),
            "last_played": a.get("last_played", 0), "hidden": a.get("hidden", False),
            "deck_compat": DECK_COMPAT.get(a.get("deck_compat")), "size": int(m.get("SizeOnDisk") or 0) or None,
            "install_dir": str(install_dir) if install_dir else None, "library": m.get("library"),
            "buildid": m.get("buildid"), "last_updated": int(m.get("LastUpdated") or 0) or None,
            "update_pending": bool(flags & 2) or int(m.get("BytesToDownload") or 0) > int(m.get("BytesDownloaded") or 0),
            "launch_options": launch.get("LaunchOptions", "") if isinstance(launch, dict) else "",
            "compat_tool": compat.get("name", "") if isinstance(compat, dict) else "",
            "protondb": await _protondb_summary(appid),
            "store_url": f"https://store.steampowered.com/app/{appid}",
            "art": custom.art_current(appid),
        }
    if kind == "rom":
        g = next((g for g in (await roms.collect())["games"] if g["path"] == ident), None)
        if g is None:
            raise ValueError("Ese juego ya no está (¿se desmontó la tarjeta?).")
        s = dict(shortcuts.items()).get(ident) or {}
        appid = s.get("appid") if s.get("status") == "added" else None
        a = pt.get(appid, {}) if appid else {}
        return {
            "key": key, "source": "rom", "appid": appid, "title": g["title"], "installed": True,
            "minutes": a.get("minutes", 0), "last_played": a.get("last_played", 0), "hidden": a.get("hidden", False),
            "rom": g, "steam": {k: s.get(k) for k in ("status", "emulator", "exe", "launch_options", "collection", "error")},
            "art": custom.art_current(appid) if appid else None,
        }
    if kind == "sc":
        appid = int(ident)
        a = pt.get(appid, {})
        return {"key": key, "source": "shortcut", "appid": appid, "title": a.get("name"), "installed": True,
                "minutes": a.get("minutes", 0), "last_played": a.get("last_played", 0),
                "hidden": a.get("hidden", False), "art": custom.art_current(appid)}
    raise ValueError(f"clave no válida: {key}")


# Cola de descargas de Steam, tal como la envía el plugin.
DOWNLOADS = Path.home() / ".cache/deckhub/downloads.json"


def store_downloads(items):
    if not isinstance(items, list):
        raise ValueError("se esperaba una lista")
    DOWNLOADS.parent.mkdir(parents=True, exist_ok=True)
    DOWNLOADS.write_text(json.dumps({"updated": time.time(), "items": items[:200]}))


def downloads():
    try:
        d = json.loads(DOWNLOADS.read_text())
    except (OSError, ValueError):
        return {"updated": None, "items": [], "pending": 0, "bytes": 0}
    pend = [i for i in d["items"] if not i.get("completed") and not i.get("active")]
    return {**d, "pending": len(pend), "bytes": sum(int(i.get("bytes") or 0) for i in pend)}


def download_all():
    custom._queue_action({"type": "downloads_all"})


# Acciones dentro de Steam: las aplica el plugin con SteamClient.
STEAM_ACTIONS = {"run", "launch_options", "compat_tool", "hidden", "shortcut_launch_options"}


def steam_action(action, appid, value=None):
    if action not in STEAM_ACTIONS:
        raise ValueError(f"acción no válida: {action}")
    appid = int(appid)
    if action in ("launch_options", "shortcut_launch_options", "compat_tool"):
        value = str(value or "")
        if len(value) > 1000 or "\n" in value:
            raise ValueError("Valor no válido.")
    if action == "shortcut_launch_options":
        # Mantener la cola de accesos directos en sincronía con lo que hay en Steam.
        data = shortcuts._load()
        for s in data.values():
            if s.get("appid") == appid:
                s["launch_options"] = value
        shortcuts._save(data)
    custom._queue_action({"type": "steam", "name": f"{action}:{appid}", "action": action,
                          "appid": appid, "value": value})
