"""Rutas protegidas por token: unidades, archivos, espacio, paquetes, juegos y tareas."""
import asyncio
import os
import re
from pathlib import Path
from urllib.parse import quote

from aiohttp import web

from . import fileops, jobs
from . import config
from .modules import artwork, cheats, custom, emulators, library, packages, playtime, store, roms, saves, shortcuts, storage


def _ok(data=None, **extra):
    return web.json_response({"ok": True, **({"data": data} if data is not None else {}), **extra})


@web.middleware
async def errors(request, handler):
    """Convierte errores de validación y del sistema en respuestas JSON legibles."""
    try:
        return await handler(request)
    except web.HTTPException:
        raise
    except (fileops.PathError, ValueError) as e:
        return web.json_response({"error": str(e)}, status=400)
    except FileNotFoundError as e:
        return web.json_response({"error": f"no existe: {e.filename}"}, status=404)
    except FileExistsError as e:
        return web.json_response({"error": f"ya existe: {e.filename}"}, status=409)
    except (OSError, RuntimeError) as e:
        return web.json_response({"error": str(e)}, status=500)


async def _body(request):
    try:
        return await request.json()
    except ValueError:
        raise ValueError("cuerpo JSON no válido")


# --- Unidades ---------------------------------------------------------------

async def drive_mount(request):
    return _ok(await storage.mount((await _body(request))["device"]))


async def drive_unmount(request):
    return _ok(await storage.unmount((await _body(request))["device"]))


async def drive_automount(request):
    b = await _body(request)
    storage.set_automount(b["uuid"], bool(b["enabled"]))
    return _ok()


# --- Archivos ---------------------------------------------------------------

async def files_roots(request):
    return _ok(fileops.roots())


async def files_list(request):
    q = request.query
    return _ok(fileops.listdir(q.get("path", str(fileops.HOME)), q.get("hidden") == "1"))


async def files_mkdir(request):
    b = await _body(request)
    return _ok(fileops.mkdir(b["path"], b["name"]))


async def files_rename(request):
    b = await _body(request)
    return _ok(fileops.rename(b["path"], b["name"]))


async def files_trash(request):
    return _ok(fileops.trash((await _body(request))["paths"]))


async def files_copy(request):
    b = await _body(request)
    return _ok(fileops.transfer(b["paths"], b["dest"], move=False))


async def files_move(request):
    b = await _body(request)
    return _ok(fileops.transfer(b["paths"], b["dest"], move=True))


async def files_upload(request):
    dest = request.query.get("dir")
    reader = await request.multipart()
    saved = []
    while (field := await reader.next()) is not None:
        if field.filename:
            saved.append(await fileops.save_upload(field, dest))
    return _ok(saved)


async def files_download(request):
    p = fileops.safe(request.query.get("path"))
    if not p.is_file():
        raise fileops.PathError(f"no es un archivo: {p}")
    return web.FileResponse(p, headers={
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(p.name)}"})


async def space(request):
    return _ok(await fileops.space(request.query.get("path", str(fileops.HOME))))


# --- Paquetes, juegos y tareas ----------------------------------------------

async def packages_list(request):
    return _ok(await packages.collect())


async def packages_search(request):
    return _ok(await packages.search(request.query.get("q", "")))


async def packages_install(request):
    return _ok(packages.install((await _body(request))["id"]))


async def packages_uninstall(request):
    return _ok(packages.uninstall((await _body(request))["id"]))


async def roms_list(request):
    if request.query.get("refresh") == "1":
        roms.collect.invalidate()
    return _ok(await roms.collect())


async def emulators_list(request):
    return _ok(await emulators.collect())


FLATPAK_ICONS = [Path("/var/lib/flatpak/exports/share/icons/hicolor"),
                 Path.home() / ".local/share/flatpak/exports/share/icons/hicolor"]


async def emulators_icon(request):
    """Ícono de un emulador: el que trae su Flatpak instalado o, si no, el de Flathub."""
    app_id = request.query.get("id", "")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,120}", app_id):
        raise ValueError(f"id de flatpak no válido: {app_id}")
    for size in ("scalable", "512x512", "256x256", "128x128", "64x64"):
        for root in FLATPAK_ICONS:
            for ext in ("svg", "png"):
                f = root / size / "apps" / f"{app_id}.{ext}"
                if f.is_file():
                    return web.FileResponse(f, headers={"Cache-Control": "max-age=86400"})
    raise web.HTTPFound(f"https://dl.flathub.org/repo/appstream/x86_64/icons/128x128/{app_id}.png")


