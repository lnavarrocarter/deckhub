"""Explorador de archivos limitado a /home/deck y /run/media/deck.

Nada se borra de forma definitiva: "eliminar" mueve a la papelera estándar
(~/.local/share/Trash o <unidad>/.Trash-<uid>), igual que el gestor de archivos de KDE.
"""
import itertools
import os
import shutil
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from . import jobs
from .modules import roms
from .util import run

HOME = Path.home()
MEDIA = Path("/run/media") / HOME.name
ROOTS = [HOME, MEDIA]
CHUNK = 8 * 1024 * 1024


class PathError(ValueError):
    pass


def safe(path):
    """Resuelve una ruta y verifica que quede dentro de las raíces permitidas."""
    if not path:
        raise PathError("ruta vacía")
    p = Path(path).expanduser().resolve()
    if not any(p == r or r in p.parents for r in ROOTS):
        raise PathError(f"fuera de las carpetas permitidas: {p}")
    return p


def _check_name(name):
    if not name or "/" in name or name in (".", ".."):
        raise PathError(f"nombre no válido: {name!r}")
    return name


def roots():
    out = [{"name": "Inicio", "path": str(HOME)}]
    if MEDIA.exists():
        out += [{"name": m.name, "path": str(m)} for m in sorted(MEDIA.iterdir()) if m.is_mount()]
    return out


def listdir(path, show_hidden=False):
    p = safe(path)
    if not p.is_dir():
        raise PathError(f"no es una carpeta: {p}")
    entries = []
    for e in os.scandir(p):
        if not show_hidden and e.name.startswith("."):
            continue
        try:
            st = e.stat(follow_symlinks=False)
        except OSError:
            continue
        is_dir = e.is_dir(follow_symlinks=False)
        entries.append({
            "name": e.name, "dir": is_dir, "size": None if is_dir else st.st_size,
            "mtime": int(st.st_mtime), "game": None if is_dir else roms.classify(e.name, str(p)),
        })
    entries.sort(key=lambda x: (not x["dir"], x["name"].lower()))
    parent = str(p.parent) if p not in ROOTS else None
    return {"path": str(p), "parent": parent, "entries": entries}


def mkdir(path, name):
    target = safe(path) / _check_name(name)
    target.mkdir()
    return str(target)


def rename(path, name):
    src = safe(path)
    dst = src.with_name(_check_name(name))
    if dst.exists():
        raise PathError(f"ya existe: {dst.name}")
    src.rename(dst)
    return str(dst)


def _unique(dst):
    if not dst.exists():
        return dst
    stem, suffix = dst.stem, dst.suffix
    for i in itertools.count(2):
        cand = dst.with_name(f"{stem} ({i}){suffix}")
        if not cand.exists():
            return cand


def _trash_dir(p):
    """Papelera freedesktop: la de la unidad si está en un medio extraíble."""
    if MEDIA in p.parents:
        mount = MEDIA / p.relative_to(MEDIA).parts[0]
        return mount / f".Trash-{os.getuid()}"
    return HOME / ".local/share/Trash"


def trash(paths):
    moved = []
    for path in paths:
        p = safe(path)
        if p in ROOTS or (MEDIA in p.parents and p.parent == MEDIA):
            raise PathError(f"no se puede eliminar una raíz: {p}")
        tdir = _trash_dir(p)
        (tdir / "files").mkdir(parents=True, exist_ok=True)
        (tdir / "info").mkdir(parents=True, exist_ok=True)
        dst = _unique(tdir / "files" / p.name)
        (tdir / "info" / f"{dst.name}.trashinfo").write_text(
            "[Trash Info]\n"
            f"Path={quote(str(p))}\n"
            f"DeletionDate={datetime.now().strftime('%Y-%m-%dT%H:%M:%S')}\n"
        )
        p.rename(dst)
        moved.append(str(p))
    return moved


def _size(p):
    if p.is_file() or p.is_symlink():
        return p.lstat().st_size
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file() and not f.is_symlink())


def _copy_file(src, dst, job):
    tmp = dst.with_name(dst.name + ".part")
    with open(src, "rb") as fi, open(tmp, "wb") as fo:
        while chunk := fi.read(CHUNK):
            fo.write(chunk)
            job["done"] += len(chunk)
    shutil.copystat(src, tmp, follow_symlinks=False)
    tmp.rename(dst)


def _copy_any(src, dst, job):
    if src.is_dir() and not src.is_symlink():
        dst.mkdir()
        for child in src.iterdir():
            _copy_any(child, dst / child.name, job)
    elif src.is_symlink():
        os.symlink(os.readlink(src), dst)
    else:
        _copy_file(src, dst, job)


def _transfer(job, srcs, dest, move):
    job["total"] = sum(_size(s) for s in srcs)
    for src in srcs:
        dst = _unique(dest / src.name)
        if move:
            try:
                src.rename(dst)  # mismo sistema de archivos: instantáneo
                job["done"] += _size(dst)
                continue
            except OSError:
                pass
        _copy_any(src, dst, job)
        if move:
            shutil.rmtree(src) if src.is_dir() and not src.is_symlink() else src.unlink()


def transfer(paths, dest, move):
    srcs = [safe(p) for p in paths]
    d = safe(dest)
    if not d.is_dir():
        raise PathError(f"el destino no es una carpeta: {d}")
    for s in srcs:
        if s == d or s in d.parents:
            raise PathError(f"no se puede copiar una carpeta dentro de sí misma: {s.name}")
    verb = "Mover" if move else "Copiar"
    label = f"{verb} {srcs[0].name}" + (f" y {len(srcs) - 1} más" if len(srcs) > 1 else "")
    return jobs.start("move" if move else "copy", f"{label} → {d}", _transfer, srcs, d, move)


async def save_upload(field, dest):
    """Guarda un archivo de un formulario multipart en `dest` sin cargarlo en memoria."""
    d = safe(dest)
    name = _check_name(Path(field.filename or "").name)
    dst = _unique(d / name)
    tmp = dst.with_name(dst.name + ".part")
    size = 0
    try:
        with open(tmp, "wb") as f:
            while chunk := await field.read_chunk(CHUNK):
                f.write(chunk)
                size += len(chunk)
        tmp.rename(dst)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return {"path": str(dst), "size": size}


_space_cache = {}


async def space(path):
    """Tamaño de cada elemento de una carpeta (du), cacheado 5 minutos."""
    p = safe(path)
    hit = _space_cache.get(p)
    if hit and time.monotonic() - hit[0] < 300:
        return hit[1]
    out = await run("du", "-x", "-b", "-d", "1", str(p), timeout=300)
    items = []
    for line in out.splitlines():
        size, _, name = line.partition("\t")
        if name and Path(name) != p:
            items.append({"name": Path(name).name, "path": name, "size": int(size)})
    # du -d 1 no lista archivos sueltos: se añaden los grandes.
    for e in os.scandir(p):
        if e.is_file(follow_symlinks=False):
            items.append({"name": e.name, "path": e.path, "size": e.stat().st_size, "file": True})
    items.sort(key=lambda x: x["size"], reverse=True)
    result = {"path": str(p), "total": sum(i["size"] for i in items), "items": items[:200]}
    _space_cache[p] = (time.monotonic(), result)
    return result
