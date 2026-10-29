"""Personalización: portadas de cualquier juego, videos de arranque, fondo de
escritorio y temas del modo juego (instalados para CSS Loader).
"""
import asyncio
import json
import re
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


STEAM = HOME / ".local/share/Steam"
LIBCACHE = STEAM / "appcache/librarycache"
# Nombre en config/grid (personalizada) y en librarycache (original de Steam).
ART_FILES = {"grid": ("{id}p", ["library_capsule", "library_600x900"]),
             "wide": ("{id}", ["library_header", "header"]),
             "hero": ("{id}_hero", ["library_hero"]),
             "logo": ("{id}_logo", ["logo"])}


def _grid_dir():
    # Usuario de Steam usado más recientemente.
    users = sorted((STEAM / "userdata").glob("*/config/localconfig.vdf"),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    return users[0].parent / "grid" if users else None


def art_current(appid):
    """Imagen que muestra Steam ahora para cada tipo: personalizada u original."""
    appid = int(appid)
    grid = _grid_dir()
    out = {}
    for kind, (custom_name, originals) in ART_FILES.items():
        found = None
        if grid:
            for ext in ("png", "jpg", "jpeg", "webp"):
                f = grid / f"{custom_name.format(id=appid)}.{ext}"
                if f.exists():
                    found = {"path": str(f), "custom": True}
                    break
        if not found:
            folder = LIBCACHE / str(appid)
            for name in originals:
                hits = list(folder.rglob(f"{name}.*")) if folder.is_dir() else []
                hits += list(LIBCACHE.glob(f"{appid}_{name}.*"))  # formato antiguo
                hits = [h for h in hits if "blur" not in h.name]
                if hits:
                    found = {"path": str(hits[0]), "custom": False}
                    break
        if found:
            found["mtime"] = int(Path(found["path"]).stat().st_mtime)
        out[kind] = found
    return out


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


# Recomendaciones descargables: videos de la comunidad de steamdeckrepo.com.
DECKREPO = "https://steamdeckrepo.com/api/posts"
DECKREPO_SORTS = ["trending", "downloads-desc", "likes-desc", "created_at-desc"]


async def _get_json(url, params, source):
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20),
                                     headers={"User-Agent": "DeckHub"}) as s:
        try:
            async with s.get(url, params=params) as r:
                r.raise_for_status()
                return await r.json()
        except Exception as e:
            raise RuntimeError(f"{source} no responde: {artwork.describe(e)}")


async def _download(url, hosts, dest):
    host = urlparse(url).hostname or ""
    if urlparse(url).scheme != "https" or not any(host == h or host.endswith("." + h) for h in hosts):
        raise ValueError("Origen de descarga no permitido.")
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=180),
                                     headers={"User-Agent": "DeckHub"}) as s:
        try:
            async with s.get(url) as r:
                r.raise_for_status()
                with open(tmp, "wb") as f:
                    async for chunk in r.content.iter_chunked(1 << 20):
                        f.write(chunk)
        except Exception as e:
            tmp.unlink(missing_ok=True)
            raise RuntimeError(f"No pude descargar: {artwork.describe(e)}")
    tmp.replace(dest)
    return dest


def _movie_name(slug):
    return fileops._check_name(re.sub(r"[^\w.-]+", "_", slug)[:115] + ".webm")


async def browse_movies(search="", sort="trending", page=1):
    params = {"page": max(1, int(page)), "sort": sort if sort in DECKREPO_SORTS else "trending"}
    if search:
        params["search"] = search
    data = await _get_json(DECKREPO, params, "steamdeckrepo.com")
    have = {p.name for p in MOVIES.glob("*.webm")} if MOVIES.exists() else set()
    return {"items": [{
        "id": p["id"], "title": p["title"], "author": (p.get("user") or {}).get("steam_name"),
        "thumbnail": p.get("thumbnail"), "preview": p.get("video_preview"), "video": p.get("video"),
        "duration": p.get("video_duration"), "likes": p.get("likes"), "downloads": p.get("downloads"),
        "installed": _movie_name(p["slug"]) in have, "slug": p["slug"],
    } for p in data.get("posts", [])
        # steamdeckrepo también tiene videos de suspensión, que van en otro sitio.
        if p.get("type", "boot_video") == "boot_video" and p.get("video", "").endswith(".webm")]}


async def download_movie(video, slug):
    dest = await _download(video, ("steamdeckrepo.com",), MOVIES / _movie_name(slug))
    return dest.name


# Fondos recomendados: Wallhaven, solo contenido apto (purity=100) y sin fotos de personas.
WALLHAVEN = "https://wallhaven.cc/api/v1/search"


async def browse_wallpapers(query="", page=1):
    params = {"purity": "100", "categories": "110", "atleast": "1280x800", "ratios": "16x10,16x9",
              "sorting": "toplist" if not query else "relevance", "page": max(1, int(page))}
    if query:
        params["q"] = query
    data = await _get_json(WALLHAVEN, params, "Wallhaven")
    have = {p.name for p in WALL_DIR.glob("*")} if WALL_DIR.exists() else set()
    return {"last_page": data.get("meta", {}).get("last_page", 1), "items": [{
        "id": w["id"], "thumb": w["thumbs"]["small"], "full": w["path"], "resolution": w.get("resolution"),
        "installed": Path(w["path"]).name in have,
    } for w in data.get("data", []) if w.get("purity") == "sfw"]}