async def emulators_install(request):
    return _ok(await emulators.install((await _body(request))["id"]))


async def emulators_configure(request):
    return _ok(await emulators.configure((await _body(request))["id"]))


async def shortcuts_list(request):
    return _ok(await shortcuts.collect())


async def shortcuts_add(request):
    return _ok(await shortcuts.request_add((await _body(request))["paths"]))


async def shortcuts_remove(request):
    return _ok(shortcuts.request_remove((await _body(request))["paths"]))


async def shortcuts_pending(request):
    return _ok(shortcuts.pending())


async def shortcuts_ack(request):
    b = await _body(request)
    shortcuts.ack(b["key"], b.get("appid"), bool(b.get("removed")), b.get("error"))
    return _ok()


async def eden_firmware(request):
    """Firmware desde un .zip subido (multipart) o una ruta del Deck ({"path": ...})."""
    if request.content_type.startswith("multipart/"):
        reader = await request.multipart()
        field = await reader.next()
        if field is None or not field.filename:
            raise ValueError("No llegó ningún archivo.")
        tmp = Path.home() / ".cache/deckhub/firmware-upload.zip"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp, "wb") as f:
            while chunk := await field.read_chunk(8 * 1024 * 1024):
                f.write(chunk)
        return _ok(emulators.install_firmware(str(tmp), cleanup=True))
    path = fileops.safe((await _body(request)).get("path"))
    if not path.exists():
        raise ValueError(f"No existe: {path}")
    return _ok(emulators.install_firmware(str(path)))


async def eden_keys(request):
    reader = await request.multipart()
    files = {}
    while (field := await reader.next()) is not None:
        name = Path(field.filename or "").name.lower()
        if name in ("prod.keys", "title.keys"):
            files[name] = await field.read(decode=False)
    emulators.install_keys(files)
    return _ok(sorted(files))


async def playtime_get(request):
    return _ok(playtime.load())


async def playtime_report(request):
    b = await _body(request)
    return _ok(playtime.store(b.get("apps"), b.get("compat_tools")))


async def library_list(request):
    return _ok(await library.collect())


async def library_detail(request):
    return _ok(await library.detail(request.query.get("key", "")))


async def library_action(request):
    b = await _body(request)
    library.steam_action(b["action"], b["appid"], b.get("value"))
    return _ok()


async def downloads_get(request):
    return _ok(library.downloads())


async def downloads_report(request):
    library.store_downloads((await _body(request)).get("items"))
    return _ok()


async def downloads_all(request):
    library.download_all()
    return _ok()


async def store_get(request):
    return _ok(store.collect())


async def store_refresh(request):
    return _ok(await store.refresh())


async def store_import(request):
    return _ok(await store.import_wishlist())


async def store_userdata(request):
    return _ok(store.set_steam_userdata(await _body(request)))


async def store_search(request):
    return _ok(await store.search(request.query.get("q", "")))


async def store_track(request):
    b = await _body(request)
    await store.track(b["appid"], b.get("target"), b.get("notify_low", True))
    return _ok()


async def store_untrack(request):
    store.untrack((await _body(request))["appid"])
    return _ok()


async def store_notifications(request):
    return _ok(store.pending_notifications())


async def store_notifications_ack(request):
    store.ack_notification((await _body(request))["id"])
    return _ok()


async def art_image(request):
    """Imagen actual de un juego (para <img>); 404 si Steam no tiene ninguna."""
    cur = custom.art_current(request.query.get("appid", "0")).get(request.query.get("kind", "grid"))
    if not cur:
        raise web.HTTPNotFound()
    return web.FileResponse(cur["path"], headers={"Cache-Control": "max-age=60"})


async def art_pending(request):
    return _ok(shortcuts.pending_art() + custom.pending_art())


async def art_ack(request):
    b = await _body(request)
    if b["key"].startswith("custom:"):
        custom.ack_art(b["key"].split(":", 1)[1], b.get("error"))
    else:
        shortcuts.ack_art(b["key"], b.get("error"))
    return _ok()


# --- Personalización -------------------------------------------------------------

async def custom_get(request):
    return _ok(await custom.collect())


async def custom_art_options(request):
    q = request.query
    return _ok(await custom.art_options(q.get("appid", "0"), q.get("kind", "grid"),
                                        q.get("title", ""), q.get("shortcut") == "1"))


