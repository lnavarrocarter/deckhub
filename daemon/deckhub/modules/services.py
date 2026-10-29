"""SteamOS, servicios clave, Decky y flatpaks."""
import asyncio
from pathlib import Path

from ..util import cached, read, run

HOMEBREW = Path.home() / "homebrew"
SYSTEM_UNITS = ["plugin_loader", "sshd", "NetworkManager", "bluetooth"]
USER_UNITS = ["deckhub", "steamos-manager", "pipewire", "gamescope-session"]


def _os_release():
    info = {}
    for line in (read("/etc/os-release") or "").splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            info[k] = v.strip('"')
    return info


async def _unit_state(unit, user=False):
    args = ["systemctl", "--user"] if user else ["systemctl"]
    return (await run(*args, "is-active", unit)).strip() or "unknown"


@cached(30)
async def collect():
    osr = _os_release()
    sys_states = await asyncio.gather(*(_unit_state(u) for u in SYSTEM_UNITS))
    usr_states = await asyncio.gather(*(_unit_state(u, True) for u in USER_UNITS))
    flatpaks = []
    for line in (await run("flatpak", "list", "--app", "--columns=application,name,version")).splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            flatpaks.append({"id": parts[0], "name": parts[1],
                             "version": parts[2] if len(parts) > 2 else ""})
    plugins = sorted(p.name for p in (HOMEBREW / "plugins").glob("*") if p.is_dir())
    return {
        "os": {"name": osr.get("PRETTY_NAME"), "version": osr.get("VERSION_ID"),
               "build": osr.get("BUILD_ID"), "kernel": read("/proc/sys/kernel/osrelease"),
               "model": read("/sys/devices/virtual/dmi/id/board_name")},
        "units": dict(zip(SYSTEM_UNITS, sys_states)) | dict(zip(USER_UNITS, usr_states)),
        "decky": {"version": read(HOMEBREW / "services/.loader.version"), "plugins": plugins},
        "flatpaks": flatpaks,
    }
