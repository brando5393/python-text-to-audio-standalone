"""Regenerates the app's decorative background images (assets/background-light.png,
assets/background-dark.png) and the website's background textures (docs/assets/
wood-*.webp) with the same wood-grain look -- built entirely from colors already in the
app's own palette (main.py's ttk.Theme() call), no new hues introduced.

The app's background is generated at a canvas far larger than any realistic window
(2560x1600), *not* the size of any particular window. main.py's background Label
displays it unscaled and un-stretched -- Tk clips an oversized image to whatever
smaller area the Label actually occupies rather than distorting it, which is exactly
the "always fills the visible area, never stretched, never tiled" behavior a CSS
`background-size: cover` would give, achieved for free without adding a runtime image-
resizing dependency (Pillow is a dev-only dependency here; ImageTk-based dynamic resize
at runtime would need to move it into the app's actual shipped dependencies).

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


def _smooth_field(size, rng, scale):
    """Smooth 2D noise at a given scale, via bilinear upsampling from a coarse random
    grid -- the base ingredient for domain warping below."""
    width, height = size
    gw, gh = max(2, width // scale + 2), max(2, height // scale + 2)
    coarse = rng.uniform(-1, 1, (gh, gw))
    return np.array(Image.fromarray((coarse * 127 + 128).astype(np.uint8)).resize(
        (width, height), Image.BICUBIC
    ), dtype=np.float64) / 127.0 - 1.0


def _wood_grain(size, base, grain_color, seed, knots=True):
    """An organic wood-grain field: mostly flowing, irregular parallel grain (base
    directional flow + gentle warp), with a handful of sparse, varied knots blended in
    smoothly wherever a few random attractor points pull the flow into tight concentric
    swirls -- real wood is mostly calm grain with knots as the exception, not wall-to-
    wall rosettes, which is what a naive grid of identical radial fields produces.
    Blended between `base` and `grain_color`, both already palette colors, so this only
    ever mixes tones that already exist in the app, never introduces a new one.

    `knots=False` skips the swirl entirely, leaving calm flowing grain -- unused by
    either the app or the website today, but kept as an option for any future context
    that only ever shows the texture through thin, irregular gaps rather than one open
    canvas, where a dramatic off-center knot would read as a fragmented, random-looking
    sliver instead of a coherent surface."""
    width, height = size
    rng = np.random.default_rng(seed)
    y = np.arange(height).reshape(-1, 1).astype(np.float64)
    x = np.arange(width).reshape(1, -1).astype(np.float64)
    y = np.broadcast_to(y, (height, width)).copy()
    x = np.broadcast_to(x, (height, width)).copy()

    # Sparse knot attractors: each pulls nearby coordinates toward it (inverse-square
    # falloff, capped so it doesn't blow up at the center), which is what makes grain
    # lines curl into tight rings near a knot while staying calm everywhere else.
    diag = (width ** 2 + height ** 2) ** 0.5
    n_knots = max(1, round(diag / 500)) if knots else 0
    for _ in range(n_knots):
        kx, ky = rng.uniform(0, width), rng.uniform(0, height)
        dx, dy = x - kx, y - ky
        dist = np.sqrt(dx * dx + dy * dy) + 1e-6
        radius = rng.uniform(0.12, 0.22) * diag
        falloff = np.exp(-(dist / radius) ** 2)  # 1 at the knot, ~0 a few radii out
        # Spin the local angle proportionally to how close we are to the knot, which
        # winds the base flow into a tight swirl near it and leaves it untouched
        # further away -- this is what makes a knot instead of a wall-to-wall rosette.
        spin = falloff * rng.uniform(2.0, 3.5)
        new_dx = dx * np.cos(spin) - dy * np.sin(spin)
        new_dy = dx * np.sin(spin) + dy * np.cos(spin)
        # Continuous blend by `falloff` itself (already a smooth 0..1 Gaussian) instead
        # of a hard np.where cutoff -- a thresholded switch is exactly what produces a
        # visible circular seam where the mask crosses its cutoff value.
        x = x + falloff * (new_dx - dx)
        y = y + falloff * (new_dy - dy)

    # Gentle broad warp everywhere (independent of the knots) so even the calm areas
    # have irregular, non-mechanical flow instead of perfectly straight lines.
    x = x + 18 * _smooth_field(size, rng, scale=max(width, height) // 4)
    y = y + 18 * _smooth_field(size, rng, scale=max(width, height) // 4)

    # Base directional grain, mostly horizontal -- this is what the swirl code above
    # bends locally into knots.
    rings = np.sin(y / 10.0 + x * 0.01)
    rings = (rings - rings.min()) / (rings.max() - rings.min())  # 0..1

    # Fine fibrous noise, smoothed slightly by averaging a couple of offset copies.
    noise = rng.random((height, width))
    noise = (noise + np.roll(noise, 1, axis=0) + np.roll(noise, 1, axis=1)) / 3.0

    grain = np.clip(0.82 * rings + 0.18 * noise, 0, 1)

    # Blend base -> grain_color using `grain` as the mix factor, kept subtle so it
    # reads as texture, not a color change.
    strength = 0.24
    out = np.empty((height, width, 3), dtype=np.float64)
    for c in range(3):
        out[:, :, c] = base[c] + (grain_color[c] - base[c]) * grain * strength
    return out


APP_CANVAS_SIZE = (2560, 1600)
# The logo watermark sits at a fixed offset from the canvas's own center -- since Tk
# always shows a centered crop of this oversized image regardless of the actual window
# size, "offset from center" is the only positioning that stays roughly consistent
# (bottom-right-ish of whatever's visible) across different window sizes, unlike an
# offset from the canvas's actual corner, which would only ever be visible if the
# window were maximized to the canvas's own full size.
_WATERMARK_CENTER_OFFSET = (560, 330)


def _make_app_background(filename, base_color, grain_color, seed):
    wood = np.clip(_wood_grain(APP_CANVAS_SIZE, base_color, grain_color, seed, knots=True), 0, 255).astype(np.uint8)
    img = Image.fromarray(wood, "RGB").convert("RGBA")

    logo = Image.open(os.path.join(ASSETS_DIR, "logo.png")).convert("RGBA")
    logo_size = 260
    logo = logo.resize((logo_size, logo_size), Image.LANCZOS)
    r, g, b, a = logo.split()
    logo.putalpha(a.point(lambda v: int(v * 0.16)))  # faint watermark, not a real logo

    cx, cy = APP_CANVAS_SIZE[0] // 2, APP_CANVAS_SIZE[1] // 2
    ox, oy = _WATERMARK_CENTER_OFFSET
    pos = (cx + ox - logo_size // 2, cy + oy - logo_size // 2)
    img.alpha_composite(logo, dest=pos)
    img.convert("RGB").save(os.path.join(ASSETS_DIR, filename), optimize=True)


def _make_site_background(filename, base_color, grain_color, seed, size=(1920, 1200)):
    """A single, non-tiled texture -- the swirl/knot pattern isn't seamless at its
    edges, so CSS `background-repeat` would show a visible seam grid. Used instead with
    `background-attachment: fixed; background-size: cover` in the site's CSS, which
    only ever needs to cover the viewport once, not repeat across page scroll."""
    wood = np.clip(_wood_grain(size, base_color, grain_color, seed), 0, 255).astype(np.uint8)
    Image.fromarray(wood, "RGB").save(os.path.join(DOCS_ASSETS_DIR, filename), "WEBP", quality=85, method=6)


if __name__ == "__main__":
    _make_app_background("background-light.png", CREAM, CARAMEL, seed=1)
    _make_app_background("background-dark.png", DARK_ROAST, ESPRESSO, seed=2)
    # Filenames carry a version suffix, bumped by hand whenever this script changes --
    # browsers cache images aggressively, and a same-named file update can sit stale in
    # a visitor's cache indefinitely (confirmed happening in practice: the live server
    # was already serving the new bytes under the old name while a browser kept showing
    # the previous version). A new filename forces every browser to actually refetch it.
    _make_site_background("wood-light-v2.webp", CREAM, CARAMEL, seed=1)
    _make_site_background("wood-dark-v2.webp", DARK_ROAST, ESPRESSO, seed=2)
    print("Wrote app backgrounds and docs/assets/wood-{light,dark}-v2.webp")
