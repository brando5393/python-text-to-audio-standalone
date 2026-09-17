"""WCAG 2.1 contrast-ratio math (relative luminance -> ratio), per the formulas in
https://www.w3.org/TR/WCAG21/#dfn-relative-luminance and #dfn-contrast-ratio.

Used to actually verify a text/background color pairing meets the 4.5:1 AA minimum for
normal text, rather than eyeballing it -- the same way the theme's own "warning" accent
color (see main.py) was measured and darkened after it turned out to be only 2.25:1. See
test_contrast.py for the checks this runs against the app's own palette.
"""


def _linearize(channel):
    c = channel / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_color):
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _linearize(r) + 0.7152 * _linearize(g) + 0.0722 * _linearize(b)


def contrast_ratio(hex_a, hex_b):
    """Returns the WCAG contrast ratio between two colors, always >= 1.0 regardless of
    which one is passed first (the spec defines it as lighter-over-darker)."""
    lum_a, lum_b = relative_luminance(hex_a), relative_luminance(hex_b)
    lighter, darker = max(lum_a, lum_b), min(lum_a, lum_b)
    return (lighter + 0.05) / (darker + 0.05)


MIN_AA_CONTRAST = 4.5  # WCAG AA, normal-sized text
