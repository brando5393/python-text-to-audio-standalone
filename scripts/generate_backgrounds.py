"""Generates a subtle background texture for each theme: a faint paper-grain noise plus
a large, very low-opacity watermark of the app's own icon motif (book + waveform),
bleeding off the bottom-right corner. Meant to be barely noticeable -- texture and
brand echo, not a visual centerpiece.

Run manually when these need to change: `poetry run python scripts/generate_backgrounds.py`
Requires Pillow (dev dependency only -- not needed at runtime).
"""

import os

from PIL import Image, ImageDraw

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "..", "assets")

CANVAS_SIZE = (1400, 900)

THEMES = {
    "background-light.png": {"bg": (242, 232, 217), "ink": (111, 78, 55), "noise_amount": 6},
    "background-dark.png": {"bg": (36, 27, 20), "ink": (242, 232, 217), "noise_amount": 5},
}


def _paper_grain(size, base_color, amount):
    """A faint per-pixel noise texture tinted to the theme's background color."""
    noise = Image.effect_noise(size, 24).convert("L")
    base = Image.new("RGB", size, base_color)
    grain = Image.blend(base, Image.merge("RGB", (noise, noise, noise)), amount / 255 * 4)
    return Image.blend(base, grain, 0.5)


def _watermark_icon(size, ink_color, alpha):
    """A large, faint version of the book+waveform icon motif, bottom-right, bleeding
    off the canvas edge."""
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    icon_size = int(size[1] * 0.85)
    cx = size[0] - int(icon_size * 0.32)
    cy = size[1] - int(icon_size * 0.22)

    spine_x = cx
    top_y, bottom_y = cy - int(icon_size * 0.05), cy + int(icon_size * 0.12)
    half_w = int(icon_size * 0.32)
    fill = (*ink_color, alpha)
    draw.polygon(
        [(spine_x, top_y - 15), (spine_x - half_w, top_y + 30), (spine_x - half_w, bottom_y),
         (spine_x, bottom_y - 15)],
        fill=fill,
    )
    draw.polygon(
        [(spine_x, top_y - 15), (spine_x + half_w, top_y + 30), (spine_x + half_w, bottom_y),
         (spine_x, bottom_y - 15)],
        fill=fill,
    )

    bar_widths = [int(icon_size * 0.03)] * 5
    bar_heights = [icon_size * f for f in (0.07, 0.14, 0.22, 0.14, 0.07)]
    gap = int(icon_size * 0.02)
    total_w = sum(bar_widths) + gap * (len(bar_widths) - 1)
    x = spine_x - total_w // 2
    base_y = top_y - 15
    for w, h in zip(bar_widths, bar_heights):
        draw.rounded_rectangle([x, base_y - h, x + w, base_y], radius=w * 0.3, fill=fill)
        x += w + gap

    return layer


def generate(filename, bg, ink, noise_amount):
    base = _paper_grain(CANVAS_SIZE, bg, noise_amount).convert("RGBA")
    watermark = _watermark_icon(CANVAS_SIZE, ink, alpha=14)
    combined = Image.alpha_composite(base, watermark)
    combined.convert("RGB").save(os.path.join(ASSETS_DIR, filename))


def main():
    os.makedirs(ASSETS_DIR, exist_ok=True)
    for filename, params in THEMES.items():
        generate(filename, params["bg"], params["ink"], params["noise_amount"])
        print("wrote", filename)


if __name__ == "__main__":
    main()
