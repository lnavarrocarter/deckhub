"""Tiempo de juego de la biblioteca de Steam.

Steam solo lo expone completo (juegos y accesos directos) en su interfaz: el plugin
lo envía cada pocos minutos y aquí se guarda para el panel web.
"""
import json
import time
from pathlib import Path

CACHE = Path.home() / ".cache/deckhub/playtime.json"
FIELDS = {"appid": int, "name": str, "shortcut": bool, "minutes": int,
          "minutes_2w": int, "last_played": int, "installed": bool, "hidden": bool, "deck_compat": int}


def store(apps, compat_tools=None):
    if not isinstance(apps, list):
        raise ValueError("se esperaba una lista de juegos")
    clean = []
    for a in apps:
        try:
            clean.append({k: t(a.get(k) or t()) for k, t in FIELDS.items()})
        except (TypeError, ValueError, AttributeError):
            continue
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    tmp = CACHE.with_suffix(".tmp")
    tools = [{"name": str(t.get("name")), "display": str(t.get("display"))}
             for t in (compat_tools or []) if isinstance(t, dict) and t.get("name")]
    tmp.write_text(json.dumps({"updated": time.time(), "apps": clean, "compat_tools": tools}))
    tmp.replace(CACHE)
    return len(clean)


def load():
    try:
        data = json.loads(CACHE.read_text())
    except (OSError, ValueError):
        return {"updated": None, "apps": [], "total_minutes": 0, "compat_tools": []}
    apps = sorted(data["apps"], key=lambda a: a["minutes"], reverse=True)
    return {"updated": data["updated"], "apps": apps, "compat_tools": data.get("compat_tools", []),
            "total_minutes": sum(a["minutes"] for a in apps)}
