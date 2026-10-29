"""Personalización: portadas de cualquier juego, videos de arranque, fondo de
escritorio y temas del modo juego (instalados para CSS Loader).
"""
import asyncio
import json
import shutil
import subprocess
import tempfile
import time
import uuid
import zipfile
from pathlib import Path
from urllib.parse import quote, urlparse

import aiohttp

from .. import fileops
from ..ini import Ini
from . import artwork

HOME = Path.home()
CONF = HOME / ".config/deckhub"

# --- Portadas de cualquier juego -----------------------------------------------

ART_QUEUE = CONF / "custom-art.json"
ART_CACHE = HOME / ".cache/deckhub/art/custom"
# Las portadas se descargan solo desde SteamGridDB.
ART_HOSTS = ("steamgriddb.com",)


def _load_queue():
    try:
        return json.loads(ART_QUEUE.read_text())
    except (OSError, ValueError):
        return []


def _save_queue(q):
    CONF.mkdir(parents=True, exist_ok=True)
    tmp = ART_QUEUE.with_suffix(".tmp")
    tmp.write_text(json.dumps(q, indent=1))
    tmp.replace(ART_QUEUE)


async def art_options(appid, kind, title="", shortcut=False):
    """Opciones de SteamGridDB para un juego: por AppID de Steam o, si es un acceso
    directo, buscando por título."""
    if kind not in artwork.KINDS:
        raise ValueError(f"tipo de imagen no válido: {kind}")
    _, endpoint, params = artwork.KINDS[kind]
    params = {k: v for k, v in params.items() if k != "types"}
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as s:
        try:
            if shortcut:
                found = await artwork._get(s, "/search/autocomplete/" + quote(title, safe=""))
                if not found:
                    return []
                items = await artwork._get(s, f"/{endpoint}/game/{found[0]['id']}", params)
            else:
                items = await artwork._get(s, f"/{endpoint}/steam/{int(appid)}", params)
        except artwork.ArtError:
            raise
        except Exception as e:
            raise RuntimeError(artwork.describe(e))
    return [{"url": i["url"], "thumb": i.get("thumb") or i["url"], "width": i.get("width"),
             "height": i.get("height"), "style": i.get("style")} for i in items[:30]]


async def art_apply(appid, kind, url):
    if kind not in artwork.KINDS:
        raise ValueError(f"tipo de imagen no válido: {kind}")
    host = urlparse(url).hostname or ""
    if urlparse(url).scheme != "https" or not any(host == h or host.endswith("." + h) for h in ART_HOSTS):
        raise ValueError("Solo se aceptan imágenes de SteamGridDB.")
    asset = artwork.KINDS[kind][0]
    ext = "png" if url.lower().endswith(".png") else "jpg"
    dest = ART_CACHE / str(int(appid)) / f"{kind}.{ext}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as s:
        try:
            async with s.get(url) as r:
                r.raise_for_status()
                dest.write_bytes(await r.read())
        except Exception as e:
            raise RuntimeError(artwork.describe(e))
    q = _load_queue()
    q.append({"id": uuid.uuid4().hex[:12], "appid": int(appid), "kind": kind,
              "images": {kind: {"file": str(dest), "asset": asset, "ext": ext}}, "reset": []})
    _save_queue(q)


def art_reset(appid, kinds):
    kinds = kinds or list(artwork.KINDS)
    bad = [k for k in kinds if k not in artwork.KINDS]
    if bad:
        raise ValueError(f"tipo de imagen no válido: {bad}")
    q = _load_queue()
    q.append({"id": uuid.uuid4().hex[:12], "appid": int(appid), "kind": ",".join(kinds),
              "images": {}, "reset": [artwork.KINDS[k][0] for k in kinds]})
    _save_queue(q)


def pending_art():
    """Mismo formato que shortcuts.pending_art, con clave «custom:<id>»."""
    return [{"key": f"custom:{i['id']}", "appid": i["appid"], "title": "", "images": i["images"],
             "reset": i["reset"]} for i in _load_queue()]


def ack_art(item_id, error=None):
    _save_queue([i for i in _load_queue() if i["id"] != item_id])


# --- Videos de arranque --------------------------------------------------------

MOVIES = HOME / ".local/share/Steam/config/uioverrides/movies"
# Si existe, Steam lo usa siempre en lugar del video elegido en Personalización.
DEFAULT_MOVIE = "deck_startup.webm"


