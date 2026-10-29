"""Emuladores: catálogo por consola, estado, instalación y configuración automática."""
import os
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

from .. import jobs
from ..ini import Ini
from . import packages, roms

HOME = Path.home()
MEDIA = Path("/run/media") / HOME.name
VAR = HOME / ".var/app"
GRANT = f"{MEDIA}:ro"  # los emuladores solo necesitan leer las ROMs

# "launch": argumentos para `flatpak run` que abren un juego directamente; {rom} es la ruta.
CATALOG = [
    {"id": "net.pcsx2.PCSX2", "name": "PCSX2", "consoles": ["ps2"], "recommended": True,
     "launch": ["net.pcsx2.PCSX2", "-batch", "-fullscreen", "--", "{rom}"]},
    {"id": "dev.eden_emu.eden", "name": "Eden", "consoles": ["switch"], "recommended": True,
     "launch": ["dev.eden_emu.eden", "-f", "-g", "{rom}"]},
    {"id": "io.github.ryubing.Ryujinx", "name": "Ryujinx (Ryubing)", "consoles": ["switch"],
     "launch": ["io.github.ryubing.Ryujinx", "--fullscreen", "{rom}"]},
    {"id": "org.libretro.RetroArch", "name": "RetroArch", "recommended": True,
     "consoles": ["nes", "snes", "gb", "gbc", "gba", "n64", "genesis", "psx", "pce", "segacd", "saturn"]},
    {"id": "org.ppsspp.PPSSPP", "name": "PPSSPP", "consoles": ["psp"], "recommended": True},
    {"id": "org.DolphinEmu.dolphin-emu", "name": "Dolphin", "consoles": ["gc", "wii", "gc_wii"], "recommended": True},
    {"id": "org.azahar_emu.Azahar", "name": "Azahar", "consoles": ["3ds"], "recommended": True},
    {"id": "net.kuribo64.melonDS", "name": "melonDS", "consoles": ["nds"], "recommended": True},
    {"id": "info.cemu.Cemu", "name": "Cemu", "consoles": ["wiiu"], "recommended": True},
    {"id": "org.flycast.Flycast", "name": "Flycast", "consoles": ["dreamcast"], "recommended": True},
    {"id": "app.xemu.xemu", "name": "xemu", "consoles": ["xbox"], "recommended": True},
]
DISCONTINUED = {"org.yuzu_emu.yuzu": "yuzu está descontinuado desde 2024; Eden es su sucesor."}
BY_ID = {e["id"]: e for e in CATALOG}


# --- utilidades ---------------------------------------------------------------

def _running(app_id):
    # El comando de bwrap/flatpak de una app en ejecución contiene su id.
    return subprocess.run(["pgrep", "-f", f"--app-id={app_id}|flatpak run.* {app_id}"],
                          capture_output=True).returncode == 0


def _granted(app_id):
    out = subprocess.run(["flatpak", "override", "--user", "--show", app_id],
                         capture_output=True, text=True).stdout
    return str(MEDIA) in out


def _grant(app_id):
    subprocess.run(["flatpak", "override", "--user", f"--filesystem={GRANT}", app_id],
                   check=True, capture_output=True)


def _dirs_for(games, consoles):
    """Carpetas (únicas, ordenadas) que contienen juegos de esas consolas."""
    return sorted({os.path.dirname(g["path"]) for g in games if g["console"] in consoles})


def _find_ps2_bios():
    """Carpeta 'bios' en las unidades con una imagen de BIOS de PS2 (4 MB)."""
    roots = [MEDIA / m for m in os.listdir(MEDIA)] if MEDIA.exists() else []
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            depth = Path(dirpath).relative_to(root).parts
            if len(depth) >= 3:
                dirnames.clear()
            dirnames[:] = [d for d in dirnames if not d.startswith((".", "$")) and d not in roms.SKIP_DIRS - {"bios"}]
            if Path(dirpath).name.lower() != "bios":
                continue
            images = [f for f in filenames if f.lower().endswith(".bin")
                      and os.path.getsize(os.path.join(dirpath, f)) == 4 * 1024 * 1024]
            if images:
                images.sort(key=lambda f: ("scph" not in f.lower(), f))  # preferir volcados SCPH
                return dirpath, images
    return None, []


# --- PCSX2 --------------------------------------------------------------------

PCSX2_INI = VAR / "net.pcsx2.PCSX2/config/PCSX2/inis/PCSX2.ini"


def _pcsx2_status(games):
    ini = Ini(PCSX2_INI)
    bios_dir, images = _find_ps2_bios()
    paths = [l.split("=", 1)[1].strip() for l in ini._section("GameList") if Ini._key(l) == "RecursivePaths"]
    wanted = _dirs_for(games, {"ps2"})
    warnings = []
    if not images:
        warnings.append("No encontré una BIOS de PS2 (carpeta 'bios' con un .bin de 4 MB) en las unidades.")
    configured = bool(wanted) and set(wanted) <= set(paths) and ini.get("Folders", "Bios") == bios_dir
    return {"configured": configured, "rom_dirs": wanted, "bios": bios_dir,
            "bios_file": images[0] if images else None, "warnings": warnings}


