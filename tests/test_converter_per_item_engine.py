"""Verifies each file in a batch can use its own engine/voice, set before conversion
starts, independent of every other file and of the global Settings default."""

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


def _sidecar(out_dir, wav_name):
    with open(out_dir / f"{wav_name}.wav.json", encoding="utf-8") as f:
        return json.load(f)


def _make_converter(tk_root, tmp_path, monkeypatch, **config_overrides):
    monkeypatch.setattr(Config, "CONFIG_PATH", str(tmp_path / "config.json"))
    Config.save({**Config.DEFAULTS, **config_overrides})
    monkeypatch.setattr(PiperEngine, "is_engine_installed", lambda: True)
    monkeypatch.setattr(PiperEngine, "is_voice_installed", lambda voice: True)
    monkeypatch.setattr(PiperEngine, "synthesize", _write_fake_wav)

    import tkinter as tk
    return Converter.Converter(tk.Listbox(tk_root))


def test_different_files_in_same_batch_use_different_engines(tk_root, tmp_path, monkeypatch, requires_pyttsx3_voice):
    converter = _make_converter(tk_root, tmp_path, monkeypatch, engine="pyttsx3", voice="en_US-amy-medium")

    system_src = tmp_path / "system_voice_doc.txt"
    system_src.write_text("This file should use the system voice.", encoding="utf-8")
    piper_src = tmp_path / "piper_doc.txt"
    piper_src.write_text("This file should use Piper.", encoding="utf-8")

    out_dir = tmp_path / "out"
    converter.convert_to_audio(
        [
            {"path": str(system_src), "engine": None, "voice": None},
            {"path": str(piper_src), "engine": "piper", "voice": "en_US-ryan-high"},
        ],
        str(out_dir),
    )
    _wait_for_all_done(converter)

    assert _sidecar(out_dir, "system_voice_doc")["engine"] == "pyttsx3"
    piper_sidecar = _sidecar(out_dir, "piper_doc")
    assert piper_sidecar["engine"] == "piper"
    assert piper_sidecar["voice_id"] == "en_US-ryan-high"


def test_per_item_voice_overrides_the_global_default(tk_root, tmp_path, monkeypatch):
    converter = _make_converter(tk_root, tmp_path, monkeypatch, engine="piper", voice="en_US-amy-medium")

    src = tmp_path / "custom_voice_doc.txt"
    src.write_text("This file wants a specific voice, not the global default.", encoding="utf-8")

    out_dir = tmp_path / "out"
    converter.convert_to_audio(
        [{"path": str(src), "engine": "piper", "voice": "en_US-ryan-high"}], str(out_dir)
    )
    _wait_for_all_done(converter)

    sidecar = _sidecar(out_dir, "custom_voice_doc")
    assert sidecar["voice_id"] == "en_US-ryan-high"  # the per-item choice, not en_US-amy-medium


def test_item_with_no_override_falls_back_to_global_settings(tk_root, tmp_path, monkeypatch):
    converter = _make_converter(tk_root, tmp_path, monkeypatch, engine="piper", voice="en_US-amy-medium")

    src = tmp_path / "default_doc.txt"
    src.write_text("This file has no per-item override at all.", encoding="utf-8")

    out_dir = tmp_path / "out"
    converter.convert_to_audio([{"path": str(src), "engine": None, "voice": None}], str(out_dir))
    _wait_for_all_done(converter)

    sidecar = _sidecar(out_dir, "default_doc")
    assert sidecar["engine"] == "piper"
    assert sidecar["voice_id"] == "en_US-amy-medium"


def test_plain_path_string_behaves_like_no_override(tk_root, tmp_path, monkeypatch, requires_pyttsx3_voice):
    """Backward compatibility: re-convert and batch-resume both pass plain path strings,
    not dicts -- these must keep working exactly as before, using the global settings."""
    converter = _make_converter(tk_root, tmp_path, monkeypatch, engine="pyttsx3")

    src = tmp_path / "plain_path_doc.txt"
    src.write_text("Just a plain path string, not a dict.", encoding="utf-8")

    out_dir = tmp_path / "out"
    converter.convert_to_audio([str(src)], str(out_dir))
    _wait_for_all_done(converter)

    assert _sidecar(out_dir, "plain_path_doc")["engine"] == "pyttsx3"


def test_apply_to_all_style_batch_all_use_the_same_explicit_engine(tk_root, tmp_path, monkeypatch):
    """Simulates clicking "Apply to All" in the UI: every item gets the same explicit
    override, independent of what the global Settings default happens to be."""
    converter = _make_converter(tk_root, tmp_path, monkeypatch, engine="pyttsx3")

    files = []
    for i in range(3):
        p = tmp_path / f"doc{i}.txt"
        p.write_text(f"Document number {i}.", encoding="utf-8")
        files.append({"path": str(p), "engine": "piper", "voice": "en_US-ryan-high"})

    out_dir = tmp_path / "out"
    converter.convert_to_audio(files, str(out_dir))
    _wait_for_all_done(converter)

    for i in range(3):
        sidecar = _sidecar(out_dir, f"doc{i}")
        assert sidecar["engine"] == "piper"
        assert sidecar["voice_id"] == "en_US-ryan-high"
