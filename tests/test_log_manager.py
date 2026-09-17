import logging
import queue
import tkinter as tk

import Contrast
import ErrorReporter
import LogManager

# The real ttk input-box backgrounds each theme actually draws log text on (read off a
# live ttk.Style() instance while auditing this file's contrast -- see FileManager.py's
# OVERRIDE_COLOR_LIGHT/DARK comment for the same measurement).
LIGHT_INPUT_BG = "#f2e8d9"
DARK_INPUT_BG = "#2c2118"

_REAL_REPORT = ErrorReporter.report


def _make_logger(tk_root, tmp_path, monkeypatch):
    monkeypatch.setattr(LogManager, "LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setattr(LogManager, "LOG_FILE", str(tmp_path / "logs" / "texttoaudio.log"))
    display = tk.Listbox(tk_root)
    return LogManager.LogManager(display)


def test_error_level_triggers_error_reporter(tk_root, tmp_path, monkeypatch):
    monkeypatch.setattr(ErrorReporter, "report", _REAL_REPORT)
    calls = []
    monkeypatch.setattr(ErrorReporter, "report", lambda msg, err: calls.append((msg, err)))

    logger = _make_logger(tk_root, tmp_path, monkeypatch)
    logger.add_event("error", "Something failed", "TracebackText")

    assert calls == [("Something failed", "TracebackText")]


def test_non_error_levels_do_not_trigger_error_reporter(tk_root, tmp_path, monkeypatch):
    monkeypatch.setattr(ErrorReporter, "report", _REAL_REPORT)
    calls = []
    monkeypatch.setattr(ErrorReporter, "report", lambda msg, err: calls.append((msg, err)))

    logger = _make_logger(tk_root, tmp_path, monkeypatch)
    logger.add_event("info", "All good")
    logger.add_event("warn", "Careful")
    logger.add_event("alert", "Heads up")
    logger.add_event("debug", "Details")

    assert calls == []


def test_every_light_theme_log_color_meets_wcag_aa(monkeypatch):
    monkeypatch.setattr(LogManager, "_dark_mode", False)
    for level, color in LogManager.LEVEL_COLORS_LIGHT.items():
        ratio = Contrast.contrast_ratio(color, LIGHT_INPUT_BG)
        assert ratio >= Contrast.MIN_AA_CONTRAST, f"{logging.getLevelName(level)} only {ratio:.2f}:1"


def test_every_dark_theme_log_color_meets_wcag_aa(monkeypatch):
    monkeypatch.setattr(LogManager, "_dark_mode", True)
    for level, color in LogManager.LEVEL_COLORS_DARK.items():
        ratio = Contrast.contrast_ratio(color, DARK_INPUT_BG)
        assert ratio >= Contrast.MIN_AA_CONTRAST, f"{logging.getLevelName(level)} only {ratio:.2f}:1"


def test_the_old_hardcoded_info_color_would_have_failed_dark_theme_contrast():
    """Regression guard for why this changed at all: the single hardcoded INFO color
    this replaced (#1c1c1c) measured only ~1.09:1 against the dark theme's real input
    background -- near-black text on a near-black background, effectively invisible --
    because it was only ever checked against the light theme."""
    ratio = Contrast.contrast_ratio("#1c1c1c", DARK_INPUT_BG)
    assert ratio < Contrast.MIN_AA_CONTRAST


def test_set_dark_mode_switches_colors_used_for_new_log_entries(monkeypatch):
    """Exercises _QueueHandler.emit() directly (rather than through the shared
    "texttoaudio" logger) -- pytest's own log-capturing handler can end up occupying that
    logger's `.handlers` first depending on test/plugin ordering, which would make a
    higher-level test about whether *our* handler got attached at all, not about what
    this change actually does: pick the right color for the active theme."""
    q = queue.Queue()
    handler = LogManager._QueueHandler(q)
    record = logging.LogRecord("texttoaudio", logging.WARNING, __file__, 1, "a warning", None, None)

    monkeypatch.setattr(LogManager, "_dark_mode", False)
    handler.emit(record)
    _message, light_color = q.get_nowait()

    monkeypatch.setattr(LogManager, "_dark_mode", True)
    handler.emit(record)
    _message, dark_color = q.get_nowait()

    assert light_color == LogManager.LEVEL_COLORS_LIGHT[logging.WARNING]
    assert dark_color == LogManager.LEVEL_COLORS_DARK[logging.WARNING]
    assert light_color != dark_color
