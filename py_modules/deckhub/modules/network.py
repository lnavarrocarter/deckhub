"""WiFi, interfaces, tráfico y Bluetooth."""
import socket

import psutil

from ..util import cached, run


@cached(10)
async def _wifi():
    # nmcli escapa ':' como '\:' en modo -t; los SSID con ':' son raros, se acepta.
    out = await run("nmcli", "-t", "-f", "ACTIVE,SSID,SIGNAL,FREQ,RATE,SECURITY", "dev", "wifi")
    for line in out.splitlines():
        parts = line.split(":")
        if parts and parts[0] == "yes" and len(parts) >= 6:
            return {"ssid": parts[1], "signal": int(parts[2] or 0), "freq": parts[3],
                    "rate": parts[4], "security": parts[5]}
    return None


@cached(15)
async def _bluetooth():
    out = await run("bluetoothctl", "show")
    if not out:
        return None
    powered = "Powered: yes" in out
    devices = []
    if powered:
        for line in (await run("bluetoothctl", "devices", "Connected")).splitlines():
            parts = line.split(" ", 2)
            if len(parts) == 3:
                devices.append({"mac": parts[1], "name": parts[2]})
    return {"powered": powered, "connected": devices}


async def collect():
    stats, io = psutil.net_if_stats(), psutil.net_io_counters(pernic=True)
    interfaces = []
    for name, addrs in psutil.net_if_addrs().items():
        if name == "lo":
            continue
        ipv4 = [a.address for a in addrs if a.family == socket.AF_INET]
        st, c = stats.get(name), io.get(name)
        interfaces.append({
            "name": name, "up": bool(st and st.isup), "ipv4": ipv4,
            "rx": c.bytes_recv if c else 0, "tx": c.bytes_sent if c else 0,
        })
    return {
        "hostname": socket.gethostname(),
        "interfaces": interfaces,
        "wifi": await _wifi(),
        "bluetooth": await _bluetooth(),
    }
