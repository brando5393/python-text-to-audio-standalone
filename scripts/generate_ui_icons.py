"""Generates small in-app icons (Conversions Library row icons) in the Talebrew palette.

Run manually when these need to change: `poetry run python scripts/generate_ui_icons.py`
Requires Pillow (dev dependency only -- not needed at runtime; the app loads the
resulting PNGs via Tk's native PhotoImage support, no PIL import needed there).
"""

import os

from PIL import Image, ImageDraw

ICONS_DIR = os.path.join(os.path.dirname(__file__), "..", "assets", "icons")

ESPRESSO = (111, 78, 55, 255)
CARAMEL = (169, 113, 66, 255)
HONEY = (201, 147, 47, 255)

SUPERSAMPLE = 8
FINAL_SIZE = 20


def _canvas():
    size = FINAL_SIZE * SUPERSAMPLE
    return Image.new("RGBA", (size, size), (0, 0, 0, 0)), size


def _finish(img, path):
    img.resize((FINAL_SIZE, FINAL_SIZE), Image.LANCZOS).save(path)


def draw_folder():
    img, s = _canvas()
    draw = ImageDraw.Draw(img)
    m = int(s * 0.08)
    tab_h = int(s * 0.14)
    body_top = m + tab_h
    draw.rounded_rectangle([m, m, m + s * 0.35, body_top + int(s * 0.04)], radius=s * 0.03, fill=ESPRESSO)
    draw.rounded_rectangle([m, body_top, s - m, s - m], radius=s * 0.05, fill=ESPRESSO)
    _finish(img, os.path.join(ICONS_DIR, "folder.png"))


def draw_audio_file():
    img, s = _canvas()
    draw = ImageDraw.Draw(img)
    # A little equalizer/waveform mark, echoing the app's own icon motif.
    bar_w = s * 0.14
    gap = s * 0.08
    heights = [0.35, 0.65, 0.9, 0.55, 0.3]
    colors = [HONEY, CARAMEL, HONEY, CARAMEL, HONEY]
    total_w = bar_w * len(heights) + gap * (len(heights) - 1)
    x = (s - total_w) / 2
    base_y = s * 0.85
    for h, color in zip(heights, colors):
        bar_h = s * 0.8 * h
        draw.rounded_rectangle([x, base_y - bar_h, x + bar_w, base_y], radius=bar_w * 0.3, fill=color)
        x += bar_w + gap
    _finish(img, os.path.join(ICONS_DIR, "audio.png"))


def main():
    os.makedirs(ICONS_DIR, exist_ok=True)
    draw_folder()
    draw_audio_file()
    print("Wrote assets/icons/folder.png, assets/icons/audio.png")


if __name__ == "__main__":
    main()
