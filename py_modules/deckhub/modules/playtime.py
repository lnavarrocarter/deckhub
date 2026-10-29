"""Tiempo de juego de la biblioteca de Steam.

Steam solo lo expone completo (juegos y accesos directos) en su interfaz: el plugin
lo envía cada pocos minutos y aquí se guarda para el panel web.
"""
import json
import time
from pathlib import Path

CACHE = Path.home() / ".cache/deckhub/playtime.json"
FIELDS = {"appid": int, "name": str, "shortcut": bool, "minutes": int,
          "minutes_2w": int, "last_played": int, "installed": bool}


def store(apps):
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
    tmp.write_text(json.dumps({"updated": time.time(), "apps": clean}))
    tmp.replace(CACHE)
    return len(clean)


def load():
    try:
        data = json.loads(CACHE.read_text())
    except (OSError, ValueError):
        return {"updated": None, "apps": [], "total_minutes": 0}
    apps = sorted(data["apps"], key=lambda a: a["minutes"], reverse=True)
    return {"updated": data["updated"], "apps": apps,
            "total_minutes": sum(a["minutes"] for a in apps)}
