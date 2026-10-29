"""Rutas protegidas por token: unidades, archivos, espacio, paquetes, juegos y tareas."""
from pathlib import Path
from urllib.parse import quote

from aiohttp import web

from . import fileops, jobs
from . import config
from .modules import artwork, cheats, emulators, packages, roms, saves, shortcuts, storage


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


async def art_pending(request):
    return _ok(shortcuts.pending_art())


async def art_ack(request):
    b = await _body(request)
    shortcuts.ack_art(b["key"], b.get("error"))
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
                "backup_keep": cfg["backup_keep"], "artwork_net": artwork.net_status()})


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
    for k in ("auto_artwork", "backup_daily"):
        if k in b:
            cfg[k] = bool(b[k])
    if "backup_keep" in b:
        cfg["backup_keep"] = max(1, min(100, int(b["backup_keep"])))
    config.save(cfg)
    return _ok()


# --- Partidas guardadas -------------------------------------------------------

async def saves_list(request):
    return _ok(await saves.collect())


async def saves_backup(request):
    b = await _body(request)
    return _ok(saves.backup(b["emulator"], b.get("only")))


async def saves_restore(request):
    b = await _body(request)
    return _ok(saves.restore(b["name"], b["emulator"]))


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
    r.add_get("/api/settings", settings_get)
    r.add_post("/api/settings", settings_set)
    r.add_get("/api/saves", saves_list)
    r.add_post("/api/saves/backup", saves_backup)
    r.add_post("/api/saves/restore", saves_restore)
    r.add_post("/api/saves/migrate", saves_migrate)
    r.add_get("/api/cheats", cheats_list)
    r.add_post("/api/cheats/ps2/save", cheats_ps2_save)
    r.add_post("/api/cheats/ps2/toggle", cheats_ps2_toggle)
    r.add_post("/api/cheats/ps2/delete", cheats_ps2_delete)
    r.add_post("/api/cheats/eden/save", cheats_eden_save)
    r.add_post("/api/cheats/eden/toggle", cheats_eden_toggle)
    r.add_post("/api/cheats/eden/delete", cheats_eden_delete)
    r.add_get("/api/jobs", jobs_list)