async def custom_art_current(request):
    """?appid=N para un juego, o ?appids=1,2,3 para varios (mapa por AppID)."""
    q = request.query
    if "appids" in q:
        ids = [i for i in q["appids"].split(",") if i.strip().isdigit()][:200]
        return _ok({i: custom.art_current(i) for i in ids})
    return _ok(custom.art_current(q.get("appid", "0")))


async def custom_art_apply(request):
    b = await _body(request)
    await custom.art_apply(b["appid"], b["kind"], b["url"])
    return _ok()


async def custom_art_reset(request):
    b = await _body(request)
    custom.art_reset(b["appid"], b.get("kinds"))
    return _ok()


async def _upload_into(request, folder):
    reader = await request.multipart()
    field = await reader.next()
    if field is None or not field.filename:
        raise ValueError("No llegó ningún archivo.")
    folder.mkdir(parents=True, exist_ok=True)
    return (await fileops.save_upload(field, str(folder)))["path"]


async def custom_movie_upload(request):
    path = await _upload_into(request, custom.MOVIES)
    return _ok(custom.check_movie(path).name)


async def custom_movie_default(request):
    name = (await _body(request)).get("name")
    custom.movie_set_default(name) if name else custom.movie_clear_default()
    return _ok()


async def custom_movie_delete(request):
    custom.movie_delete((await _body(request))["name"])
    return _ok()


async def custom_wallpaper_upload(request):
    path = await _upload_into(request, custom.WALL_DIR)
    return _ok(str(custom.check_wallpaper(path)))


async def custom_wallpaper_set(request):
    return _ok(custom.set_wallpaper((await _body(request))["path"]))


async def custom_movies_browse(request):
    q = request.query
    return _ok(await custom.browse_movies(q.get("search", ""), q.get("sort", "trending"), q.get("page", "1")))


async def custom_movies_download(request):
    b = await _body(request)
    return _ok(await custom.download_movie(b["video"], b["slug"]))


async def custom_wallpaper_browse(request):
    q = request.query
    return _ok(await custom.browse_wallpapers(q.get("q", ""), q.get("page", "1")))


async def custom_wallpaper_download(request):
    b = await _body(request)
    return _ok(await custom.download_wallpaper(b["url"], bool(b.get("apply"))))


async def custom_preview(request):
    return web.FileResponse(custom.preview_path(request.query.get("path", "")))


async def custom_themes_browse(request):
    q = request.query
    return _ok(await custom.browse_themes(q.get("search", ""), q.get("target", ""), q.get("page", "1")))


async def custom_themes_install(request):
    return _ok(await custom.install_theme((await _body(request))["id"]))


async def custom_themes_toggle(request):
    b = await _body(request)
    custom.set_theme_active(b["folder"], bool(b["active"]))
    return _ok()


async def decky_install(request):
    return _ok(await custom.request_plugin_install((await _body(request))["name"]))


async def decky_actions_pending(request):
    return _ok(custom.pending_actions())


async def decky_actions_ack(request):
    custom.ack_action((await _body(request))["id"])
    return _ok()


async def custom_themes_remove(request):
    custom.remove_theme((await _body(request))["folder"])
    return _ok()


async def art_refresh(request):
    b = await _body(request)
    artwork.retry_now()
    return _ok(shortcuts.request_art(b.get("paths")))


# --- Ajustes ------------------------------------------------------------------

async def settings_get(request):
    cfg = config.load()
    k = cfg.get("steamgriddb_key", "")
    return _ok({"steamgriddb_key_set": bool(k), "steamgriddb_key_hint": f"…{k[-4:]}" if k else "",
                "auto_artwork": cfg["auto_artwork"], "backup_daily": cfg["backup_daily"],
                "backup_keep": cfg["backup_keep"], "artwork_net": artwork.net_status(),
                "lan_access": cfg["lan_access"], "store_country": cfg.get("store_country", ""),
                "itad_key_set": bool(cfg.get("itad_key"))})


