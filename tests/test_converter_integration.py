"""End-to-end conversion tests using the real pyttsx3/SAPI engine (fast, native --
no network, no emulation). Piper isn't exercised here since it requires downloading
a ~20MB engine and ~60MB voice model, which doesn't belong in a fast unit test run."""

import os
import time

import Config
import Converter


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


def test_converts_txt_file_to_wav(tk_root, tmp_path, monkeypatch, requires_pyttsx3_voice):
    monkeypatch.setattr(Config, "CONFIG_PATH", str(tmp_path / "config.json"))
    Config.save({**Config.DEFAULTS, "engine": "pyttsx3"})

    import tkinter as tk
    log_widget = tk.Listbox(tk_root)
    converter = Converter.Converter(log_widget)

    src = tmp_path / "note.txt"
    src.write_text("This is a short end to end conversion test.", encoding="utf-8")
    out_dir = tmp_path / "out"

    converter.convert_to_audio([str(src)], str(out_dir))
    events = _wait_for_all_done(converter)

    kinds = [e[0] for e in events]
    assert "done" in kinds
    assert "all_done" in kinds
    assert (out_dir / "note.wav").exists()
    assert (out_dir / "note.wav").stat().st_size > 0


def test_unsupported_file_is_skipped_not_errored(tk_root, tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "CONFIG_PATH", str(tmp_path / "config.json"))
    Config.save({**Config.DEFAULTS, "engine": "pyttsx3"})

    import tkinter as tk
    log_widget = tk.Listbox(tk_root)
    converter = Converter.Converter(log_widget)

    src = tmp_path / "image.png"
    src.write_bytes(b"\x89PNG")

    converter.convert_to_audio([str(src)], str(tmp_path / "out"))
    events = _wait_for_all_done(converter)

    kinds = [e[0] for e in events]
    assert "skipped" in kinds
    assert "error" not in kinds


def test_cancel_stops_remaining_files(tk_root, tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "CONFIG_PATH", str(tmp_path / "config.json"))
    Config.save({**Config.DEFAULTS, "engine": "pyttsx3"})

    import tkinter as tk
    log_widget = tk.Listbox(tk_root)
    converter = Converter.Converter(log_widget)

    files = []
    for i in range(3):
        p = tmp_path / f"doc{i}.txt"
        p.write_text("Some text to convert. " * 50, encoding="utf-8")
        files.append(str(p))

    out_dir = tmp_path / "out"
    converter.convert_to_audio(files, str(out_dir))
    converter.cancel()
    events = _wait_for_all_done(converter)

    skipped = [e for e in events if e[0] == "skipped" and e[2] == "Cancelled"]
    assert len(skipped) >= 1