def movies():
    MOVIES.mkdir(parents=True, exist_ok=True)
    return {"dir": str(MOVIES),
            "items": [{"name": p.name, "size": p.stat().st_size, "default": p.name == DEFAULT_MOVIE}
                      for p in sorted(MOVIES.glob("*.webm"))]}


def check_movie(path):
    p = fileops.safe(path)
    if p.parent != MOVIES or p.suffix.lower() != ".webm":
        fileops.trash([str(p)])
        raise ValueError("Steam solo acepta videos .webm.")
    return p


def movie_set_default(name):
    src = check_movie(str(MOVIES / name))
    dst = MOVIES / DEFAULT_MOVIE
    if src == dst:
        return
    if dst.exists():
        fileops.trash([str(dst)])
    shutil.copy2(src, dst)


def movie_clear_default():
    dst = MOVIES / DEFAULT_MOVIE
    if dst.exists():
        fileops.trash([str(dst)])


def movie_delete(name):
    fileops.trash([str(check_movie(str(MOVIES / name)))])


# --- Fondo de escritorio (modo escritorio KDE) ---------------------------------

WALL_DIR = HOME / "Pictures/DeckHub/fondos"
SYSTEM_WALLS = Path("/usr/share/wallpapers")
PLASMA_CFG = HOME / ".config/plasma-org.kde.plasma.desktop-appletsrc"
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
WALL_SECTION = "][Wallpaper][org.kde.image][General"


def _wall_sections(ini):
    return [name for name, _ in ini.sections if name and name.endswith(WALL_SECTION)]


def wallpapers():
    WALL_DIR.mkdir(parents=True, exist_ok=True)
    ini = Ini(PLASMA_CFG, sep="=")
    secs = _wall_sections(ini)
    current = ini.get(secs[0], "Image") if secs else None
    current = (current or "").removeprefix("file://")

    def items(folder, own):
        return [{"path": str(p), "name": p.stem, "own": own, "current": str(p) == current}
                for p in sorted(folder.glob("*")) if p.is_file() and p.suffix.lower() in IMAGE_EXT]
    return {"dir": str(WALL_DIR), "current": current,
            "items": items(WALL_DIR, True) + items(SYSTEM_WALLS, False)}


def _wall_path(path):
    p = Path(path).resolve()
    if p.suffix.lower() not in IMAGE_EXT or p.parent not in (WALL_DIR, SYSTEM_WALLS) or not p.is_file():
        raise ValueError("Elige una imagen de tus fondos o de los del sistema.")
    return p


def _plasma_running():
    return subprocess.run(["pgrep", "-x", "plasmashell"], capture_output=True).returncode == 0


def set_wallpaper(path):
    p = _wall_path(path)
    if _plasma_running():
        r = subprocess.run(["plasma-apply-wallpaperimage", str(p)], capture_output=True, text=True, timeout=20)
        if r.returncode != 0:
            raise RuntimeError(r.stderr.strip() or "plasma-apply-wallpaperimage falló")
        return {"applied": "now"}
    # En modo juego KDE no está abierto: se deja configurado para el próximo inicio.
    ini = Ini(PLASMA_CFG, sep="=")
    secs = _wall_sections(ini)
    if not secs:
        raise RuntimeError("No encontré la configuración del escritorio de KDE.")
    for sec in secs:
        ini.set(sec, "Image", f"file://{p}")
    ini.save()
    return {"applied": "next_desktop"}


def check_wallpaper(path):
    p = fileops.safe(path)
    if p.parent != WALL_DIR or p.suffix.lower() not in IMAGE_EXT:
        fileops.trash([str(p)])
        raise ValueError("Formato no válido: usa JPG, PNG o WEBP.")
    return p


def preview_path(path):
    """Archivo que se puede mostrar en el panel (fondos y videos de arranque)."""
    p = Path(path).resolve()
    if p.is_file() and p.parent in (WALL_DIR, SYSTEM_WALLS, MOVIES):
        return p
    raise ValueError("vista previa no permitida")


# --- Temas (CSS Loader) -------------------------------------------------------

THEMES = HOME / "homebrew/themes"
PLUGINS = HOME / "homebrew/plugins"
DECKTHEMES = "https://api.deckthemes.com"
THEME_TARGETS = ["System-Wide", "Home", "Library", "Keyboard", "Lock Screen", "Background",
                 "Profile", "Store", "Tweak", "Snippet", "Other"]


def css_loader_installed():
    for pj in PLUGINS.glob("*/plugin.json"):
        try:
            if "css" in json.loads(pj.read_text()).get("name", "").lower():
                return True
        except (OSError, ValueError):
            continue
    return False


