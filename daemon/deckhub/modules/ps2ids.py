"""Serial y CRC de juegos de PS2 leídos de la ISO, como los calcula PCSX2.

PCSX2 nombra trucos y ajustes por juego como <SERIAL>_<CRC>: el serial sale de
SYSTEM.CNF (BOOT2 = cdrom0:\\SLUS_123.45;1) y el CRC es el XOR de todas las
palabras de 32 bits del ejecutable ELF.
"""
import asyncio
import json
import re
import struct
from pathlib import Path

from . import roms

SECTOR = 2048
CACHE = Path.home() / ".cache/deckhub/ps2ids.json"


def _records(f, lba, size):
    """Entradas (nombre, lba, tamaño) de un directorio ISO9660."""
    f.seek(lba * SECTOR)
    data = f.read(size)
    pos = 0
    while pos < len(data):
        n = data[pos]
        if n == 0:  # relleno hasta el siguiente sector
            pos = (pos // SECTOR + 1) * SECTOR
            continue
        rec = data[pos:pos + n]
        ext_lba, ext_size = struct.unpack_from("<I", rec, 2)[0], struct.unpack_from("<I", rec, 10)[0]
        name = rec[33:33 + rec[32]].decode("ascii", "replace").split(";")[0]
        yield name.upper(), ext_lba, ext_size
        pos += n


def identify(path):
    with open(path, "rb") as f:
        f.seek(16 * SECTOR)
        pvd = f.read(SECTOR)
        if pvd[1:6] != b"CD001":
            raise ValueError("no es una imagen ISO9660")
        root = pvd[156:156 + 34]
        root_lba, root_size = struct.unpack_from("<I", root, 2)[0], struct.unpack_from("<I", root, 10)[0]
        entries = {name: (lba, size) for name, lba, size in _records(f, root_lba, root_size)}
        if "SYSTEM.CNF" not in entries:
            raise ValueError("sin SYSTEM.CNF")
        lba, size = entries["SYSTEM.CNF"]
        f.seek(lba * SECTOR)
        cnf = f.read(size).decode("ascii", "replace")
        m = re.search(r"BOOT2\s*=\s*cdrom0:\\?([^;\s]+)", cnf, re.I)
        if not m:
            raise ValueError("SYSTEM.CNF sin BOOT2")
        elf_name = m.group(1).split("\\")[-1].upper()
        serial = re.sub(r"^([A-Z]{4})_(\d{3})\.(\d{2})$", r"\1-\2\3", elf_name)
        if elf_name not in entries:
            return {"serial": serial, "crc": None}
        lba, size = entries[elf_name]
        f.seek(lba * SECTOR)
        elf = f.read(size)
    words = struct.unpack_from(f"<{len(elf) // 4}I", elf)
    crc = 0
    for w in words:
        crc ^= w
    return {"serial": serial, "crc": f"{crc:08X}"}


def _load_cache():
    try:
        return json.loads(CACHE.read_text())
    except (OSError, ValueError):
        return {}


async def collect():
    """{ruta_iso: {serial, crc, title}} para los juegos de PS2 en .iso (cacheado)."""
    cache, changed, out = _load_cache(), False, {}
    for g in (await roms.collect())["games"]:
        if g["console"] != "ps2" or not g["path"].lower().endswith(".iso"):
            continue
        st = Path(g["path"]).stat()
        stamp = f"{st.st_size}:{int(st.st_mtime)}"
        hit = cache.get(g["path"])
        if not hit or hit.get("stamp") != stamp:
            try:
                info = await asyncio.to_thread(identify, g["path"])
            except (OSError, ValueError, struct.error) as e:
                info = {"serial": None, "crc": None, "error": str(e)}
            hit = {**info, "stamp": stamp}
            cache[g["path"]] = hit
            changed = True
        out[g["path"]] = {**hit, "title": g["title"]}
    if changed:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(cache, indent=1))
    return out