async def settings_set(request):
    b = await _body(request)
    cfg = config.load()
    if "steamgriddb_key" in b:
        old = cfg.get("steamgriddb_key", "")
        cfg["steamgriddb_key"] = str(b["steamgriddb_key"]).strip()
        config.save(cfg)
        if cfg["steamgriddb_key"]:
            try:
                await artwork.check_key()
            except Exception as e:
                cfg["steamgriddb_key"] = old
                config.save(cfg)
                if isinstance(e, artwork.ArtError):
                    raise ValueError(str(e))
                raise ValueError(f"No pude validar la clave: {artwork.describe(e)}.")
            artwork.retry_now()
    if "itad_key" in b:
        key = str(b["itad_key"]).strip()
        if key:
            try:
                await store.check_itad_key(key)
            except Exception as e:
                raise ValueError(f"No pude validar la clave de IsThereAnyDeal: {e}")
        cfg["itad_key"] = key
    if "ui_lang" in b:
        from . import i18n
        lang = str(b["ui_lang"])
        if lang != "auto" and lang not in {l["code"] for l in i18n.available()}:
            raise ValueError(f"idioma no disponible: {lang}")
        cfg["ui_lang"] = lang
    if "store_country" in b:
        cc = str(b["store_country"]).strip().upper()
        if cc and (len(cc) != 2 or not cc.isalpha()):
            raise ValueError("País no válido: usa el código de 2 letras (CL, MX, US…).")
        cfg["store_country"] = cc
    for k in ("auto_artwork", "backup_daily"):
        if k in b:
            cfg[k] = bool(b[k])
    if "backup_keep" in b:
        cfg["backup_keep"] = max(1, min(100, int(b["backup_keep"])))
    rebind = "lan_access" in b and bool(b["lan_access"]) != cfg["lan_access"]
    if rebind:
        cfg["lan_access"] = bool(b["lan_access"])
    config.save(cfg)
    if rebind:
        # Cambiar la dirección de escucha exige reiniciar: se sale con error y
        # systemd (Restart=on-failure) vuelve a levantarlo en ~3 s con el nuevo ajuste.
        asyncio.get_running_loop().call_later(0.5, os._exit, 75)
    return _ok(restarting=rebind)


# --- Partidas guardadas -------------------------------------------------------

async def saves_list(request):
    return _ok(await saves.collect())


async def saves_backup(request):
    b = await _body(request)
    return _ok(saves.backup(b["emulator"], b.get("only")))


async def saves_restore(request):
    b = await _body(request)
    return _ok(saves.restore(b["name"], b["emulator"], b.get("only")))


async def saves_delete(request):
    b = await _body(request)
    saves.delete_save(b["emulator"], b["id"])
    return _ok()


async def saves_backup_delete(request):
    b = await _body(request)
    saves.delete_backup(b["emulator"], b["name"])
    return _ok()


async def saves_migrate(request):
    return _ok(saves.migrate_yuzu())


# --- Trucos ---------------------------------------------------------------------

async def cheats_list(request):
    return _ok(await cheats.collect())


async def cheats_ps2_save(request):
    b = await _body(request)
    await cheats.ps2_save(b["path"], b["text"])
    return _ok()


async def cheats_ps2_toggle(request):
    b = await _body(request)
    await cheats.ps2_toggle(b["path"], bool(b["enabled"]))
    return _ok()


async def cheats_ps2_delete(request):
    await cheats.ps2_delete((await _body(request))["path"])
    return _ok()


async def cheats_eden_save(request):
    b = await _body(request)
    cheats.eden_save(b["title_id"], b["name"], b["build_id"], b["text"])
    return _ok()


async def cheats_eden_toggle(request):
    b = await _body(request)
    cheats.eden_toggle(b["title_id"], b["name"], bool(b["enabled"]))
    return _ok()


async def cheats_eden_delete(request):
    b = await _body(request)
    cheats.eden_delete(b["title_id"], b["name"])
    return _ok()


async def jobs_list(request):
    return _ok(jobs.listing())


