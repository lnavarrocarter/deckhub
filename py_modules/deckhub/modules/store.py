"""Tienda: seguimiento de precios de juegos de Steam (lista de deseados o añadidos a
mano), mínimo histórico y alertas que el plugin muestra como notificación.

Solo lectura: nada aquí compra ni toca la cuenta.
"""
import asyncio
import json
import logging
import time
from pathlib import Path

import aiohttp

from .. import config
from . import artwork, steam

log = logging.getLogger("deckhub.store")
DATA = Path.home() / ".config/deckhub/store.json"
STEAM_API = "https://api.steampowered.com"
STORE = "https://store.steampowered.com"
ITAD = "https://api.isthereanydeal.com"
ITAD_STEAM_SHOP = 61
CHECK_EVERY = 6 * 3600
UA = {"User-Agent": "DeckHub/1.0 (Steam Deck price tracker)"}
# Moneda de la tienda -> país, para detectar la región sin preguntar.
CURRENCY_COUNTRY = {"CLP": "CL", "USD": "US", "EUR": "ES", "MXN": "MX", "BRL": "BR", "COP": "CO", "PEN": "PE",
                    "GBP": "GB", "CAD": "CA", "AUD": "AU", "JPY": "JP", "UYU": "UY", "ARS": "AR", "CRC": "CR"}
DECK = {3: "Verificado", 2: "Jugable", 1: "No compatible"}


def _load():
    try:
        d = json.loads(DATA.read_text())
    except (OSError, ValueError):
        d = {}
    d.setdefault("tracked", {})
    d.setdefault("notifications", [])
    return d


def _save(d):
    DATA.parent.mkdir(parents=True, exist_ok=True)
    tmp = DATA.with_suffix(".tmp")
    tmp.write_text(json.dumps(d))
    tmp.replace(DATA)


def _steamid():
    """SteamID64 de la cuenta usada más recientemente en el Deck."""
    try:
        users = steam.parse_vdf((steam.STEAM / "config/loginusers.vdf").read_text(errors="replace")).get("users", {})
    except OSError:
        return None
    recent = [k for k, v in users.items() if isinstance(v, dict) and v.get("MostRecent") == "1"]
    return (recent or list(users) or [None])[0]


async def _json(session, method, url, **kw):
    try:
        async with session.request(method, url, **kw) as r:
            if r.status == 403 and url.startswith(ITAD):
                raise artwork.ArtError("La clave de IsThereAnyDeal no es válida.")
            r.raise_for_status()
            return await r.json(content_type=None)
    except artwork.ArtError:
        raise
    except Exception as e:
        raise RuntimeError(artwork.describe(e).replace("www.steamgriddb.com", url.split("/")[2]))


def _session():
    return aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30), headers=UA)


async def country():
    """País de la tienda: el elegido en Ajustes o el detectado por la moneda de Steam."""
    cfg = config.load()
    if cfg.get("store_country"):
        return cfg["store_country"]
    async with _session() as s:
        d = await _json(s, "GET", f"{STORE}/api/appdetails", params={"appids": "620", "filters": "price_overview"})
    cur = (d.get("620", {}).get("data") or {}).get("price_overview", {}).get("currency", "USD")
    cc = CURRENCY_COUNTRY.get(cur, "US")
    cfg["store_country"] = cc
    config.save(cfg)
    return cc


