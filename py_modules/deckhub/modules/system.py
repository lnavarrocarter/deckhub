"""CPU, GPU, memoria, temperaturas, ventilador, batería, TDP y pantalla."""
import time
from pathlib import Path

import psutil

from ..util import hwmon, hwmon_value, read

BAT = Path("/sys/class/power_supply/BAT1")
GPU = Path("/sys/class/drm/card0/device")

# Primera llamada para que cpu_percent devuelva valores reales en adelante.
psutil.cpu_percent(percpu=True)


def _gpu_clock():
    for line in (read(GPU / "pp_dpm_sclk") or "").splitlines():
        if line.endswith("*"):
            return int(line.split()[1].rstrip("Mhz"))
    return None


def _battery():
    if not BAT.exists():
        return None
    volt = read(BAT / "voltage_now", cast=int)
    curr = read(BAT / "current_now", cast=int)
    full = read(BAT / "charge_full", cast=int)
    design = read(BAT / "charge_full_design", cast=int)
    watts = round(volt * curr / 1e12, 2) if volt and curr is not None else None
    return {
        "percent": read(BAT / "capacity", cast=int),
        "status": read(BAT / "status"),
        "watts": watts,
        "voltage": round(volt / 1e6, 2) if volt else None,
        "cycles": read(BAT / "cycle_count", cast=int),
        "health": round(full * 100 / design, 1) if full and design else None,
    }


def _backlight():
    bl = next(Path("/sys/class/backlight").glob("*"), None)
    if bl is None:
        return None
    cur, mx = read(bl / "brightness", cast=int), read(bl / "max_brightness", cast=int)
    return round(cur * 100 / mx) if cur is not None and mx else None


async def collect():
    freq = psutil.cpu_freq()
    mem, swap = psutil.virtual_memory(), psutil.swap_memory()
    gpu_hw = hwmon("amdgpu")
    tdp = None
    if gpu_hw is not None:
        tdp = {
            "watts": read(gpu_hw / "power1_cap", cast=int),
            "max": read(gpu_hw / "power1_cap_max", cast=int),
        }
        tdp = {k: v / 1e6 if v else None for k, v in tdp.items()}
    return {
        "cpu": {
            "percent": psutil.cpu_percent(),
            "per_core": psutil.cpu_percent(percpu=True),
            "mhz": round(freq.current) if freq else None,
            "max_mhz": round(freq.max) if freq else None,
            "temp": hwmon_value("k10temp", "temp1_input", 1000),
            "load": [round(x, 2) for x in psutil.getloadavg()],
        },
        "gpu": {
            "percent": read(GPU / "gpu_busy_percent", cast=int),
            "mhz": _gpu_clock(),
            "temp": hwmon_value("amdgpu", "temp1_input", 1000),
            "watts": hwmon_value("amdgpu", "power1_average", 1e6),
            "perf_level": read(GPU / "power_dpm_force_performance_level"),
        },
        "tdp": tdp,
        "memory": {
            "total": mem.total, "used": mem.total - mem.available, "percent": mem.percent,
            "swap_total": swap.total, "swap_used": swap.used,
        },
        "fan_rpm": hwmon_value("steamdeck_hwmon", "fan1_input"),
        "board_temp": hwmon_value("acpitz", "temp1_input", 1000),
        "battery": _battery(),
        "brightness": _backlight(),
        "uptime": int(time.time() - psutil.boot_time()),
    }
