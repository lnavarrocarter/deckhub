"""Helpers compartidos: lectura de sysfs, hwmon, comandos y caché."""
import asyncio
import time
from pathlib import Path


def read(path, default=None, cast=str):
    try:
        return cast(Path(path).read_text().strip())
    except (OSError, ValueError):
        return default


def hwmon(name):
    """Devuelve la carpeta hwmon con ese nombre (el índice cambia entre arranques)."""
    for h in Path("/sys/class/hwmon").glob("hwmon*"):
        if read(h / "name") == name:
            return h
    return None


def hwmon_value(name, attr, scale=1.0):
    h = hwmon(name)
    if h is None:
        return None
    v = read(h / attr, cast=int)
    return None if v is None else round(v / scale, 2)


async def run(*cmd, timeout=5):
    """Ejecuta un comando y devuelve stdout (o '' si falla)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL
        )
        out, _ = await asyncio.wait_for(proc.communicate(), timeout)
        return out.decode(errors="replace")
    except (OSError, asyncio.TimeoutError):
        return ""


def cached(ttl):
    """Cachea el resultado de una corrutina sin argumentos durante `ttl` segundos."""
    def deco(fn):
        state = {"t": 0.0, "v": None, "lock": None}

        async def wrapper():
            if state["lock"] is None:
                state["lock"] = asyncio.Lock()
            async with state["lock"]:
                if time.monotonic() - state["t"] > ttl:
                    state["v"] = await fn()
                    state["t"] = time.monotonic()
                return state["v"]

        def invalidate():
            state["t"] = 0.0

        wrapper.invalidate = invalidate
        return wrapper
    return deco