def _pcsx2_configure(job, games):
    bios_dir, images = _find_ps2_bios()
    ini = Ini(PCSX2_INI)
    if bios_dir:
        ini.set("Folders", "Bios", bios_dir)
        ini.set("Filenames", "BIOS", images[0])
    dirs = _dirs_for(games, {"ps2"})
    if dirs:
        ini.set_list("GameList", "RecursivePaths", dirs)
    ini.set("UI", "SetupWizardIncomplete", "false")
    ini.set("UI", "StartFullscreen", "true")
    ini.set("UI", "ConfirmShutdown", "false")
    ini.save()


# --- Eden (Switch) -----------------------------------------------------------

EDEN = VAR / "dev.eden_emu.eden"
EDEN_INI = EDEN / "config/eden/qt-config.ini"
EDEN_KEYS = EDEN / "data/eden/keys"
EDEN_FIRMWARE = EDEN / "data/eden/nand/system/Contents/registered"
# Llaves de emuladores anteriores que se pueden reutilizar (son tuyas, de tu consola).
OLD_KEYS = [VAR / "org.yuzu_emu.yuzu/data/yuzu/keys", HOME / ".local/share/yuzu/keys",
            HOME / ".local/share/citron/keys", HOME / ".local/share/sudachi/keys"]
NAND_DIRS = ["SDMC", "UserNAND", "SysNAND"]


def _eden_status(games):
    ini = Ini(EDEN_INI)
    wanted = _dirs_for(games, {"switch"})
    current = [l.split("=", 1)[1] for l in ini._section("UI")
               if (Ini._key(l) or "").startswith("Paths\\gamedirs\\") and Ini._key(l).endswith("\\path")]
    keys = (EDEN_KEYS / "prod.keys").exists()
    firmware = EDEN_FIRMWARE.exists() and any(EDEN_FIRMWARE.iterdir())
    warnings = []
    if not keys:
        src = next((d for d in OLD_KEYS if (d / "prod.keys").exists()), None)
        warnings.append("Faltan las llaves (prod.keys)." +
                        (f" Se copiarán desde {src} al configurar." if src else
                         " Cópialas desde tu consola a " + str(EDEN_KEYS)))
    if not firmware:
        warnings.append("Falta el firmware de Switch: usa «Instalar firmware» con el volcado de tu "
                        "consola (.zip o carpeta con los .nca). Sin él muchos juegos no arrancan.")
    configured = keys and bool(wanted) and set(wanted) <= set(current)
    return {"configured": configured, "rom_dirs": wanted, "keys": keys, "firmware": firmware,
            "firmware_info": _firmware_info(), "warnings": warnings}


def _eden_configure(job, games):
    if not (EDEN_KEYS / "prod.keys").exists():
        src = next((d for d in OLD_KEYS if (d / "prod.keys").exists()), None)
        if src:
            EDEN_KEYS.mkdir(parents=True, exist_ok=True)
            for f in src.glob("*.keys"):
                shutil.copy2(f, EDEN_KEYS / f.name)
    ini = Ini(EDEN_INI, sep="=")
    ini.remove("UI", lambda k: k.startswith("Paths\\gamedirs\\"))
    dirs = NAND_DIRS + _dirs_for(games, {"switch"})
    pairs = [("Paths\\gamedirs\\size", len(dirs))]
    for i, d in enumerate(dirs, 1):
        pairs += [(f"Paths\\gamedirs\\{i}\\path", d),
                  (f"Paths\\gamedirs\\{i}\\deep_scan\\default", "true"),
                  (f"Paths\\gamedirs\\{i}\\deep_scan", "false"),
                  (f"Paths\\gamedirs\\{i}\\expanded\\default", "true"),
                  (f"Paths\\gamedirs\\{i}\\expanded", "true")]
    ini.add("UI", pairs)
    ini.set("UI", "fullscreen\\default", "false")
    ini.set("UI", "fullscreen", "true")
    ini.save()


def _firmware_info():
    files = list(EDEN_FIRMWARE.glob("*.nca")) if EDEN_FIRMWARE.exists() else []
    newest = max((f.stat().st_mtime for f in files), default=None)
    return {"files": len(files), "installed": int(newest) if newest else None}


