import Contrast
import FileManager

# The app's own coffeehouse theme colors (see main.py's ttk.Theme(...) registration) and
# the actual per-theme ttk input-box backgrounds ttkbootstrap derives from them (read
# directly off a live ttk.Style() instance while auditing this file's contrast, not
# guessed) -- these are what the file list's text is actually drawn on.
LIGHT_INPUT_BG = "#f2e8d9"
DARK_INPUT_BG = "#2c2118"


def test_contrast_ratio_is_symmetric_and_self_contrast_is_one():
    assert Contrast.contrast_ratio("#000000", "#ffffff") == Contrast.contrast_ratio("#ffffff", "#000000")
    assert Contrast.contrast_ratio("#808080", "#808080") == 1.0


def test_contrast_ratio_matches_known_black_on_white():
    # Black on white is the textbook maximum, exactly 21:1.
    assert round(Contrast.contrast_ratio("#000000", "#ffffff"), 2) == 21.0


def test_override_color_meets_wcag_aa_on_light_theme_input_background():
    ratio = Contrast.contrast_ratio(FileManager.FileManager.OVERRIDE_COLOR_LIGHT, LIGHT_INPUT_BG)
    assert ratio >= Contrast.MIN_AA_CONTRAST


def test_override_color_meets_wcag_aa_on_dark_theme_input_background():
    ratio = Contrast.contrast_ratio(FileManager.FileManager.OVERRIDE_COLOR_DARK, DARK_INPUT_BG)
    assert ratio >= Contrast.MIN_AA_CONTRAST


def test_the_old_hardcoded_blue_would_have_failed_dark_theme_contrast():
    """Regression guard for why this changed at all: plain "blue" (#0000FF), the color
    this replaced, measured only ~1.83:1 against the dark theme's input background --
    proof the old color-coding was never actually checked against both themes."""
    ratio = Contrast.contrast_ratio("#0000FF", DARK_INPUT_BG)
    assert ratio < Contrast.MIN_AA_CONTRAST
