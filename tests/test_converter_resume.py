"""Tests for resuming an interrupted conversion (see Converter._convert_one), using a
fake _synthesize_chunk so these stay fast and don't depend on a real TTS engine."""

import hashlib
import json
import os
import time
import wave

import Config
import Converter
import TextChunking


def _write_silence_wav(path, num_frames=50, framerate=16000):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(framerate)
        w.writeframes(b"\x00\x00" * num_frames)


def _seed_resume_state(tmp_path, output_file, completed_chunks, total_chunks, text_hash):
    """Writes the exact on-disk state _convert_one would have left behind if the app
    had been closed or crashed after `completed_chunks` chunks finished."""
    seed_wav = str(tmp_path / "seed.wav")
    _write_silence_wav(seed_wav)
    with wave.open(seed_wav, "rb") as w:
        one_chunk_frames = w.readframes(w.getnframes())
    with open(output_file + ".partial.pcm", "wb") as f:
        for _ in range(completed_chunks):
            f.write(one_chunk_frames)
    with open(output_file + ".progress.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "completed_chunks": completed_chunks, "total_chunks": total_chunks, "text_hash": text_hash,
                "engine": "pyttsx3", "voice_id": None, "nchannels": 1, "sampwidth": 2, "framerate": 16000,
            },
            f,
        )


def _make_converter(tk_root, tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "CONFIG_PATH", str(tmp_path / "config.json"))
    Config.save({**Config.DEFAULTS, "engine": "pyttsx3"})

    import tkinter as tk
    converter = Converter.Converter(tk.Listbox(tk_root))

    calls = []

    def fake_synthesize(self, chunk_text, chunk_path, use_piper, settings):
        calls.append(chunk_text)
        _write_silence_wav(chunk_path)

    monkeypatch.setattr(Converter.Converter, "_synthesize_chunk", fake_synthesize)
    return converter, calls


def test_resumes_from_last_completed_chunk(tk_root, tmp_path, monkeypatch):
    converter, calls = _make_converter(tk_root, tmp_path, monkeypatch)

    text = "Sentence number one. " * 200
    chunks = TextChunking.split_into_chunks(text)
    assert len(chunks) >= 2, "test needs multiple chunks to prove a resume, not a fresh start"
    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

    out_dir = tmp_path / "out"
    os.makedirs(out_dir, exist_ok=True)
    output_file = str(out_dir / "book.wav")
    _seed_resume_state(tmp_path, output_file, completed_chunks=1, total_chunks=len(chunks), text_hash=text_hash)

    converter._convert_one("book.txt", chunks, output_file, text, False, Config.load(), 0, len(chunks), time.time())

    assert len(calls) == len(chunks) - 1, "the already-completed first chunk should not be re-synthesized"
    assert os.path.isfile(output_file)
    assert not os.path.isfile(output_file + ".progress.json")
    assert not os.path.isfile(output_file + ".partial.pcm")


def test_ignores_resume_state_when_text_changed(tk_root, tmp_path, monkeypatch):
    """If the source document changed since the interrupted attempt, the old progress
    no longer corresponds to this text -- resuming would stitch together audio from two
    different documents, so it must start over instead."""
    converter, calls = _make_converter(tk_root, tmp_path, monkeypatch)

    text = "Sentence number one. " * 200
    chunks = TextChunking.split_into_chunks(text)

    out_dir = tmp_path / "out"
    os.makedirs(out_dir, exist_ok=True)
    output_file = str(out_dir / "book.wav")
    _seed_resume_state(tmp_path, output_file, completed_chunks=1, total_chunks=len(chunks), text_hash="stale-hash")

    converter._convert_one("book.txt", chunks, output_file, text, False, Config.load(), 0, len(chunks), time.time())

    assert len(calls) == len(chunks), "a text mismatch must fall back to synthesizing every chunk"


def test_fresh_conversion_leaves_no_resume_scratch_files(tk_root, tmp_path, monkeypatch):
    converter, calls = _make_converter(tk_root, tmp_path, monkeypatch)

    text = "A short one-chunk conversion."
    chunks = TextChunking.split_into_chunks(text)

    out_dir = tmp_path / "out"
    os.makedirs(out_dir, exist_ok=True)
    output_file = str(out_dir / "note.wav")

    converter._convert_one("note.txt", chunks, output_file, text, False, Config.load(), 0, len(chunks), time.time())

    assert len(calls) == len(chunks)
    assert os.path.isfile(output_file)
    assert not os.path.isfile(output_file + ".progress.json")
    assert not os.path.isfile(output_file + ".partial.pcm")
