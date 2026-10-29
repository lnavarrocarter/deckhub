"""Backend del plugin: puente entre la interfaz de Decky y el daemon DeckHub local."""
import asyncio
import base64
import json
import os
import urllib.error
import urllib.request

import decky

DAEMON = "http://127.0.0.1:8765"
TOKEN_FILE = os.path.join(decky.DECKY_USER_HOME, ".config/deckhub/token")


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
            out.append({"key": item["key"], "appid": item["appid"], "images": images})
        return out

    async def ack_art(self, key, error=None):
        try:
            await asyncio.to_thread(_request, "/api/shortcuts/art/ack", {"key": key, "error": error})
            return True
        except Exception:
            return False

    async def _main(self):
        decky.logger.info("DeckHub plugin cargado")

    async def _unload(self):
        decky.logger.info("DeckHub plugin descargado")