async def _items(session, appids, cc):
    """Nombre, precio, descuento, reseñas y compatibilidad con Deck, de a 50 juegos."""
    out = {}
    for i in range(0, len(appids), 50):
        req = {"ids": [{"appid": int(a)} for a in appids[i:i + 50]],
               "context": {"language": "spanish", "country_code": cc},
               "data_request": {"include_platforms": True, "include_reviews": True, "include_assets": True}}
        d = await _json(session, "GET", f"{STEAM_API}/IStoreBrowseService/GetItems/v1/",
                        params={"input_json": json.dumps(req)})
        for it in d.get("response", {}).get("store_items", []):
            if not it.get("success") == 1:
                continue
            bp = it.get("best_purchase_option") or {}
            final = int(bp.get("final_price_in_cents") or 0)
            orig = int(bp.get("original_price_in_cents") or final)
            rv = (it.get("reviews") or {}).get("summary_filtered") or {}
            out[it["appid"]] = {
                "name": it.get("name"), "final": final, "initial": orig, "formatted": bp.get("formatted_final_price"),
                "formatted_initial": bp.get("formatted_original_price"),
                "discount": int(bp.get("discount_pct") or 0), "free": bool(it.get("is_free")),
                "discount_end": min([int(x["discount_end_date"]) for x in bp.get("active_discounts", [])
                                     if x.get("discount_end_date")] or [0]) or None,
                "purchasable": bool(bp), "deck": DECK.get((it.get("platforms") or {}).get("steam_deck_compat_category")),
                "reviews": rv.get("review_score_label"), "reviews_pct": rv.get("percent_positive"),
                "url": f"{STORE}/{it.get('store_url_path') or 'app/' + str(it['appid'])}",
            }
    return out


async def _itad_lows(session, appids, cc, key):
    """Mínimo histórico en Steam para la región, según IsThereAnyDeal (si hay clave)."""
    ids = {}
    for a in appids:
        d = await _json(session, "GET", f"{ITAD}/games/lookup/v1", params={"key": key, "appid": a})
        if d.get("found"):
            ids[d["game"]["id"]] = a
    if not ids:
        return {}
    d = await _json(session, "POST", f"{ITAD}/games/storelow/v2",
                    params={"key": key, "country": cc, "shops": ITAD_STEAM_SHOP}, json=list(ids))
    out = {}
    for g in d or []:
        lows = [x for x in g.get("lows", []) if (x.get("shop") or {}).get("id") == ITAD_STEAM_SHOP]
        if lows:
            p = lows[0]["price"]
            out[ids[g["id"]]] = {"amount": round(float(p["amount"]) * 100), "currency": p.get("currency"),
                                 "cut": lows[0].get("cut"), "timestamp": lows[0].get("timestamp")}
    return out


def _notify(d, appid, t, text):
    d["notifications"].append({"id": f"{appid}-{int(time.time())}", "appid": appid, "title": t, "body": text,
                               "time": time.time(), "delivered": False})
    d["notifications"] = d["notifications"][-50:]


def _low(t):
    """Mínimo histórico conocido: el de IsThereAnyDeal o el más bajo que vio DeckHub."""
    lows = [x for x in (t.get("low_seen"), (t.get("itad_low") or {}).get("amount")) if x]
    return min(lows) if lows else None


def _check_alerts(d, appid, t):
    """Alerta una vez por cada nuevo precio que cumple el objetivo o iguala el mínimo."""
    p = t.get("price") or {}
    if not p.get("final") or not p.get("purchasable"):
        return
    final = p["final"]
    low = _low(t)
    reasons = []
    if t.get("target") and final <= t["target"]:
        reasons.append("bajó de tu precio objetivo")
    if t.get("notify_low") and low and final <= low and p.get("discount"):
        reasons.append("está en su mínimo histórico")
    key = f"{final}:{','.join(reasons)}"
    if reasons and t.get("alerted") != key:
        t["alerted"] = key
        _notify(d, appid, f"{t['name']} · {p.get('formatted')}",
                f"{' y '.join(reasons).capitalize()}" + (f" (-{p['discount']}%)" if p.get("discount") else ""))


async def refresh(appids=None):
    d = _load()
    ids = [int(a) for a in (appids or d["tracked"].keys())]
    if not ids:
        return {"checked": 0}
    cc = await country()
    async with _session() as s:
        info = await _items(s, ids, cc)
        key = config.load().get("itad_key", "").strip()
        lows = {}
        if key:
            try:
                lows = await _itad_lows(s, ids, cc, key)
            except Exception as e:
                log.warning("IsThereAnyDeal: %s", e)
    now = time.time()
    for a in ids:
        t = d["tracked"].get(str(a))
        p = info.get(a)
        if not t or not p:
            continue
        t["name"] = p["name"] or t.get("name")
        t["price"] = {**p, "checked": now}
        if p["final"] and p["purchasable"]:
            hist = t.setdefault("history", [])
            if not hist or hist[-1][1] != p["final"]:
                hist.append([int(now), p["final"]])
                del hist[:-200]
            t["low_seen"] = min(t.get("low_seen") or p["final"], p["final"])
        if a in lows:
            t["itad_low"] = lows[a]
        _check_alerts(d, a, t)
    d["last_check"] = now
    d["country"] = cc
    _save(d)
    return {"checked": len(info)}