def setup(app):
    r = app.router
    r.add_post("/api/drives/mount", drive_mount)
    r.add_post("/api/drives/unmount", drive_unmount)
    r.add_post("/api/drives/automount", drive_automount)
    r.add_get("/api/files/roots", files_roots)
    r.add_get("/api/files/list", files_list)
    r.add_get("/api/files/download", files_download)
    r.add_post("/api/files/mkdir", files_mkdir)
    r.add_post("/api/files/rename", files_rename)
    r.add_post("/api/files/trash", files_trash)
    r.add_post("/api/files/copy", files_copy)
    r.add_post("/api/files/move", files_move)
    r.add_post("/api/files/upload", files_upload)
    r.add_get("/api/space", space)
    r.add_get("/api/packages", packages_list)
    r.add_get("/api/packages/search", packages_search)
    r.add_post("/api/packages/install", packages_install)
    r.add_post("/api/packages/uninstall", packages_uninstall)
    r.add_get("/api/roms", roms_list)
    r.add_get("/api/emulators", emulators_list)
    r.add_get("/api/emulators/icon", emulators_icon)
    r.add_post("/api/emulators/install", emulators_install)
    r.add_post("/api/emulators/configure", emulators_configure)
    r.add_post("/api/emulators/eden/firmware", eden_firmware)
    r.add_post("/api/emulators/eden/keys", eden_keys)
    r.add_get("/api/shortcuts", shortcuts_list)
    r.add_post("/api/shortcuts/add", shortcuts_add)
    r.add_post("/api/shortcuts/remove", shortcuts_remove)
    r.add_get("/api/shortcuts/pending", shortcuts_pending)
    r.add_post("/api/shortcuts/ack", shortcuts_ack)
    r.add_get("/api/shortcuts/art/pending", art_pending)
    r.add_post("/api/shortcuts/art/ack", art_ack)
    r.add_post("/api/shortcuts/art/refresh", art_refresh)
    r.add_get("/api/steam/playtime", playtime_get)
    r.add_post("/api/steam/playtime", playtime_report)
    r.add_get("/api/steam/downloads", downloads_get)
    r.add_post("/api/steam/downloads", downloads_report)
    r.add_post("/api/steam/downloads/all", downloads_all)
    r.add_get("/api/store", store_get)
    r.add_post("/api/store/refresh", store_refresh)
    r.add_post("/api/store/import", store_import)
    r.add_get("/api/store/search", store_search)
    r.add_post("/api/store/userdata", store_userdata)
    r.add_post("/api/store/track", store_track)
    r.add_post("/api/store/untrack", store_untrack)
    r.add_get("/api/store/notifications", store_notifications)
    r.add_post("/api/store/notifications/ack", store_notifications_ack)
    r.add_get("/api/library", library_list)
    r.add_get("/api/library/detail", library_detail)
    r.add_post("/api/library/action", library_action)
    r.add_get("/api/custom/art/image", art_image)
    r.add_get("/api/custom", custom_get)
    r.add_get("/api/custom/art/options", custom_art_options)
    r.add_get("/api/custom/art/current", custom_art_current)
    r.add_post("/api/custom/art/apply", custom_art_apply)
    r.add_post("/api/custom/art/reset", custom_art_reset)
    r.add_post("/api/custom/movies/upload", custom_movie_upload)
    r.add_post("/api/custom/movies/default", custom_movie_default)
    r.add_post("/api/custom/movies/delete", custom_movie_delete)
    r.add_post("/api/custom/wallpaper/upload", custom_wallpaper_upload)
    r.add_post("/api/custom/wallpaper/set", custom_wallpaper_set)
    r.add_get("/api/custom/preview", custom_preview)
    r.add_get("/api/custom/movies/browse", custom_movies_browse)
    r.add_post("/api/custom/movies/download", custom_movies_download)
    r.add_get("/api/custom/wallpaper/browse", custom_wallpaper_browse)
    r.add_post("/api/custom/wallpaper/download", custom_wallpaper_download)
    r.add_get("/api/custom/themes/browse", custom_themes_browse)
    r.add_post("/api/custom/themes/install", custom_themes_install)
    r.add_post("/api/custom/themes/toggle", custom_themes_toggle)
    r.add_post("/api/custom/themes/remove", custom_themes_remove)
    r.add_post("/api/decky/install", decky_install)
    r.add_get("/api/decky/actions/pending", decky_actions_pending)
    r.add_post("/api/decky/actions/ack", decky_actions_ack)
    r.add_get("/api/settings", settings_get)
    r.add_post("/api/settings", settings_set)
    r.add_get("/api/saves", saves_list)
    r.add_post("/api/saves/backup", saves_backup)
    r.add_post("/api/saves/restore", saves_restore)
    r.add_post("/api/saves/delete", saves_delete)
    r.add_post("/api/saves/backups/delete", saves_backup_delete)
    r.add_post("/api/saves/migrate", saves_migrate)
    r.add_get("/api/cheats", cheats_list)
    r.add_post("/api/cheats/ps2/save", cheats_ps2_save)
    r.add_post("/api/cheats/ps2/toggle", cheats_ps2_toggle)
    r.add_post("/api/cheats/ps2/delete", cheats_ps2_delete)
    r.add_post("/api/cheats/eden/save", cheats_eden_save)
    r.add_post("/api/cheats/eden/toggle", cheats_eden_toggle)
    r.add_post("/api/cheats/eden/delete", cheats_eden_delete)
    r.add_get("/api/jobs", jobs_list)
