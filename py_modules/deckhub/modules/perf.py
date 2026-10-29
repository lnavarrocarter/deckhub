"""Rendimiento: ajustes de memoria y swap al estilo de CryoUtilities.

Leer los valores no requiere permisos; cambiarlos lo hace el ayudante
/etc/deckhub/deckhub-tune (root, instalado una vez por el usuario) vía sudo -n.
"""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from .. import jobs

HELPER_SRC = Path(__file__).resolve().parent.parent / "helper/deckhub-tune"
HELPER = Path("/etc/deckhub/deckhub-tune")
SUDOERS = "/etc/sudoers.d/zz-deckhub-tune"
MM = "/sys/kernel/mm/transparent_hugepage"
SWAPFILE = Path("/home/swapfile")

# id, archivo, valor de fábrica de SteamOS 3.9, recomendado y por qué.
SETTINGS = [
    {"id": "swappiness", "path": "/proc/sys/vm/swappiness", "factory": "60", "recommended": "1",
     "name": "Swappiness", "desc": "Cuánto prefiere el sistema mover memoria a la swap. Bajo = mantiene los juegos en RAM y usa la swap solo si hace falta."},
    {"id": "compaction_proactiveness", "path": "/proc/sys/vm/compaction_proactiveness", "factory": "20", "recommended": "0",
     "name": "Compactación proactiva", "desc": "Reordena la memoria en segundo plano. Desactivarla evita pequeños tirones durante el juego."},
    {"id": "page_lock_unfairness", "path": "/proc/sys/vm/page_lock_unfairness", "factory": "5", "recommended": "1",
     "name": "Page lock unfairness", "desc": "Cómo reparte el kernel el acceso a páginas de memoria. 1 reduce esperas largas en juegos con mucha carga."},
    {"id": "khugepaged_defrag", "path": f"{MM}/khugepaged/defrag", "factory": "1", "recommended": "0",
     "name": "Desfragmentación de huge pages", "desc": "Proceso que junta memoria en bloques grandes. Desactivarlo quita trabajo de fondo que puede causar tirones."},
    {"id": "thp_enabled", "path": f"{MM}/enabled", "factory": "always", "recommended": "always",
     "name": "Transparent Huge Pages", "desc": "Bloques de memoria grandes para juegos. SteamOS 3.9 ya lo trae activado."},
    {"id": "thp_shmem", "path": f"{MM}/shmem_enabled", "factory": "advise", "recommended": "advise",
     "name": "Huge pages en memoria compartida", "desc": "Lo mismo para memoria compartida. «advise» es lo recomendado y ya viene así."},
]
SWAP_RECOMMENDED_GB = 16


def _read(path):
    try:
        v = Path(path).read_text().strip()
    except OSError:
        return None
    return v.split("[", 1)[1].split("]", 1)[0] if "[" in v else v


def _meminfo():
    out = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        k, v = line.split(":", 1)
        out[k] = int(v.split()[0]) * 1024
    return out


def _swaps():
    out = []
    for line in Path("/proc/swaps").read_text().splitlines()[1:]:
        name, kind, size, used, *_ = line.split()
        out.append({"name": name, "kind": "zram" if "zram" in name else kind,
                    "size": int(size) * 1024, "used": int(used) * 1024})
    return out


def _vram():
    for f in Path("/sys/class/drm").glob("card*/device/mem_info_vram_total"):
        try:
            return int(f.read_text())
        except (OSError, ValueError):
            continue
    return None


def _sha(path):
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


def helper_state():
    installed = HELPER.is_file()
    allowed = installed and subprocess.run(["sudo", "-n", "-l", str(HELPER)], capture_output=True).returncode == 0
    return {"installed": installed, "allowed": allowed, "up_to_date": installed and _sha(HELPER) == _sha(HELPER_SRC),
            "install_command": (
                f"sudo install -D -o root -g root -m 0755 '{HELPER_SRC}' {HELPER} && "
                f"echo 'deck ALL=(root) NOPASSWD: {HELPER}' | sudo tee {SUDOERS} >/dev/null && sudo chmod 440 {SUDOERS}")}


async def collect():
    settings = []
    for s in SETTINGS:
        cur = _read(s["path"])
        settings.append({k: s[k] for k in ("id", "name", "desc", "factory", "recommended")} | {
            "current": cur, "optimized": cur == s["recommended"], "tunable": s["recommended"] != s["factory"]})
    mem = _meminfo()
    swaps = _swaps()
    swapfile = next((s for s in swaps if s["name"] == str(SWAPFILE)), None)
    return {
        "settings": settings,
        "persisted": Path("/etc/sysctl.d/99-deckhub.conf").exists() or Path("/etc/tmpfiles.d/deckhub-thp.conf").exists(),
        "memory": {"total": mem.get("MemTotal"), "available": mem.get("MemAvailable")},
        "swaps": swaps,
        "swapfile": {"size": swapfile["size"] if swapfile else (SWAPFILE.stat().st_size if SWAPFILE.exists() else 0),
                     "used": swapfile["used"] if swapfile else 0, "recommended_gb": SWAP_RECOMMENDED_GB},
        "home_free": shutil.disk_usage("/home").free,
        "vram": _vram(),
        "helper": helper_state(),
    }


def _run(job, *args):
    if not helper_state()["allowed"]:
        raise RuntimeError("Falta instalar el ayudante de rendimiento (pestaña Rendimiento).")
    r = subprocess.run(["sudo", "-n", str(HELPER), *args], capture_output=True, text=True, timeout=900)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or "el ayudante falló")
    job["done"] = job["total"] = 1
    return r.stdout.strip()


def apply(ids, persist=True):
    by_id = {s["id"]: s for s in SETTINGS}
    bad = [i for i in ids if i not in by_id]
    if bad or not ids:
        raise ValueError(f"ajuste desconocido: {bad or ids}")
    values = {i: by_id[i]["recommended"] for i in ids}
    args = ["apply", json.dumps(values)] + (["--persist"] if persist else [])
    return jobs.start("perf", f"Aplicar {len(values)} ajustes de memoria", _run, *args)


def revert():
    return jobs.start("perf", "Volver a los ajustes de memoria de fábrica", _run, "revert")


def resize_swap(gb):
    gb = int(gb)
    if not 1 <= gb <= 32:
        raise ValueError("el tamaño de swap debe estar entre 1 y 32 GB")
    return jobs.start("perf", f"Cambiar el archivo de swap a {gb} GB", _run, "swap", str(gb))
