"""Partidas guardadas de PCSX2, Eden y yuzu: listar, respaldar, restaurar y migrar.

Los respaldos son .zip en ~/DeckHub/backups/<emulador>/ con rutas relativas a la
carpeta de datos del emulador, para poder restaurarlos en su sitio.
"""
import asyncio
import logging
import re
import shutil
import time
import zipfile
from datetime import datetime
from pathlib import Path

from .. import config, fileops, jobs
from . import emulators, ps2ids, roms

log = logging.getLogger("deckhub.saves")
HOME = Path.home()
VAR = HOME / ".var/app"
BACKUPS = HOME / "DeckHub/backups"

# Para cada emulador: carpeta base y subcarpetas que contienen partidas.
EMUS = {
    "pcsx2": {"name": "PCSX2", "app": "net.pcsx2.PCSX2",
              "base": VAR / "net.pcsx2.PCSX2/config/PCSX2", "dirs": ["memcards", "sstates"]},
    "eden": {"name": "Eden", "app": "dev.eden_emu.eden",
             "base": VAR / "dev.eden_emu.eden/data/eden",
             "dirs": ["nand/user/save", "nand/system/save/8000000000000010"]},
    "yuzu": {"name": "yuzu", "app": "org.yuzu_emu.yuzu",
             "base": VAR / "org.yuzu_emu.yuzu/data/yuzu",
             "dirs": ["nand/user/save", "nand/system/save/8000000000000010"]},
}


def _size(p):
    if p.is_file():
        return p.stat().st_size
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def _mtime(p):
    if p.is_file():
        return p.stat().st_mtime
    return max([f.stat().st_mtime for f in p.rglob("*") if f.is_file()] or [p.stat().st_mtime])


def _switch_saves(emu, titles):
    root = EMUS[emu]["base"] / "nand/user/save/0000000000000000"
    out = []
    if not root.exists():
        return out
    for profile in root.iterdir():
        if not profile.is_dir():
            continue
        for title in profile.iterdir():
            if title.is_dir():
                tid = title.name.upper()
                out.append({"id": f"{profile.name}/{title.name}", "title_id": tid,
                            "title": titles.get(tid, tid), "profile": profile.name,
                            "size": _size(title), "mtime": int(_mtime(title))})
    return sorted(out, key=lambda s: -s["mtime"])


def _pcsx2_saves(serials):
    base = EMUS["pcsx2"]["base"]
    out = []
    for f in sorted((base / "memcards").glob("*.ps2")):
        out.append({"id": f"memcards/{f.name}", "kind": "memcard", "title": f"Tarjeta de memoria {f.stem}",
                    "size": f.stat().st_size, "mtime": int(f.stat().st_mtime)})
    for f in sorted((base / "sstates").glob("*.p2s")):
        serial = f.name.split(" ")[0]
        out.append({"id": f"sstates/{f.name}", "kind": "savestate", "serial": serial,
                    "title": serials.get(serial, serial), "file": f.name,
                    "size": f.stat().st_size, "mtime": int(f.stat().st_mtime)})
    return out


SWITCH_SAVES = "nand/user/save/0000000000000000"
SWITCH_ID = re.compile(r"[0-9A-Fa-f]{32}/[0-9A-Fa-f]{16}")
PCSX2_ID = re.compile(r"(memcards/[^/]+\.ps2|sstates/[^/]+\.p2s)")


def _save_rel(emu, save_id):
    """Ruta relativa a la carpeta del emulador de una partida, validando su id."""
    if emu not in EMUS:
        raise ValueError(f"emulador desconocido: {emu}")
    if emu == "pcsx2" and PCSX2_ID.fullmatch(save_id or ""):
        return save_id
    if emu != "pcsx2" and SWITCH_ID.fullmatch(save_id or ""):
        return f"{SWITCH_SAVES}/{save_id}"
    raise ValueError(f"partida no válida: {save_id}")


def _ids_in(emu, names):
    """Ids de partida presentes en una lista de rutas de un zip."""
    out = set()
    for n in names:
        parts = n.split("/")
        if emu == "pcsx2" and len(parts) == 2 and parts[0] in ("memcards", "sstates"):
            out.add(n)
        elif emu != "pcsx2" and n.startswith(SWITCH_SAVES + "/") and len(parts) >= 7:
            out.add(f"{parts[4]}/{parts[5]}")
    return out


