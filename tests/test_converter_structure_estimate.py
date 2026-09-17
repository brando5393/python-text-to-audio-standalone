"""Verifies that when a file has no real structural metadata (a plain TXT file has no
page or chapter concept extract_structure_counts can read), the conversion sidecar falls
back to a heuristic estimate from the text itself, instead of leaving pages/chapters as
None (which the UI shows as an "Unknown" placeholder -- see ConversionsLibrary.py)."""

import json
import time
import wave

import Config
import Converter
import PiperEngine


def _write_fake_wav(_text, _voice_id, path, **_kwargs):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(22050)
        w.writeframes(b"\x00\x00" * 100)


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


def _make_converter(tk_root, tmp_path, monkeypatch, **config_overrides):
    monkeypatch.setattr(Config, "CONFIG_PATH", str(tmp_path / "config.json"))
    Config.save({**Config.DEFAULTS, **config_overrides})
    monkeypatch.setattr(PiperEngine, "is_engine_installed", lambda: True)
    monkeypatch.setattr(PiperEngine, "is_voice_installed", lambda voice: True)
    monkeypatch.setattr(PiperEngine, "synthesize", _write_fake_wav)

    import tkinter as tk
    return Converter.Converter(tk.Listbox(tk_root))


def test_txt_file_gets_estimated_pages_and_chapters_in_sidecar(tk_root, tmp_path, monkeypatch):
    converter = _make_converter(tk_root, tmp_path, monkeypatch, engine="piper", voice="en_US-amy-medium")

    src = tmp_path / "novel.txt"
    body = "Chapter 1\n" + ("Filler text. " * 400) + "\nChapter 2\n" + ("More filler. " * 400)
    src.write_text(body, encoding="utf-8")
    out_dir = tmp_path / "out"

    converter.convert_to_audio([str(src)], str(out_dir))
    events = _wait_for_all_done(converter)

    assert "error" not in [e[0] for e in events]
    with open(out_dir / "novel.wav.json", encoding="utf-8") as f:
        sidecar = json.load(f)
    assert sidecar["pages"] is not None and sidecar["pages"] >= 1
    assert sidecar["chapters"] == 2


def test_txt_file_with_no_chapter_headings_gets_estimated_pages_but_no_chapters(tk_root, tmp_path, monkeypatch):
    converter = _make_converter(tk_root, tmp_path, monkeypatch, engine="piper", voice="en_US-amy-medium")

    src = tmp_path / "note.txt"
    src.write_text("Just a short plain note with no chapter structure at all.", encoding="utf-8")
    out_dir = tmp_path / "out"

    converter.convert_to_audio([str(src)], str(out_dir))
    events = _wait_for_all_done(converter)

    assert "error" not in [e[0] for e in events]
    with open(out_dir / "note.wav.json", encoding="utf-8") as f:
        sidecar = json.load(f)
    assert sidecar["pages"] == 1
    assert sidecar["chapters"] is None
