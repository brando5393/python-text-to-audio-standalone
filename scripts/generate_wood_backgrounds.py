"""Regenerates the app's decorative background images (assets/background-light.png,
assets/background-dark.png) and the website's background textures (docs/assets/
wood-*.webp) with a subtle wood-grain look -- built entirely from colors already in the
app's own palette (main.py's ttk.Theme() call), no new hues introduced.

The app's two background images aren't flat: each already carries a faint logo
watermark in the bottom-right, baked in as a per-pixel tint over the flat base color.
This script extracts that tint as a delta (original_pixel - base_color) and reapplies
it unchanged on top of the new wood-grain texture, so the watermark's position and
shape are untouched -- only the texture underneath it changes.

Run manually when the theme palette changes:
    poetry run python scripts/generate_wood_backgrounds.py
"""

import os

import numpy as np
from PIL import Image

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "..", "assets")
DOCS_ASSETS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs", "assets")

# Same coffeehouse palette as main.py's ttk.Theme() call -- no colors outside this set.
CREAM = (242, 232, 217)       # #f2e8d9
DARK_ROAST = (36, 27, 20)     # #241b14
ESPRESSO = (111, 78, 55)      # #6f4e37
CARAMEL = (169, 113, 66)      # #a97142


def _value_noise_1d(length, rng, octaves):
    """Smooth 1D noise via linear interpolation between random control points at a
    few scales -- irregular, unlike a clean sine wave, which is what makes the result
    below read as organic wood grain instead of a mechanical ripple pattern."""
    result = np.zeros(length)
    for scale, weight in octaves:
        n_points = max(2, length // scale)
        control = rng.uniform(-1, 1, n_points)
        xp = np.linspace(0, length - 1, n_points)
        result += weight * np.interp(np.arange(length), xp, control)
    return result


def _wood_grain(size, base, grain_color, seed):
    """A wood-grain field: irregular, mostly-horizontal streaks (real wood grain runs
    along the board, not in a mechanical diagonal ripple) built from smooth 1D noise
    per row plus fine fibrous noise, blended between `base` and `grain_color` -- both
    already palette colors, so this only ever mixes tones that already exist in the
    app, never introduces a new one."""
    width, height = size
    rng = np.random.default_rng(seed)

    # Each row's grain "centerline" wanders slowly and irregularly along its length --
    # this per-row horizontal profile is what gives long streaks their natural waviness.
    row_offsets = _value_noise_1d(height, rng, octaves=[(9, 0.6), (40, 0.9), (140, 0.5)])

    y = np.arange(height).reshape(-1, 1).astype(np.float64)
    x = np.arange(width).reshape(1, -1).astype(np.float64)
    wander = row_offsets.reshape(-1, 1) * 14  # px of horizontal drift per row

    # Streak bands: mostly a function of y (+ a little x, for very gentle diagonal
    # bias real wood boards often have), with irregular spacing from the row wander.
    rings = np.sin((y + wander) / 5.5 + x * 0.006)
    rings += 0.5 * np.sin((y + wander) / 2.1 + x * 0.003 + 2.3)
    rings = (rings - rings.min()) / (rings.max() - rings.min())  # 0..1

    # Fine fibrous noise, smoothed slightly by averaging a couple of offset copies.
    noise = rng.random((height, width))
    noise = (noise + np.roll(noise, 1, axis=0) + np.roll(noise, 1, axis=1)) / 3.0

    grain = np.clip(0.75 * rings + 0.25 * noise, 0, 1)

    # Plank seams: a few faint vertical lines suggesting separate boards in a table.
    seam_mask = np.zeros((1, width))
    seam_spacing = width / 4.3
    for i in range(5):
        center = int(seam_spacing * i + rng.uniform(-10, 10))
        for offset in (-1, 0, 1):
            col = center + offset
            if 0 <= col < width:
                seam_mask[0, col] = 0.35 * (1 - abs(offset) * 0.5)
    grain = np.clip(grain + seam_mask, 0, 1)

    # Blend base -> grain_color using `grain` as the mix factor, kept subtle (max ~18%
    # toward grain_color) so it reads as texture, not a color change.
    strength = 0.18
    out = np.empty((height, width, 3), dtype=np.float64)
    for c in range(3):
        out[:, :, c] = base[c] + (grain_color[c] - base[c]) * grain * strength
    return out


def _apply_to_existing(filename, base_color, grain_color, seed):
    path = os.path.join(ASSETS_DIR, filename)
    original = np.asarray(Image.open(path).convert("RGB"), dtype=np.float64)
    base_arr = np.array(base_color, dtype=np.float64)
    delta = original - base_arr  # captures the existing watermark logo tint

    wood = _wood_grain((original.shape[1], original.shape[0]), base_color, grain_color, seed)
    result = np.clip(wood + delta, 0, 255).astype(np.uint8)
    Image.fromarray(result, "RGB").save(path)


def _make_site_tile(filename, base_color, grain_color, seed, size=512):
    wood = np.clip(_wood_grain((size, size), base_color, grain_color, seed), 0, 255).astype(np.uint8)
    Image.fromarray(wood, "RGB").save(os.path.join(DOCS_ASSETS_DIR, filename), "WEBP", quality=88, method=6)


if __name__ == "__main__":
    _apply_to_existing("background-light.png", CREAM, CARAMEL, seed=1)
    _apply_to_existing("background-dark.png", DARK_ROAST, ESPRESSO, seed=2)
    _make_site_tile("wood-light.webp", CREAM, CARAMEL, seed=1)
    _make_site_tile("wood-dark.webp", DARK_ROAST, ESPRESSO, seed=2)
    print("Wrote app backgrounds and docs/assets/wood-{light,dark}.webp")