def _install_firmware(job, source, cleanup):
    """Copia los .nca de un volcado de firmware (zip o carpeta) a la NAND de Eden.

    Es lo mismo que hace Eden en Herramientas → Instalar firmware: reemplaza el
    contenido de nand/system/Contents/registered con los .nca del volcado.
    """
    from .. import fileops  # evita import circular al cargar los módulos

    if _running("dev.eden_emu.eden"):
        raise RuntimeError("Cierra Eden antes de instalar el firmware.")
    src = Path(source)
    try:
        if src.is_dir():
            ncas = [f for f in src.rglob("*.nca") if f.is_file()]
            if len(ncas) < 20:
                raise RuntimeError(f"La carpeta solo tiene {len(ncas)} archivos .nca; no parece un firmware completo.")
            job["total"] = sum(f.stat().st_size for f in ncas)
            items = [(f.name, f) for f in ncas]
        else:
            z = zipfile.ZipFile(src)
            members = [m for m in z.infolist() if m.filename.lower().endswith(".nca") and not m.is_dir()]
            if len(members) < 20:
                raise RuntimeError(f"El zip solo tiene {len(members)} archivos .nca; no parece un firmware completo.")
            job["total"] = sum(m.file_size for m in members)
            items = [(Path(m.filename).name, m) for m in members]

        # El firmware anterior va a la papelera (se puede recuperar).
        if EDEN_FIRMWARE.exists() and any(EDEN_FIRMWARE.iterdir()):
            fileops.trash([str(EDEN_FIRMWARE)])
        EDEN_FIRMWARE.mkdir(parents=True, exist_ok=True)
        for name, item in items:
            dest = EDEN_FIRMWARE / name
            if isinstance(item, Path):
                shutil.copyfile(item, dest)
                job["done"] += item.stat().st_size
            else:
                with z.open(item) as fi, open(dest, "wb") as fo:
                    shutil.copyfileobj(fi, fo, 8 * 1024 * 1024)
                job["done"] += item.file_size
    finally:
        if cleanup:
            src.unlink(missing_ok=True)  # el zip temporal que se subió


def install_firmware(source, cleanup=False):
    return jobs.start("firmware", "Instalar firmware de Switch en Eden", _install_firmware, source, cleanup)


def install_keys(files):
    """files: {"prod.keys": bytes, "title.keys": bytes}. Las anteriores van a la papelera."""
    from .. import fileops

    if "prod.keys" not in files:
        raise ValueError("Falta prod.keys.")
    text = files["prod.keys"].decode("utf-8", "replace")
    if not re.search(r"^\s*header_key\s*=\s*[0-9a-fA-F]{64}", text, re.M):
        raise ValueError("Ese archivo no parece un prod.keys válido (no tiene header_key).")
    EDEN_KEYS.mkdir(parents=True, exist_ok=True)
    old = [str(EDEN_KEYS / n) for n in files if (EDEN_KEYS / n).exists()]
    if old:
        fileops.trash(old)
    for name, data in files.items():
        (EDEN_KEYS / name).write_bytes(data)


CONFIGURERS = {
    "net.pcsx2.PCSX2": (_pcsx2_status, _pcsx2_configure),
    "dev.eden_emu.eden": (_eden_status, _eden_configure),
}


# --- API ----------------------------------------------------------------------

async def collect():
    installed = {a["id"]: a for a in (await packages.collect())["apps"]}
    library = await roms.collect()
    games = library["games"]
    counts = {c["console"]: c["count"] for c in library["consoles"]}
    out = []
    for e in CATALOG:
        app = installed.get(e["id"])
        item = {"id": e["id"], "name": e["name"], "consoles": e["consoles"],
                "console_names": [roms.NAMES.get(c, c) for c in e["consoles"]],
                "recommended": e.get("recommended", False),
                "installed": bool(app), "version": app["version"] if app else None,
                "size": app["size"] if app else None,
                "games": sum(counts.get(c, 0) for c in e["consoles"]),
                "auto_config": e["id"] in CONFIGURERS, "access": False, "configured": None,
                "warnings": []}
        if app:
            item["access"] = _granted(e["id"])
            if e["id"] in CONFIGURERS:
                item |= CONFIGURERS[e["id"]][0](games)
        out.append(item)
    stale = [{"id": i, "name": installed[i]["name"], "reason": r}
             for i, r in DISCONTINUED.items() if i in installed]
    return {"emulators": out, "discontinued": stale}


def _configure(job, app_id, games):
    if _running(app_id):
        raise RuntimeError(f"Cierra {BY_ID[app_id]['name']} antes de configurarlo.")
    _grant(app_id)
    if app_id in CONFIGURERS:
        CONFIGURERS[app_id][1](job, games)


def _install_and_configure(job, app_id, games):
    packages._flatpak(job, ["install", "flathub", app_id])
    _configure(job, app_id, games)


async def configure(app_id):
    if app_id not in BY_ID:
        raise ValueError(f"emulador desconocido: {app_id}")
    games = (await roms.collect())["games"]
    return jobs.start("emulator", f"Configurar {BY_ID[app_id]['name']}", _configure, app_id, games)


async def install(app_id):
    if app_id not in BY_ID:
        raise ValueError(f"emulador desconocido: {app_id}")
    games = (await roms.collect())["games"]
    return jobs.start("emulator", f"Instalar y configurar {BY_ID[app_id]['name']}",
                      _install_and_configure, app_id, games)
