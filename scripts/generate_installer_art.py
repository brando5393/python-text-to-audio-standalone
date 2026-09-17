"""Generates the branded bitmaps the Windows Installer UI shows during setup (the top
banner on every page, and the full-panel background on the Welcome/Exit pages), so the
.msi doesn't fall back to Windows Installer's plain default grey. Run manually whenever
the logo or theme colors change -- the output is committed, not built by CI:

    poetry run python scripts/generate_installer_art.py

Windows Installer requires these as true BMP (not PNG), at exact pixel sizes:
  banner.bmp    493 x 58   -- top strip on every dialog
  dialog.bmp    493 x 312  -- full background on the Welcome and Exit dialogs
See setup.py's bdist_msi_options["data"]["Binary"] for how these get embedded.
"""

import os

from PIL import Image, ImageDraw, ImageFont

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "..", "assets")
FONTS_DIR = r"C:\Windows\Fonts"

# Same coffeehouse palette as main.py's ttkbootstrap theme.
CREAM = "#f2e8d9"
ESPRESSO = "#6f4e37"
ESPRESSO_DARK = "#3b2a1e"
CARAMEL = "#a97142"


def _title_font(size):
    try:
        return ImageFont.truetype(os.path.join(FONTS_DIR, "palab.ttf"), size)
    except OSError:
        return ImageFont.load_default()


def _subtitle_font(size):
    try:
        return ImageFont.truetype(os.path.join(FONTS_DIR, "pala.ttf"), size)
    except OSError:
        return ImageFont.load_default()


def make_banner():
    width, height = 493, 58
    img = Image.new("RGB", (width, height), CREAM)
    draw = ImageDraw.Draw(img)

    logo = Image.open(os.path.join(ASSETS_DIR, "logo.png")).convert("RGBA")
    logo_size = 44
    logo = logo.resize((logo_size, logo_size), Image.LANCZOS)
    logo_y = (height - logo_size) // 2
    img.paste(logo, (10, logo_y), logo)

    draw.text((10 + logo_size + 10, height // 2), "Talebrew", font=_title_font(22), fill=ESPRESSO, anchor="lm")
    draw.line([(0, height - 1), (width, height - 1)], fill=CARAMEL, width=1)

    img.save(os.path.join(ASSETS_DIR, "installer_banner.bmp"))


def make_dialog_background():
    width, height = 493, 312
    img = Image.new("RGB", (width, height), CREAM)
    draw = ImageDraw.Draw(img)

    # A soft espresso panel across the bottom third keeps the standard installer
    # text (which Windows Installer draws on top of this bitmap) readable, while
    # still reading as branded rather than a plain grey default.
    panel_top = int(height * 0.62)
    draw.rectangle([(0, panel_top), (width, height)], fill=ESPRESSO)

    logo = Image.open(os.path.join(ASSETS_DIR, "logo.png")).convert("RGBA")
    logo_size = 150
    logo = logo.resize((logo_size, logo_size), Image.LANCZOS)
    logo_x = (width - logo_size) // 2
    logo_y = int(panel_top * 0.5) - logo_size // 2
    img.paste(logo, (logo_x, logo_y), logo)

    draw.text(
        (width // 2, panel_top + 14), "Talebrew", font=_title_font(26), fill=CREAM, anchor="ma",
    )
    draw.text(
        (width // 2, panel_top + 48), "Every story, brewed aloud.", font=_subtitle_font(13), fill=CREAM, anchor="ma",
    )

    img.save(os.path.join(ASSETS_DIR, "installer_dialog.bmp"))


if __name__ == "__main__":
    make_banner()
    make_dialog_background()
    print("Wrote assets/installer_banner.bmp and assets/installer_dialog.bmp")
