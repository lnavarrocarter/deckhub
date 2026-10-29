"""Idioma del panel: el elegido en Ajustes o, en automático, el de Steam en el Deck.

El código y los textos base están en español; cada idioma extra es un JSON en
web/i18n/<código>.json con «texto en español» → «traducción» (las partes dinámicas
se marcan con {}). Para añadir un idioma basta con crear su archivo.
"""
import json
import re
from pathlib import Path

from . import config

I18N_DIR = Path(__file__).parent / "web/i18n"
REGISTRY = Path.home() / ".steam/registry.vdf"
# Idioma de Steam -> código del panel. Los que no tienen traducción caen en inglés.
STEAM_LANGS = {"spanish": "es", "latam": "es", "english": "en", "brazilian": "pt", "portuguese": "pt",
               "french": "fr", "german": "de", "italian": "it"}


def available():
    langs = [{"code": "es", "name": "Español"}]
    for f in sorted(I18N_DIR.glob("*.json")):
        try:
            langs.append({"code": f.stem, "name": json.loads(f.read_text(encoding="utf-8")).get("_language", f.stem)})
        except (OSError, ValueError):
            continue
    return langs


def steam_language():
    try:
        m = re.search(r'"language"\s+"([^"]+)"', REGISTRY.read_text(errors="replace"), re.I)
    except OSError:
        return None
    return m.group(1).lower() if m else None


def resolve():
    choice = config.load().get("ui_lang", "auto")
    codes = {l["code"] for l in available()}
    if choice != "auto" and choice in codes:
        lang = choice
    else:
        lang = STEAM_LANGS.get(steam_language() or "", "en")
        if lang not in codes:
            lang = "en"
    return {"choice": choice, "lang": lang, "steam_language": steam_language(), "available": available()}


def info():
    r = resolve()
    dict_ = {}
    if r["lang"] != "es":
        try:
            dict_ = json.loads((I18N_DIR / f"{r['lang']}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    return {**r, "dict": dict_}
