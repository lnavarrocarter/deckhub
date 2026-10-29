"""Discos, particiones, uso, temperaturas del NVMe y montaje de unidades extraíbles."""
import json
import logging
import re

import psutil

from .. import config
from ..util import cached, hwmon, read, run

log = logging.getLogger("deckhub.storage")
IGNORED_FS = {"squashfs", "overlay", "tmpfs", "devtmpfs", "efivarfs"}
MOUNTABLE_FS = {"ntfs", "exfat", "vfat", "ext4", "btrfs", "f2fs", "xfs"}
# Solo se montan/desmontan tarjetas SD y USB; el disco interno no se toca.
REMOVABLE = re.compile(r"^/dev/(mmcblk\d+p\d+|sd[a-z]\d+)$")


async def _lsblk():
    out = await run("lsblk", "-J", "-b", "-o",
                    "NAME,PATH,SIZE,TYPE,FSTYPE,LABEL,UUID,MODEL,MOUNTPOINT,FSUSED")
    try:
        return json.loads(out)["blockdevices"]
    except (ValueError, KeyError):
        return []


def _partition(p, automount):
    fs = p.get("fstype")
    return {
        "name": p["name"], "path": p.get("path"), "size": p.get("size"), "fstype": fs,
        "label": p.get("label"), "uuid": p.get("uuid"), "mountpoint": p.get("mountpoint"),
        "used": int(p["fsused"]) if p.get("fsused") else None,
        "mountable": bool(REMOVABLE.match(p.get("path") or "")) and fs in MOUNTABLE_FS,
        "automount": p.get("uuid") in automount,
    }


@cached(5)
async def collect():
    automount = set(config.load()["automount"])
    disks = []
    for d in await _lsblk():
        if d.get("type") != "disk" or d["name"].startswith(("zram", "loop")):
            continue
        disks.append({
            "name": d["name"],
            "model": (d.get("model") or "").strip() or None,
            "size": d.get("size"),
            "removable": d["name"].startswith(("mmcblk", "sd")),
            "partitions": [_partition(p, automount) for p in d.get("children", [])],
        })

    mounts, seen = [], set()
    for p in psutil.disk_partitions():
        if p.fstype in IGNORED_FS or p.device in seen:
            continue
        if not (p.mountpoint in ("/", "/home") or p.mountpoint.startswith("/run/media")):
            continue
        seen.add(p.device)
        u = psutil.disk_usage(p.mountpoint)
        mounts.append({
            "device": p.device, "mountpoint": p.mountpoint, "fstype": p.fstype,
            "total": u.total, "used": u.used, "free": u.free, "percent": u.percent,
        })

    temps = {}
    nvme = hwmon("nvme")
    if nvme is not None:
        for i in (1, 2, 3):
            t = read(nvme / f"temp{i}_input", cast=int)
            if t is not None:
                label = read(nvme / f"temp{i}_label") or f"temp{i}"
                temps[label] = round(t / 1000, 1)

    return {"disks": disks, "mounts": mounts, "nvme_temps": temps}


async def _udisks(action, device):
    if not REMOVABLE.match(device):
        raise ValueError(f"solo se pueden {action} tarjetas SD o USB: {device}")
    out = await run("udisksctl", action, "-b", device, "--no-user-interaction", timeout=30)
    collect.invalidate()
    return out.strip()


async def mount(device):
    out = await _udisks("mount", device)
    if "Mounted" not in out:
        raise RuntimeError(out or "udisks no pudo montar la unidad")
    return out


async def unmount(device):
    out = await _udisks("unmount", device)
    if "Unmounted" not in out:
        raise RuntimeError(out or "udisks no pudo desmontar (¿archivos abiertos?)")
    return out


def set_automount(uuid, enabled):
    cfg = config.load()
    ids = set(cfg["automount"])
    ids.add(uuid) if enabled else ids.discard(uuid)
    cfg["automount"] = sorted(ids)
    config.save(cfg)
    collect.invalidate()


async def automount_all():
    """Monta las particiones marcadas que estén conectadas y sin montar."""
    wanted = set(config.load()["automount"])
    if not wanted:
        return
    for d in await _lsblk():
        for p in d.get("children", []):
            if p.get("uuid") in wanted and not p.get("mountpoint"):
                try:
                    log.info("automontaje: %s", await mount(p["path"]))
                except Exception as e:
                    log.warning("automontaje de %s falló: %s", p.get("path"), e)