_zip_ids = {}


def _contents(emu, z):
    """Partidas que contiene un respaldo (cacheado por fecha de modificación)."""
    key, mtime = str(z), z.stat().st_mtime
    hit = _zip_ids.get(key)
    if not hit or hit[0] != mtime:
        try:
            with zipfile.ZipFile(z) as f:
                hit = (mtime, _ids_in(emu, f.namelist()))
        except zipfile.BadZipFile:
            hit = (mtime, set())
        _zip_ids[key] = hit
    return hit[1]


def backups(emu=None):
    out = []
    for e in ([emu] if emu else EMUS):
        folder = BACKUPS / e
        for z in sorted(folder.glob("*.zip"), reverse=True) if folder.exists() else []:
            out.append({"emulator": e, "name": z.name, "path": str(z), "auto": "-auto" in z.name,
                        "size": z.stat().st_size, "mtime": int(z.stat().st_mtime),
                        "saves": len(_contents(e, z))})
    return out


async def collect():
    games = (await roms.collect())["games"]
    titles = {g["base_id"]: g["title"] for g in games if g.get("base_id")}
    titles |= {g["title_id"]: g["title"] for g in games if g.get("title_id") and g.get("kind") == "base"}
    serials = {i["serial"]: i["title"] for i in (await ps2ids.collect()).values() if i.get("serial")}
    out = {}
    for key, e in EMUS.items():
        if not e["base"].exists():
            continue
        saves = _pcsx2_saves(serials) if key == "pcsx2" else _switch_saves(key, titles)
        zips = sorted((BACKUPS / key).glob("*.zip"), reverse=True) if (BACKUPS / key).exists() else []
        for sv in saves:
            sv["backups"] = [z.name for z in zips if sv["id"] in _contents(key, z)]
        out[key] = {"name": e["name"], "saves": saves, "total": sum(s["size"] for s in saves),
                    "running": emulators._running(e["app"])}
    cfg = config.load()
    return {"emulators": out, "backups": backups(),
            "settings": {"daily": cfg["backup_daily"], "keep": cfg["backup_keep"]},
            "can_migrate": bool(out.get("yuzu", {}).get("saves")) and "eden" in out}


# --- respaldos ------------------------------------------------------------------

def _zip(job, emu, only=None, tag="manual"):
    e = EMUS[emu]
    base = e["base"]
    if only:  # una partida concreta (id de collect())
        targets = [base / _save_rel(emu, only)]
    else:
        targets = [base / d for d in e["dirs"] if (base / d).exists()]
    files = [f for t in targets for f in ([t] if t.is_file() else t.rglob("*")) if f.is_file()]
    if not files:
        raise RuntimeError("No hay partidas que respaldar.")
    job["total"] = sum(f.stat().st_size for f in files)
    folder = BACKUPS / emu
    folder.mkdir(parents=True, exist_ok=True)
    suffix = "-" + re.sub(r"[^\w.-]", "_", only.split("/")[-1])[:40] if only else ""
    dest = folder / f"{datetime.now():%Y%m%d-%H%M%S}-{tag}{suffix}.zip"
    tmp = dest.with_suffix(".part")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for f in files:
            z.write(f, f.relative_to(base))
            job["done"] += f.stat().st_size
    tmp.rename(dest)
    _prune(emu)
    return dest


def _prune(emu):
    keep = int(config.load().get("backup_keep", 10))
    auto = sorted((BACKUPS / emu).glob("*-auto*.zip"), reverse=True)
    for old in auto[keep:]:
        old.unlink()  # solo se rotan los automáticos; los manuales se quedan


def backup(emu, only=None):
    if emu not in EMUS:
        raise ValueError(f"emulador desconocido: {emu}")
    if only:
        _save_rel(emu, only)
    label = f"Respaldar partidas de {EMUS[emu]['name']}" + (f" ({only.split('/')[-1]})" if only else "")
    return jobs.start("backup", label, _zip, emu, only)


