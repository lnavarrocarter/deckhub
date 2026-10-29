"""Configuración persistente y token de acceso en ~/.config/deckhub."""
import json
import os
import secrets
from pathlib import Path

DIR = Path.home() / ".config/deckhub"
CONFIG = DIR / "config.json"
TOKEN = DIR / "token"

DEFAULTS = {
    "automount": [],          # UUIDs de particiones a montar al iniciar
    "steamgriddb_key": "",    # clave API de SteamGridDB para portadas
    "auto_artwork": True,     # buscar portadas al agregar un juego a Steam
    "backup_daily": True,     # respaldo diario de partidas guardadas
    "backup_keep": 10,        # respaldos que se conservan por emulador
}


def load():
    try:
        return {**DEFAULTS, **json.loads(CONFIG.read_text())}
    except (OSError, ValueError):
        return dict(DEFAULTS)


def save(cfg):
    DIR.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, indent=2))
    tmp.replace(CONFIG)


def token():
    """Lee el token o lo genera la primera vez (solo legible por el usuario)."""
    try:
        t = TOKEN.read_text().strip()
        if t:
            return t
    except OSError:
        pass
    DIR.mkdir(parents=True, exist_ok=True)
    t = secrets.token_urlsafe(18)
    fd = os.open(TOKEN, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(t + "\n")
    return t
