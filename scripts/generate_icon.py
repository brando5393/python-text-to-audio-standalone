"""Generates the app icon/logo: an open book with a rising soundwave, in the
coffee-house palette. Concept chosen after reviewing three options -- this one
reads clearly as "audiobook" and holds up down to 16px.

Run manually when the icon needs to change: `poetry run python scripts/generate_icon.py`
Requires Pillow (dev dependency only -- not needed at runtime).
"""

import os

from PIL import Image, ImageDraw

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "..", "assets")

ESPRESSO = (111, 78, 55, 255)
ESPRESSO_DARK = (74, 51, 34, 255)
CREAM = (247, 240, 227, 255)
CARAMEL = (169, 113, 66, 255)
HONEY = (201, 147, 47, 255)

SIZE = 1024


def draw_icon():
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = 24
    draw.ellipse([margin, margin, SIZE - margin, SIZE - margin], fill=ESPRESSO)
    draw.ellipse([margin, margin, SIZE - margin, SIZE - margin], outline=ESPRESSO_DARK, width=14)

    # Open book: two trapezoids meeting at a spine, curving slightly like open pages.
    spine_x = SIZE // 2
    top_y, bottom_y = 600, 760
    draw.polygon(
        [(spine_x, top_y - 20), (300, top_y + 40), (300, bottom_y), (spine_x, bottom_y - 20)], fill=CREAM
    )
    draw.polygon(
        [(spine_x, top_y - 20), (724, top_y + 40), (724, bottom_y), (spine_x, bottom_y - 20)], fill=CREAM
    )
    draw.line([(spine_x, top_y - 20), (spine_x, bottom_y - 20)], fill=CARAMEL, width=8)

    # Waveform / equalizer bars rising from the spine (stands in for audio).
    bar_widths = [36, 60, 92, 60, 36]
    bar_heights = [80, 160, 260, 160, 80]
    colors = [HONEY, CARAMEL, HONEY, CARAMEL, HONEY]
    total_w = sum(bar_widths) + (len(bar_widths) - 1) * 20
    x = spine_x - total_w // 2
    base_y = top_y - 20
    for w, h, color in zip(bar_widths, bar_heights, colors):
        draw.rounded_rectangle([x, base_y - h, x + w, base_y], radius=16, fill=color)
        x += w + 20

    return img


def save_ico(img, path):
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img.save(path, format="ICO", sizes=sizes)


def main():
    os.makedirs(ASSETS_DIR, exist_ok=True)
    icon = draw_icon()
    icon.resize((512, 512), Image.LANCZOS).save(os.path.join(ASSETS_DIR, "logo.png"))
    save_ico(icon, os.path.join(ASSETS_DIR, "icon.ico"))
    icon.resize((256, 256), Image.LANCZOS).save(os.path.join(ASSETS_DIR, "icon-256.png"))
    print("Wrote assets/logo.png, assets/icon.ico, assets/icon-256.png")


if __name__ == "__main__":
    main()
