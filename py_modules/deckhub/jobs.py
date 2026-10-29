"""Tareas largas (copias, movimientos, flatpak) en segundo plano con progreso."""
import asyncio
import itertools
import logging
import time

log = logging.getLogger("deckhub.jobs")
JOBS = {}
_ids = itertools.count(1)
KEEP = 50  # tareas terminadas que se recuerdan


def start(kind, label, fn, *args):
    """Ejecuta fn(job, *args) en un hilo. fn puede actualizar job['done'] / job['total']."""
    job = {"id": next(_ids), "kind": kind, "label": label, "status": "running",
           "done": 0, "total": None, "error": None, "started": time.time(), "ended": None}
    JOBS[job["id"]] = job

    async def runner():
        try:
            await asyncio.to_thread(fn, job, *args)
            job["status"] = "done"
        except Exception as e:
            log.warning("tarea %s (%s) falló: %s", job["id"], label, e)
            job["status"], job["error"] = "error", str(e)
        job["ended"] = time.time()
        finished = [j for j in JOBS.values() if j["status"] != "running"]
        for old in sorted(finished, key=lambda j: j["id"])[:-KEEP]:
            JOBS.pop(old["id"], None)

    asyncio.get_running_loop().create_task(runner())
    return job


def listing():
    return sorted(JOBS.values(), key=lambda j: j["id"], reverse=True)
