"""Paquetes Flatpak: listar con tamaño, buscar, instalar y desinstalar."""
import re
import subprocess

from .. import jobs
from ..util import cached, run

APP_ID = re.compile(r"^[A-Za-z0-9_.-]+$")
UNITS = {"bytes": 1, "kB": 1e3, "MB": 1e6, "GB": 1e9, "TB": 1e12}


def _bytes(text):
    m = re.match(r"([\d.,]+)\s*(\w+)", text.replace("\xa0", " "))
    if not m:
        return None
    return int(float(m.group(1).replace(",", ".")) * UNITS.get(m.group(2), 1))


@cached(30)
async def collect():
    out = await run("flatpak", "list", "--app",
                    "--columns=application,name,version,size,installation,origin")
    apps = []
    for line in out.splitlines():
        p = line.split("\t")
        if len(p) >= 6:
            apps.append({"id": p[0], "name": p[1], "version": p[2], "size": _bytes(p[3]),
                         "installation": p[4], "origin": p[5]})
    apps.sort(key=lambda a: a["size"] or 0, reverse=True)
    return {"apps": apps, "total": sum(a["size"] or 0 for a in apps)}


async def search(query):
    out = await run("flatpak", "search", "--columns=application,name,description,version",
                    query, timeout=30)
    results = []
    for line in out.splitlines():
        p = line.split("\t")
        if len(p) >= 2 and APP_ID.match(p[0]):
            results.append({"id": p[0], "name": p[1],
                            "description": p[2] if len(p) > 2 else "",
                            "version": p[3] if len(p) > 3 else ""})
    return results[:30]


def _flatpak(job, args):
    r = subprocess.run(["flatpak", *args, "-y", "--noninteractive"],
                       capture_output=True, text=True, timeout=1800)
    collect.invalidate()
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip()[-400:] or "flatpak falló")


def _check(app_id):
    if not APP_ID.match(app_id or ""):
        raise ValueError(f"id de flatpak no válido: {app_id!r}")
    return app_id


def install(app_id):
    _check(app_id)
    return jobs.start("flatpak", f"Instalar {app_id}", _flatpak, ["install", "flathub", app_id])


def uninstall(app_id):
    _check(app_id)
    return jobs.start("flatpak", f"Desinstalar {app_id}", _flatpak, ["uninstall", app_id])
