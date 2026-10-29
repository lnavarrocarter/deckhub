"""Genera assets/store.png (imagen de la tienda de Decky y del README). Uso: python scripts/make-store-image.py"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
W, H = 1280, 640
img = Image.new("RGB", (W, H), "#14171c")
d = ImageDraw.Draw(img)

# Degradado diagonal suave.
for y in range(H):
    c = int(20 + 18 * y / H)
    d.line([(0, y), (W, y)], fill=(c, c + 4, c + 14))


def font(size, bold=False):
    for name in (["segoeuib.ttf", "DejaVuSans-Bold.ttf", "arialbd.ttf"] if bold else ["segoeui.ttf", "DejaVuSans.ttf", "arial.ttf"]):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


accent = (26, 159, 255)
d.polygon([(110, 250), (160, 200), (210, 250), (160, 300)], fill=accent)
d.text((240, 190), "DeckHub", font=font(110, True), fill="#e6e9ed")
d.text((112, 340), "System dashboard & retro hub for Steam Deck", font=font(44), fill="#8b95a1")

chips = ["Library & artwork", "Emulators", "Saves & cheats", "Themes", "Deals & alerts", "Web dashboard"]
x, y = 112, 440
for c in chips:
    f = font(30)
    w = d.textlength(c, font=f) + 40
    if x + w > W - 100:
        x, y = 112, y + 70
    d.rounded_rectangle([x, y, x + w, y + 52], radius=26, outline=accent, width=3)
    d.text((x + 20, y + 9), c, font=f, fill="#e6e9ed")
    x += w + 18

out = ROOT / "assets/store.png"
out.parent.mkdir(exist_ok=True)
img.save(out, optimize=True)
print(out)
