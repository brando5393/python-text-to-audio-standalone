"""Regression tests for the reported bug: "the default system voice is still playing
regardless of voice selection." Root cause: when engine="piper" is selected but the
engine binary or the chosen voice isn't actually installed, Converter silently fell back
to pyttsx3 with no indication why -- from the user's side, this looked exactly like their
voice choice was being ignored.

Uses a manual logging.Handler attached directly to the "texttoaudio" logger rather than
pytest's caplog fixture: caplog's handler attachment didn't reliably see records from
this logger in this project's setup (verified independently -- the actual application
behavior is correct; caplog just wasn't a reliable way to observe it here), while a
plain handler we attach and remove ourselves is unambiguous.
"""

import logging
import tkinter as tk
import time

import Config
import Converter
import PiperEngine


class _CollectingHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())


def _wait_for_all_done(converter, timeout=20):
    events = []
    deadline = time.time() + timeout
    while time.time() < deadline:
        new_events = converter.poll_events()
        events.extend(new_events)
        if any(e[0] == "all_done" for e in new_events):
            return events
        time.sleep(0.05)
    raise TimeoutError(f"Conversion did not finish within {timeout}s. Events so far: {events}")


def _run_with_collected_logs(fn):
    """Runs fn(handler) with a _CollectingHandler attached to the "texttoaudio" logger
    for the duration of the call, then detaches it again."""
    logger = logging.getLogger("texttoaudio")
    handler = _CollectingHandler()
    logger.addHandler(handler)
    try:
        fn(handler)
    finally:
        logger.removeHandler(handler)
    return handler.messages


def test_falls_back_and_warns_when_piper_engine_not_installed(tk_root, tmp_path, monkeypatch, requires_pyttsx3_voice):
    monkeypatch.setattr(Config, "CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.setattr(PiperEngine, "PIPER_EXE", str(tmp_path / "no_engine" / "piper.exe"))
    Config.save({**Config.DEFAULTS, "engine": "piper", "voice": "en_US-amy-medium"})

    log_list = tk.Listbox(tk_root)
    from LogManager import LogManager
    logger = LogManager(log_list)
    converter = Converter.Converter(log_list)

    src = tmp_path / "note.txt"
    src.write_text("Testing the fallback warning.", encoding="utf-8")

    events = []

    def go(_handler):
        converter.convert_to_audio([str(src)], str(tmp_path / "out"))
        events.extend(_wait_for_all_done(converter))

    messages = _run_with_collected_logs(go)

    # It should still complete the conversion (via the fallback), just with a warning
    # explaining why the system voice was used instead of the selected Piper voice.
    assert any(e[0] == "done" for e in events)
    assert any("Piper is selected for" in m for m in messages), (messages, "expected a fallback warning")
    assert any("engine isn't installed" in m for m in messages)


def test_falls_back_and_warns_when_selected_voice_not_installed(tk_root, tmp_path, monkeypatch, requires_pyttsx3_voice):
    monkeypatch.setattr(Config, "CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.setattr(PiperEngine, "VOICES_DIR", str(tmp_path / "no_voices"))
    # Simulate the engine being installed (skip the real 21MB download in a test).
    monkeypatch.setattr(PiperEngine, "is_engine_installed", lambda: True)
    Config.save({**Config.DEFAULTS, "engine": "piper", "voice": "some-voice-that-was-never-downloaded"})

    log_list = tk.Listbox(tk_root)
    from LogManager import LogManager
    logger = LogManager(log_list)
    converter = Converter.Converter(log_list)

    src = tmp_path / "note.txt"
    src.write_text("Testing the fallback warning for a missing voice.", encoding="utf-8")

    events = []

    def go(_handler):
        converter.convert_to_audio([str(src)], str(tmp_path / "out"))
        events.extend(_wait_for_all_done(converter))

    messages = _run_with_collected_logs(go)

    assert any(e[0] == "done" for e in events)
    assert any("Piper is selected for" in m for m in messages)
    assert any("isn't downloaded yet" in m for m in messages)


def test_no_warning_when_piper_is_actually_ready(tk_root, tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.setattr(PiperEngine, "is_engine_installed", lambda: True)
    monkeypatch.setattr(PiperEngine, "is_voice_installed", lambda voice: True)
    monkeypatch.setattr(PiperEngine, "synthesize", lambda text, voice, path, **k: _write_fake_wav(path))
    Config.save({**Config.DEFAULTS, "engine": "piper", "voice": "fully-ready-voice"})

    log_list = tk.Listbox(tk_root)
    from LogManager import LogManager
    logger = LogManager(log_list)
    converter = Converter.Converter(log_list)

    src = tmp_path / "note.txt"
    src.write_text("Testing the happy path.", encoding="utf-8")

    events = []

    def go(_handler):
        converter.convert_to_audio([str(src)], str(tmp_path / "out"))
        events.extend(_wait_for_all_done(converter))

    messages = _run_with_collected_logs(go)

    assert any(e[0] == "done" for e in events)
    assert not any("Piper is selected for" in m for m in messages)


def _write_fake_wav(path):
    import wave
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(22050)
        w.writeframes(b"\x00\x00" * 100)
