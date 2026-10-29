"""Trucos para PCSX2 (.pnach) y Eden (cheats/<BUILDID>.txt).

Los trucos los aporta el usuario (pegados o subidos); aquí solo se colocan en
el sitio correcto y se activan/desactivan.
"""
import re
import shutil
from pathlib import Path

from .. import fileops
from ..ini import Ini
from . import emulators, ps2ids, roms

HOME = Path.home()
PCSX2 = HOME / ".var/app/net.pcsx2.PCSX2/config/PCSX2"
EDEN_LOAD = HOME / ".var/app/dev.eden_emu.eden/data/eden/load"
# Eden no tiene "desactivar" por archivo: los trucos apagados se guardan aquí.
EDEN_OFF = HOME / ".local/share/deckhub/cheats-off"
BUILD_ID = re.compile(r"^[0-9A-Fa-f]{16}([0-9A-Fa-f]{16})?$")
TITLE_ID = re.compile(r"^01[0-9A-Fa-f]{14}$")
NAME = re.compile(r"^[\w .,'()\-+&!]{1,60}$")


def _groups(text):
    """Nombres de trucos etiquetados ([Nombre]) dentro de un .pnach."""
    return [m.group(1).strip() for m in re.finditer(r"^\[([^\]]+)\]\s*$", text, re.M)]


# --- PCSX2 ----------------------------------------------------------------------

def _pnach(serial, crc):
    return PCSX2 / "cheats" / f"{serial}_{crc}.pnach"


def _gameini(serial, crc):
    return Ini(PCSX2 / "gamesettings" / f"{serial}_{crc}.ini")


async def _ps2():
    out = []
    for path, i in (await ps2ids.collect()).items():
        item = {"path": path, "title": i["title"], "serial": i.get("serial"), "crc": i.get("crc"),
                "error": i.get("error"), "cheats": None, "enabled": False, "groups": []}
        if i.get("serial") and i.get("crc"):
            f = _pnach(i["serial"], i["crc"])
            if f.exists():
                text = f.read_text(errors="replace")
                item["cheats"] = text
                item["groups"] = _groups(text)
                item["enabled"] = _gameini(i["serial"], i["crc"]).get("EmuCore", "EnableCheats") == "true"
        out.append(item)
    return sorted(out, key=lambda x: x["title"].lower())


async def _ps2_lookup(path):
    info = (await ps2ids.collect()).get(path)
    if not info or not info.get("serial") or not info.get("crc"):
        raise ValueError("No pude identificar ese juego de PS2 (serial/CRC).")
    return info["serial"], info["crc"]


async def ps2_save(path, text):
    serial, crc = await _ps2_lookup(path)
    f = _pnach(serial, crc)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text.replace("\r\n", "\n").rstrip() + "\n")
    await ps2_toggle(path, True)


async def ps2_toggle(path, enabled):
    if emulators._running("net.pcsx2.PCSX2"):
        raise RuntimeError("Cierra PCSX2 para cambiar los trucos.")
    serial, crc = await _ps2_lookup(path)
    ini = _gameini(serial, crc)
    ini.set("EmuCore", "EnableCheats", "true" if enabled else "false")
    # PCSX2 2.x solo aplica los trucos etiquetados que están en [Cheats] Enable.
    f = _pnach(serial, crc)
    groups = _groups(f.read_text(errors="replace")) if f.exists() else []
    ini.set_list("Cheats", "Enable", groups if enabled else [])
    ini.save()


async def ps2_delete(path):
    serial, crc = await _ps2_lookup(path)
    await ps2_toggle(path, False)
    if _pnach(serial, crc).exists():
        fileops.trash([str(_pnach(serial, crc))])


# --- Eden -----------------------------------------------------------------------

def _eden_entries(root, enabled):
    out = []
    if not root.exists():
        return out
    for tdir in root.iterdir():
        if not TITLE_ID.match(tdir.name):
            continue
        for mod in tdir.iterdir():
            cheats = mod / "cheats"
            if cheats.is_dir():
                for f in cheats.glob("*.txt"):
                    out.append({"title_id": tdir.name.upper(), "name": mod.name, "build_id": f.stem.upper(),
                                "enabled": enabled, "text": f.read_text(errors="replace")})
    return out


async def _switch():
    games = (await roms.collect())["games"]
    titles = {g["base_id"]: g["title"] for g in games if g.get("base_id") and g.get("kind") == "base"}
    entries = _eden_entries(EDEN_LOAD, True) + _eden_entries(EDEN_OFF, False)
    for e in entries:
        e["title"] = titles.get(e["title_id"], e["title_id"])
    games_out = [{"title_id": tid, "title": t} for tid, t in sorted(titles.items(), key=lambda x: x[1].lower())]
    return {"cheats": entries, "games": games_out}


def _check(title_id, name, build_id=None):
    if not TITLE_ID.match(title_id or ""):
        raise ValueError(f"Title ID no válido: {title_id!r}")
    if not NAME.match(name or ""):
        raise ValueError("Nombre de truco no válido (letras, números y espacios, máx. 60).")
    if build_id is not None and not BUILD_ID.match(build_id or ""):
        raise ValueError("El Build ID debe tener 16 o 32 caracteres hexadecimales "
                         "(es el nombre del .txt, p. ej. 0123456789ABCDEF.txt).")


def eden_save(title_id, name, build_id, text):
    _check(title_id, name, build_id)
    d = EDEN_LOAD / title_id.upper() / name / "cheats"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{build_id.upper()}.txt").write_text(text.replace("\r\n", "\n").rstrip() + "\n")


def eden_toggle(title_id, name, enabled):
    _check(title_id, name)
    if emulators._running("dev.eden_emu.eden"):
        raise RuntimeError("Cierra Eden para cambiar los trucos.")
    src_root, dst_root = (EDEN_OFF, EDEN_LOAD) if enabled else (EDEN_LOAD, EDEN_OFF)
    src = src_root / title_id.upper() / name
    if not src.exists():
        raise ValueError("No encontré ese truco.")
    dst = dst_root / title_id.upper() / name
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        fileops.trash([str(dst)])
    shutil.move(str(src), str(dst))


def eden_delete(title_id, name):
    _check(title_id, name)
    paths = [str(r / title_id.upper() / name) for r in (EDEN_LOAD, EDEN_OFF)
             if (r / title_id.upper() / name).exists()]
    fileops.trash(paths)  # a la papelera, como todo en DeckHub


async def collect():
    return {"ps2": await _ps2(), "switch": await _switch()}
