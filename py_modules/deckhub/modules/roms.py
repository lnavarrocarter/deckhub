"""Detección de juegos por consola en las unidades montadas y carpetas de ROMs."""
import os
import re
from pathlib import Path

from ..util import cached

HOME = Path.home()
SCAN_ROOTS = [Path("/run/media") / HOME.name, HOME / "Emulation/roms", HOME / "RetroHub/roms"]
MAX_DEPTH = 4
SKIP_DIRS = {".Trash-1000", "System Volume Information", "WindowsApps", "Program Files",
             "$RECYCLE.BIN", "bios", "steamapps", "shadercache", "compatdata"}

BY_EXT = {
    "nsp": "switch", "xci": "switch", "nsz": "switch", "xcz": "switch",
    "sfc": "snes", "smc": "snes", "nes": "nes", "gba": "gba", "gb": "gb", "gbc": "gbc",
    "n64": "n64", "z64": "n64", "v64": "n64", "nds": "nds", "3ds": "3ds", "cia": "3ds",
    "md": "genesis", "gen": "genesis", "pce": "pce", "rvz": "gc_wii", "wbfs": "wii", "gcm": "gc",
}
DISC_EXT = {"iso", "chd", "cso", "bin", "img", "zso"}
# Pistas en la ruta para saber a qué consola pertenece una imagen de disco.
FOLDER_HINTS = [("ps2", "ps2"), ("psx", "psx"), ("ps1", "psx"), ("psp", "psp"),
                ("gamecube", "gc"), ("gc", "gc"), ("wii", "wii"), ("dreamcast", "dreamcast"),
                ("saturn", "saturn"), ("segacd", "segacd")]
NAMES = {"switch": "Nintendo Switch", "ps2": "PlayStation 2", "psx": "PlayStation",
         "psp": "PSP", "gc": "GameCube", "wii": "Wii", "gc_wii": "GameCube / Wii",
         "snes": "Super Nintendo", "nes": "NES", "gba": "Game Boy Advance", "gb": "Game Boy",
         "gbc": "Game Boy Color", "n64": "Nintendo 64", "nds": "Nintendo DS", "3ds": "Nintendo 3DS",
         "genesis": "Mega Drive", "pce": "PC Engine", "dreamcast": "Dreamcast",
         "saturn": "Saturn", "segacd": "Sega CD", "disc": "Disco (sin identificar)"}

TITLE_ID = re.compile(r"\b(01[0-9A-Fa-f]{14})\b")
VERSION = re.compile(r"\[v(\d+)\]|\bv(\d+(?:\.\d+)*)\b|\((\d+\.\d+(?:\.\d+)?)\)")
NOISE = re.compile(r"\[[^\]]*\]|\([^)]*\)|\b(?:Base|NSP|UPD|UPDATE|DLC|APP)\b", re.I)


def _switch_info(name):
    m = TITLE_ID.search(name)
    info = {"title_id": None, "base_id": None, "kind": "base"}
    if m:
        tid = m.group(1).upper()
        group = int(tid[-4], 16) & 0xE  # la DLC suma 1 al cuarto dígito desde el final
        info["title_id"] = tid
        info["base_id"] = f"{tid[:-4]}{group:X}000"
        info["kind"] = "base" if tid.endswith("000") else "update" if tid.endswith("800") else "dlc"
    elif re.search(r"\b(UPD|UPDATE)\b", name, re.I):
        info["kind"] = "update"
    elif re.search(r"\bDLC\b", name, re.I):
        info["kind"] = "dlc"
    return info


def _title(stem):
    t = NOISE.sub(" ", stem)
    t = TITLE_ID.sub(" ", t)
    t = re.sub(r"\bv\d+(?:\.\d+)*\b", " ", t, flags=re.I)
    if " " not in stem.strip():  # nombres estilo "Mario.Tennis.Aces"
        t = t.replace(".", " ")
    t = t.replace("_", " ")
    return re.sub(r"\s+", " ", t).strip(" -.") or stem


