import tkinter as tk

import ErrorReporter
import LogManager

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