def _restore(job, emu, zpath, only=None):
    e = EMUS[emu]
    if emulators._running(e["app"]):
        raise RuntimeError(f"Cierra {e['name']} antes de restaurar.")
    try:
        _zip({"done": 0, "total": 0}, emu, only=only, tag="antes-de-restaurar")  # por si acaso
    except RuntimeError:
        pass  # no había nada que respaldar (p. ej. la partida se había borrado)
    base = e["base"].resolve()
    prefix = _save_rel(emu, only) if only else None
    with zipfile.ZipFile(zpath) as z:
        members = [m for m in z.infolist() if not prefix or m.filename == prefix or m.filename.startswith(prefix + "/")]
        if not members:
            raise RuntimeError("Ese respaldo no contiene la partida.")
        job["total"] = sum(m.file_size for m in members)
        for m in members:
            dest = (base / m.filename).resolve()
            if base not in dest.parents:
                raise RuntimeError(f"ruta no válida en el respaldo: {m.filename}")
            z.extract(m, base)
            job["done"] += m.file_size


def _backup_path(emu, name):
    if emu not in EMUS:
        raise ValueError(f"emulador desconocido: {emu}")
    zpath = BACKUPS / emu / Path(name).name
    if not zpath.is_file():
        raise ValueError(f"no existe el respaldo {name}")
    return zpath


def restore(name, emu, only=None):
    zpath = _backup_path(emu, name)
    if only:
        _save_rel(emu, only)
    label = f"Restaurar {zpath.name} en {EMUS[emu]['name']}" + (f" ({only.split('/')[-1]})" if only else "")
    return jobs.start("restore", label, _restore, emu, zpath, only)


def delete_save(emu, save_id):
    """Manda una partida a la papelera, con un respaldo previo por si acaso."""
    e = EMUS.get(emu) or {}
    if emu in EMUS and emulators._running(e["app"]):
        raise RuntimeError(f"Cierra {e['name']} antes de eliminar partidas.")
    path = EMUS[emu]["base"] / _save_rel(emu, save_id)
    if not path.exists():
        raise ValueError(f"partida no válida: {save_id}")
    _zip({"done": 0, "total": 0}, emu, only=save_id, tag="antes-de-eliminar")
    fileops.trash([str(path)])


def delete_backup(emu, name):
    fileops.trash([str(_backup_path(emu, name))])


def _migrate(job):
    """Copia partidas y perfil de yuzu a Eden (antes respalda lo que tenga Eden)."""
    src, dst = EMUS["yuzu"]["base"], EMUS["eden"]["base"]
    if emulators._running(EMUS["eden"]["app"]):
        raise RuntimeError("Cierra Eden antes de migrar.")
    if any((dst / d).exists() and any((dst / d).rglob("*")) for d in EMUS["eden"]["dirs"]):
        _zip({"done": 0, "total": 0}, "eden", tag="antes-de-migrar")
    dirs = [d for d in EMUS["yuzu"]["dirs"] if (src / d).exists()]
    job["total"] = sum(_size(src / d) for d in dirs)
    for d in dirs:
        shutil.copytree(src / d, dst / d, dirs_exist_ok=True)
        job["done"] += _size(src / d)


def migrate_yuzu():
    return jobs.start("migrate", "Migrar partidas de yuzu a Eden", _migrate)


def set_settings(daily=None, keep=None):
    cfg = config.load()
    if daily is not None:
        cfg["backup_daily"] = bool(daily)
    if keep is not None:
        cfg["backup_keep"] = max(1, min(100, int(keep)))
    config.save(cfg)


async def daily_loop():
    """Respaldo automático cada 24 h (si el emulador no está abierto)."""
    while True:
        await asyncio.sleep(600)
        try:
            if not config.load().get("backup_daily"):
                continue
            for emu in ("pcsx2", "eden"):
                e = EMUS[emu]
                if not e["base"].exists() or emulators._running(e["app"]):
                    continue
                last = max([b["mtime"] for b in backups(emu) if "-auto" in b["name"]] or [0])
                if time.time() - last > 86400:
                    await asyncio.to_thread(_zip, {"done": 0, "total": 0}, emu, None, "auto")
                    log.info("respaldo automático de %s hecho", emu)
        except RuntimeError:
            pass  # sin partidas todavía
        except Exception:
            log.exception("respaldo automático")