def _version(stem, console):
    v = VERSION.search(stem)
    if not v:
        return None
    raw = next(g for g in v.groups() if g)
    if console == "switch" and raw.isdigit():
        # En Switch la versión es número_de_parche * 65536; 0 es el juego base.
        n = int(raw) // 65536
        return f"parche {n}" if n else None
    return raw


def classify(filename, folder=""):
    """Devuelve la consola y metadatos de un archivo de juego, o None."""
    stem, _, ext = filename.rpartition(".")
    ext = ext.lower()
    console = BY_EXT.get(ext)
    if console is None and ext in DISC_EXT:
        low = f"{folder}/{filename}".lower()
        console = next((c for hint, c in FOLDER_HINTS if re.search(rf"\b{hint}\b", low)), "disc")
    if console is None:
        return None
    info = {"console": console, "console_name": NAMES[console], "title": _title(stem)}
    if console == "switch":
        info |= _switch_info(filename)
    info["version"] = _version(stem, console)
    return info


def _walk(root, depth=0):
    try:
        it = list(os.scandir(root))
    except OSError:
        return
    for e in it:
        if e.is_dir(follow_symlinks=False):
            if depth < MAX_DEPTH and e.name not in SKIP_DIRS and not e.name.startswith("."):
                yield from _walk(e.path, depth + 1)
        elif e.is_file(follow_symlinks=False):
            yield e


def _patch(g):
    v = g.get("version") or ""
    return int(v.split()[-1]) if v.startswith("parche") else 0


def _group_switch(games):
    """Asocia actualizaciones y DLC a su juego base (mismo base_id).

    Eden/yuzu cargan las actualizaciones y DLC que encuentran en la carpeta de
    juegos, así que basta con que estén junto al juego; aquí solo se informa.
    """
    sw = [g for g in games if g["console"] == "switch"]
    by_title = {}
    for g in sw:
        if g.get("kind") == "base" and not g.get("base_id"):
            by_title.setdefault(g["title"].lower(), g)  # sin Title ID: se agrupa por nombre
    bases = {g["base_id"]: g for g in sw if g.get("kind") == "base" and g.get("base_id")}
    for g in sw:
        if g.get("kind") == "base":
            g.setdefault("updates", [])
            g.setdefault("dlc", [])
    for g in sw:
        if g.get("kind") not in ("update", "dlc"):
            continue
        base = bases.get(g.get("base_id")) or by_title.get(g["title"].lower())
        g["orphan"] = base is None
        if base is None:
            continue
        entry = {"file": g["file"], "path": g["path"], "size": g["size"],
                 "version": g.get("version"), "title_id": g.get("title_id")}
        base["updates" if g["kind"] == "update" else "dlc"].append(entry)
    for b in (g for g in sw if g.get("kind") == "base"):
        ups = sorted(b["updates"], key=_patch)
        b["latest_update"] = ups[-1]["version"] if ups else None
        # Si hay varias actualizaciones, solo cuenta la más nueva; las demás sobran.
        b["stale_updates"] = [u["path"] for u in ups[:-1]]


@cached(60)
async def collect():
    games = []
    for root in SCAN_ROOTS:
        if not root.exists():
            continue
        for e in _walk(root):
            info = classify(e.name, os.path.dirname(e.path))
            # .bin sueltos suelen ser pistas de un .cue o BIOS: solo cuentan con pista de consola.
            if info is None or (e.name.lower().endswith(".bin") and info["console"] == "disc"):
                continue
            games.append({**info, "file": e.name, "path": e.path, "size": e.stat().st_size})

    _group_switch(games)
    consoles = {}
    for g in games:
        c = consoles.setdefault(g["console"], {"console": g["console"], "name": g["console_name"],
                                               "count": 0, "size": 0})
        c["count"] += 1
        c["size"] += g["size"]
    games.sort(key=lambda g: (g["console"], g["title"].lower()))
    return {"consoles": sorted(consoles.values(), key=lambda c: -c["size"]), "games": games}
