"""Backend del plugin: instala el daemon DeckHub como servicio de usuario y hace de
puente entre la interfaz de Decky y ese daemon."""
import asyncio
import base64
import json
import os
import re
import subprocess
import urllib.error
import urllib.request

import decky

DAEMON = "http://127.0.0.1:8765"
TOKEN_FILE = os.path.join(decky.DECKY_USER_HOME, ".config/deckhub/token")
# El daemon viaja dentro del plugin, en py_modules/deckhub.
PKG_DIR = os.path.join(decky.DECKY_PLUGIN_DIR, "py_modules")
UNIT_NAME = "deckhub.service"
UNIT_FILE = os.path.join(decky.DECKY_USER_HOME, ".config/systemd/user", UNIT_NAME)
UNIT = f"""[Unit]
Description=DeckHub - supervisor del Steam Deck (instalado por el plugin de Decky)
After=network-online.target

[Service]
Type=simple
WorkingDirectory={PKG_DIR}
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=/usr/bin/python3 -m deckhub --port 8765
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
"""


def _systemctl(*args):
    # Decky no pasa la sesión del usuario al backend: se indica a mano para
    # hablar con su systemd --user (el mismo contexto que udisks y flatpak).
    uid = os.getuid()
    env = {**os.environ, "XDG_RUNTIME_DIR": f"/run/user/{uid}",
           "DBUS_SESSION_BUS_ADDRESS": f"unix:path=/run/user/{uid}/bus"}
    r = subprocess.run(["systemctl", "--user", *args], env=env, capture_output=True, text=True, timeout=30)
    if r.returncode != 0 and args[0] not in ("is-active",):
        decky.logger.warning("systemctl %s: %s", " ".join(args), r.stderr.strip())
    return r


def _bundled_version():
    with open(os.path.join(PKG_DIR, "deckhub/__init__.py")) as f:
        return re.search(r'VERSION = "([^"]+)"', f.read()).group(1)


def _running_version():
    try:
        with urllib.request.urlopen(DAEMON + "/api", timeout=10) as r:
            return json.load(r).get("version")
    except Exception:
        return None


def _ensure_daemon():
    """Escribe la unidad si cambió y (re)arranca el daemon si no es la versión incluida."""
    changed = True
    try:
        with open(UNIT_FILE) as f:
            changed = f.read() != UNIT
    except OSError:
        pass
    if changed:
        os.makedirs(os.path.dirname(UNIT_FILE), exist_ok=True)
        with open(UNIT_FILE, "w") as f:
            f.write(UNIT)
        _systemctl("daemon-reload")
    # Siempre: al actualizar, Decky ejecuta _uninstall de la versión anterior (que lo
    # deshabilita) y la unidad queda igual, así que no basta con habilitar si cambió.
    _systemctl("enable", UNIT_NAME)
    if changed or _running_version() != _bundled_version():
        _systemctl("restart", UNIT_NAME)
        decky.logger.info("daemon DeckHub %s (re)iniciado desde %s", _bundled_version(), PKG_DIR)
    else:
        _systemctl("start", UNIT_NAME)


def _token():
    try:
        with open(TOKEN_FILE) as f:
            return f.read().strip()
    except OSError:
        return ""


def _request(path, body=None):
    req = urllib.request.Request(DAEMON + path, headers={"X-DeckHub-Token": _token()})
    if body is not None:
        req.data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=35) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        try:
            return json.load(e)
        except ValueError:
            return {"error": f"HTTP {e.code}"}