async def download_wallpaper(url, apply=False):
    dest = await _download(url, ("wallhaven.cc",), WALL_DIR / fileops._check_name(Path(urlparse(url).path).name))
    check_wallpaper(str(dest))
    return {"path": str(dest), **(set_wallpaper(str(dest)) if apply else {})}


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
    """Archivo que se puede mostrar en el panel: fondos, videos de arranque e
    imágenes de la biblioteca de Steam."""
    p = Path(path).resolve()
    grid = _grid_dir()
    if p.is_file() and (p.parent in (WALL_DIR, SYSTEM_WALLS, MOVIES) or (grid and p.parent == grid.resolve())
                        or LIBCACHE.resolve() in p.parents):
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


# Acciones que el plugin ejecuta dentro de Decky:
# - "install": instalar un plugin de la tienda (Decky pide confirmación en pantalla).
# - "css_reset": recargar CSS Loader tras cambiar temas desde el panel.
DECKY_STORE = "https://plugins.deckbrew.xyz/plugins"
DECKY_CDN = "https://cdn.tzatzikiweeb.moe/file/steam-deck-homebrew/versions"
ACTIONS = CONF / "decky-actions.json"


def _load_actions():
    try:
        q = json.loads(ACTIONS.read_text())
    except (OSError, ValueError):
        return []
    # Una petición vieja (Steam cerrado mucho tiempo) no debe aparecer por sorpresa.
    return [a for a in q if time.time() - a.get("requested", 0) < 600]


def _queue_action(action):
    # Una acción nueva sobre el mismo tema/plugin reemplaza a la pendiente.
    q = [a for a in _load_actions() if a["type"] != action["type"] or a.get("name") != action.get("name")]
    q.append({**action, "id": uuid.uuid4().hex[:12], "requested": time.time()})
    CONF.mkdir(parents=True, exist_ok=True)
    ACTIONS.write_text(json.dumps(q))


async def request_plugin_install(name):
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as s:
        try:
            async with s.get(DECKY_STORE, params={"query": name}) as r:
                r.raise_for_status()
                plugins = await r.json()
        except Exception as e:
            raise RuntimeError(f"La tienda de Decky no responde: {artwork.describe(e)}")
    found = next((p for p in plugins if p.get("name") == name and p.get("versions")), None)
    if not found:
        raise ValueError(f"«{name}» no está en la tienda de Decky.")
    ver = found["versions"][0]
    _queue_action({"type": "install", "name": name, "version": ver["name"], "hash": ver["hash"],
                   "artifact": ver.get("artifact") or f"{DECKY_CDN}/{ver['hash']}.zip"})
    return {"name": name, "version": ver["name"]}


def request_css_reset():
    if css_loader_installed():
        _queue_action({"type": "css_reset"})


def pending_actions():
    return _load_actions()


def ack_action(action_id):
    ACTIONS.write_text(json.dumps([a for a in _load_actions() if a["id"] != action_id]))


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
    """Con CSS Loader instalado se le pide a él (instala también las dependencias, como
    los temas de un perfil, y actualiza su lista). Sin él, se descomprime aquí."""
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as s:
        try:
            async with s.get(f"{DECKTHEMES}/themes/{quote(theme_id)}") as r:
                r.raise_for_status()
                meta = await r.json()
            if css_loader_installed():
                _queue_action({"type": "css_install", "name": meta["name"], "theme_id": theme_id,
                               "deps": len(meta.get("dependencies") or [])})
                return {"name": meta["name"], "via": "css_loader", "deps": len(meta.get("dependencies") or [])}
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
        _write_active(dst, True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return {"name": dst.name, "via": "local", "deps": 0}


def _theme_folder(folder):
    d = (THEMES / fileops._check_name(folder)).resolve()
    if d.parent != THEMES.resolve() or not (d / "theme.json").exists():
        raise ValueError(f"tema no encontrado: {folder}")
    return d


def _write_active(d, active):
    for f in _theme_cfg(d):
        try:
            cfg = json.loads(f.read_text())
        except (OSError, ValueError):
            cfg = {}
        cfg["active"] = bool(active)
        f.write_text(json.dumps(cfg))


def set_theme_active(folder, active):
    d = _theme_folder(folder)
    if css_loader_installed():
        # CSS Loader activa también las dependencias (perfiles) y guarda el estado.
        name = json.loads((d / "theme.json").read_text()).get("name", d.name)
        _queue_action({"type": "css_state", "name": name, "active": bool(active)})
    else:
        _write_active(d, active)


def remove_theme(folder):
    fileops.trash([str(_theme_folder(folder))])
    request_css_reset()


async def collect():
    return {"movies": movies(), "wallpapers": wallpapers(), "themes": await themes(),
            "art_queue": len(_load_queue()), "time": time.time()}
