"""Empaqueta el plugin como lo instala Decky: out/DeckHub-<versión>.zip con una carpeta DeckHub/.

Requiere haber compilado antes el frontend (pnpm build). Uso: python scripts/build-zip.py
"""
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = ["plugin.json", "package.json", "main.py", "LICENSE", "README.md", "dist/index.js"]
TREES = ["py_modules"]


def main():
    version = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))["version"]
    if not (ROOT / "dist/index.js").exists():
        raise SystemExit("falta dist/index.js: ejecuta antes `pnpm build`")
    out = ROOT / "out" / f"DeckHub-{version}.zip"
    out.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name in FILES:
            z.write(ROOT / name, f"DeckHub/{name}")
        for tree in TREES:
            for p in sorted((ROOT / tree).rglob("*")):
                if p.is_file() and "__pycache__" not in p.parts:
                    z.write(p, f"DeckHub/{p.relative_to(ROOT).as_posix()}")
    # Copia con nombre fijo: releases/latest/download/DeckHub.zip apunta siempre a la última.
    latest = out.with_name("DeckHub.zip")
    latest.write_bytes(out.read_bytes())
    print(out)


if __name__ == "__main__":
    main()