class Plugin:
    async def get_status(self):
        try:
            data = await asyncio.to_thread(_request, "/api")
            return {"ok": True, "data": data}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    async def get_dashboard_url(self):
        # IP de la red local para abrir el panel web desde otro equipo.
        try:
            net = await asyncio.to_thread(_request, "/api/network")
            for iface in net.get("interfaces", []):
                if iface.get("up") and iface.get("ipv4"):
                    return f"http://{iface['ipv4'][0]}:8765"
        except Exception:
            pass
        return DAEMON

    async def set_mounted(self, device, mounted):
        path = "/api/drives/mount" if mounted else "/api/drives/unmount"
        try:
            r = await asyncio.to_thread(_request, path, {"device": device})
        except Exception as e:
            return {"ok": False, "error": str(e)}
        return {"ok": "error" not in r, "error": r.get("error")}

    async def get_pending_shortcuts(self):
        try:
            r = await asyncio.to_thread(_request, "/api/shortcuts/pending")
            return r.get("data", [])
        except Exception:
            return []  # daemon caído: se reintenta en el siguiente ciclo

    async def ack_shortcut(self, key, appid=None, removed=False, error=None):
        body = {"key": key, "appid": appid, "removed": removed, "error": error}
        try:
            await asyncio.to_thread(_request, "/api/shortcuts/ack", body)
            return True
        except Exception:
            return False

    async def get_pending_art(self):
        """Portadas listas, con cada imagen en base64 para SetCustomArtworkForApp."""
        try:
            r = await asyncio.to_thread(_request, "/api/shortcuts/art/pending")
        except Exception:
            return []
        out = []
        for item in r.get("data", []):
            images = []
            for img in item["images"].values():
                try:
                    with open(img["file"], "rb") as f:
                        data = base64.b64encode(f.read()).decode()
                except OSError:
                    continue
                images.append({"asset": img["asset"], "ext": img["ext"], "data": data})
            out.append({"key": item["key"], "appid": item["appid"], "images": images,
                        "reset": item.get("reset", [])})
        return out

    async def ack_art(self, key, error=None):
        try:
            await asyncio.to_thread(_request, "/api/shortcuts/art/ack", {"key": key, "error": error})
            return True
        except Exception:
            return False

    async def report_store_userdata(self, data):
        try:
            r = await asyncio.to_thread(_request, "/api/store/userdata", data)
            return r.get("data", 0)
        except Exception:
            return 0

    async def report_downloads(self, items):
        try:
            await asyncio.to_thread(_request, "/api/steam/downloads", {"items": items})
            return True
        except Exception:
            return False

    async def get_store_notifications(self):
        try:
            r = await asyncio.to_thread(_request, "/api/store/notifications")
            return r.get("data", [])
        except Exception:
            return []

    async def ack_store_notification(self, nid):
        try:
            await asyncio.to_thread(_request, "/api/store/notifications/ack", {"id": nid})
            return True
        except Exception:
            return False

    async def get_pending_actions(self):
        try:
            r = await asyncio.to_thread(_request, "/api/decky/actions/pending")
            return r.get("data", [])
        except Exception:
            return []

    async def ack_action(self, action_id):
        try:
            await asyncio.to_thread(_request, "/api/decky/actions/ack", {"id": action_id})
            return True
        except Exception:
            return False

    async def report_library(self, apps, compat_tools=None):
        try:
            await asyncio.to_thread(_request, "/api/steam/playtime", {"apps": apps, "compat_tools": compat_tools or []})
            return True
        except Exception:
            return False

    async def get_update(self):
        """¿Hay una versión nueva de DeckHub en GitHub Releases?"""
        try:
            return (await asyncio.to_thread(_request, "/api/updates")).get("data")
        except Exception:
            return None

    async def install_update(self):
        try:
            r = await asyncio.to_thread(_request, "/api/updates/install", {})
        except Exception as e:
            return {"ok": False, "error": str(e)}
        return {"ok": "error" not in r, "error": r.get("error")}

    async def get_perf(self):
        """Resumen de los ajustes de memoria para el menú rápido."""
        try:
            d = (await asyncio.to_thread(_request, "/api/perf")).get("data") or {}
        except Exception:
            return None
        tun = [s for s in d.get("settings", []) if s.get("tunable")]
        return {"done": sum(1 for s in tun if s["optimized"]), "total": len(tun),
                "pending": [s["id"] for s in tun if not s["optimized"]],
                "ready": bool(d.get("helper", {}).get("allowed") and d["helper"].get("up_to_date")),
                "swap_gb": round((d.get("swapfile") or {}).get("size", 0) / 1024 ** 3)}

    async def apply_perf(self, ids):
        try:
            r = await asyncio.to_thread(_request, "/api/perf/apply", {"ids": ids, "persist": True})
        except Exception as e:
            return {"ok": False, "error": str(e)}
        return {"ok": "error" not in r, "error": r.get("error")}

    async def get_language(self):
        """Idioma del panel (el elegido en Ajustes o el de Steam): «es», «en»…"""
        try:
            with urllib.request.urlopen(DAEMON + "/api/i18n", timeout=5) as r:
                return json.load(r).get("lang")
        except Exception:
            return None

    async def get_access(self):
        """URL del panel y token, para entrar desde el PC o el móvil sin SSH."""
        try:
            r = await asyncio.to_thread(_request, "/api/settings")
            lan = r.get("data", {}).get("lan_access", True)
        except Exception:
            lan = None  # daemon caído
        return {"url": await self.get_dashboard_url(), "token": _token(), "lan_access": lan}

    async def set_lan_access(self, enabled):
        """Abre o cierra el puerto 8765 a la red; el daemon se reinicia en unos segundos."""
        try:
            r = await asyncio.to_thread(_request, "/api/settings", {"lan_access": bool(enabled)})
        except Exception as e:
            return {"ok": False, "error": str(e)}
        return {"ok": "error" not in r, "error": r.get("error")}

    async def restart_daemon(self):
        r = await asyncio.to_thread(_systemctl, "restart", UNIT_NAME)
        return {"ok": r.returncode == 0, "error": r.stderr.strip() or None}

    async def _main(self):
        try:
            await asyncio.to_thread(_ensure_daemon)
        except Exception:
            decky.logger.exception("no pude preparar el daemon")
        decky.logger.info("DeckHub plugin cargado")

    async def _unload(self):
        # El daemon sigue activo: el panel web funciona aunque Decky se reinicie.
        decky.logger.info("DeckHub plugin descargado")

    async def _uninstall(self):
        # Se quita el servicio; configuración, portadas y copias de partidas se conservan.
        await asyncio.to_thread(_systemctl, "disable", "--now", UNIT_NAME)
        try:
            os.remove(UNIT_FILE)
        except OSError:
            pass
        await asyncio.to_thread(_systemctl, "daemon-reload")
        decky.logger.info("DeckHub desinstalado (datos en ~/.config/deckhub y ~/DeckHub conservados)")