async def import_wishlist():
    sid = _steamid()
    if not sid:
        raise ValueError("No encontré tu cuenta de Steam en el Deck.")
    async with _session() as s:
        w = await _json(s, "GET", f"{STEAM_API}/IWishlistService/GetWishlist/v1/", params={"steamid": sid})
    items = w.get("response", {}).get("items", [])
    if not items:
        raise ValueError("Tu lista de deseados de Steam está vacía o es privada "
                         "(Steam → Perfil → Privacidad → Detalles de juegos: Público).")
    d = _load()
    new = 0
    for it in items:
        k = str(it["appid"])
        if k not in d["tracked"]:
            d["tracked"][k] = {"name": None, "source": "wishlist", "added": time.time(), "target": None,
                               "notify_low": True}
            new += 1
    _save(d)
    await refresh([it["appid"] for it in items])
    return {"total": len(items), "new": new}


async def search(term):
    cc = await country()
    async with _session() as s:
        d = await _json(s, "GET", f"{STORE}/api/storesearch/", params={"term": term, "l": "spanish", "cc": cc})
    tracked = _load()["tracked"]
    return [{"appid": i["id"], "name": i["name"], "image": i.get("tiny_image"),
             "price": (i.get("price") or {}).get("final"), "currency": (i.get("price") or {}).get("currency"),
             "tracked": str(i["id"]) in tracked} for i in d.get("items", []) if i.get("type") == "app"]


async def track(appid, target=None, notify_low=True):
    d = _load()
    k = str(int(appid))
    t = d["tracked"].setdefault(k, {"name": None, "source": "manual", "added": time.time()})
    t["target"] = int(target) if target not in (None, "") else None
    t["notify_low"] = bool(notify_low)
    t.pop("alerted", None)
    _save(d)
    await refresh([int(appid)])


def untrack(appid):
    d = _load()
    d["tracked"].pop(str(int(appid)), None)
    _save(d)


def collect():
    d = _load()
    items = []
    for k, t in d["tracked"].items():
        p = t.get("price") or {}
        low = _low(t)
        items.append({"appid": int(k), "name": t.get("name") or k, "source": t.get("source"), "target": t.get("target"),
                      "notify_low": t.get("notify_low", True), "price": p, "low": low,
                      "low_source": "IsThereAnyDeal" if t.get("itad_low") and low == t["itad_low"]["amount"] else "DeckHub",
                      "at_low": bool(low and p.get("final") and p["final"] <= low and p.get("discount")),
                      "history": t.get("history", [])[-30:]})
    items.sort(key=lambda i: (-(i["price"].get("discount") or 0), i["name"].lower()))
    cfg = config.load()
    cc = d.get("country") or cfg.get("store_country")
    currency = next((c for c, k in CURRENCY_COUNTRY.items() if k == cc), "USD")
    return {"items": items, "last_check": d.get("last_check"), "country": cc, "currency": currency,
            "itad_key_set": bool(cfg.get("itad_key")), "steamid": _steamid(),
            "notifications": d["notifications"][-20:][::-1]}


def pending_notifications():
    return [n for n in _load()["notifications"] if not n["delivered"]]


def ack_notification(nid):
    d = _load()
    for n in d["notifications"]:
        if n["id"] == nid:
            n["delivered"] = True
    _save(d)


async def check_itad_key(key):
    async with _session() as s:
        await _json(s, "GET", f"{ITAD}/games/lookup/v1", params={"key": key, "appid": 620})


async def loop():
    """Revisa precios cada 6 horas (y poco después de arrancar si toca)."""
    await asyncio.sleep(60)
    while True:
        try:
            if _load()["tracked"] and time.time() - (_load().get("last_check") or 0) >= CHECK_EVERY:
                await refresh()
        except Exception as e:
            log.warning("revisión de precios falló: %s", e)
        await asyncio.sleep(900)