def _theme_cfg(folder):
    # CSS Loader corre como root o como usuario según la versión: se escriben ambos.
    return [folder / "config_USER.json", folder / "config_ROOT.json"]


def _theme_active(folder):
    for f in _theme_cfg(folder):
        try:
            return bool(json.loads(f.read_text()).get("active"))
        except (OSError, ValueError):
            continue
    return False


def installed_themes():
    out = []
    for tj in sorted(THEMES.glob("*/theme.json")):
        try:
            meta = json.loads(tj.read_text())
        except (OSError, ValueError):
            meta = {}
        out.append({"folder": tj.parent.name, "name": meta.get("name", tj.parent.name),
                    "version": meta.get("version"), "author": meta.get("author"),
                    "target": meta.get("target") or ", ".join(meta.get("targets") or []),
                    "active": _theme_active(tj.parent)})
    return out


async def themes():
    return {"css_loader": css_loader_installed(), "installed": installed_themes(),
            "targets": THEME_TARGETS}


async def browse_themes(search="", target="", page=1):
    params = {"page": max(1, int(page)), "perPage": 24, "order": "Most Downloaded",
              "filters": f"CSS.{target}" if target in THEME_TARGETS else "CSS"}
    if search:
        params["search"] = search
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as s:
        try:
            async with s.get(f"{DECKTHEMES}/themes", params=params) as r:
                r.raise_for_status()
                data = await r.json()
        except Exception as e:
            raise RuntimeError(f"DeckThemes no responde: {artwork.describe(e)}")
    have = {t["name"] for t in installed_themes()}
    return {"total": data.get("total", 0), "items": [{
        "id": t["id"], "name": t["displayName"] or t["name"], "folder_name": t["name"],
        "version": t.get("version"), "target": t.get("target"), "author": (t.get("author") or {}).get("username"),
        "stars": t.get("starCount"), "downloads": (t.get("download") or {}).get("downloadCount"),
        "image": f"{DECKTHEMES}/blobs/{t['images'][0]['id']}" if t.get("images") else None,
        "download": (t.get("download") or {}).get("id"), "installed": t["name"] in have,
    } for t in data.get("items", [])]}


def _extract_theme(blob):
    """Descomprime un zip de DeckThemes y devuelve la carpeta que contiene theme.json."""
    tmp = Path(tempfile.mkdtemp(prefix="deckhub-theme-"))
    zpath = tmp / "theme.zip"
    zpath.write_bytes(blob)
    out = tmp / "x"
    with zipfile.ZipFile(zpath) as z:
        for m in z.namelist():
            target = (out / m).resolve()
            if out.resolve() not in target.parents and target != out.resolve():
                raise ValueError("zip de tema no válido")
        z.extractall(out)
    found = sorted(out.rglob("theme.json"), key=lambda p: len(p.parts))
    if not found:
        raise ValueError("el zip no contiene un tema (falta theme.json)")
    return tmp, found[0].parent


async def install_theme(theme_id):
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as s:
        try:
            async with s.get(f"{DECKTHEMES}/themes/{quote(theme_id)}") as r:
                r.raise_for_status()
                meta = await r.json()
            async with s.get(f"{DECKTHEMES}/blobs/{meta['download']['id']}") as r:
                r.raise_for_status()
                blob = await r.read()
        except Exception as e:
            raise RuntimeError(f"No pude descargar el tema: {artwork.describe(e)}")
    tmp, src = await asyncio.to_thread(_extract_theme, blob)
    try:
        THEMES.mkdir(parents=True, exist_ok=True)
        dst = THEMES / fileops._check_name(src.name)
        if dst.exists():
            fileops.trash([str(dst)])  # versión anterior a la papelera
        shutil.move(str(src), str(dst))
        set_theme_active(dst.name, True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return dst.name


def _theme_folder(folder):
    d = (THEMES / fileops._check_name(folder)).resolve()
    if d.parent != THEMES.resolve() or not (d / "theme.json").exists():
        raise ValueError(f"tema no encontrado: {folder}")
    return d


def set_theme_active(folder, active):
    d = _theme_folder(folder)
    for f in _theme_cfg(d):
        try:
            cfg = json.loads(f.read_text())
        except (OSError, ValueError):
            cfg = {}
        cfg["active"] = bool(active)
        f.write_text(json.dumps(cfg))


def remove_theme(folder):
    fileops.trash([str(_theme_folder(folder))])


async def collect():
    return {"movies": movies(), "wallpapers": wallpapers(), "themes": await themes(),
            "art_queue": len(_load_queue()), "time": time.time()}
