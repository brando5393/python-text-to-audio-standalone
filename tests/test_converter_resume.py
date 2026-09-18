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


def test_failed_conversion_cleans_up_scratch_files(tk_root, tmp_path, monkeypatch):
    """If every chunk fails, _convert_one raises instead of producing a file -- that's a
    definitive failure, not an interruption, so the scratch state left behind must be
    cleaned up rather than orphaned in the Conversions folder forever."""
    converter, calls = _make_converter(tk_root, tmp_path, monkeypatch)

    def always_fails(self, chunk_text, chunk_path, use_piper, settings):
        raise RuntimeError("synthesis engine exploded")

    monkeypatch.setattr(Converter.Converter, "_synthesize_chunk", always_fails)

    text = "Sentence number one. " * 200
    chunks = TextChunking.split_into_chunks(text)

    out_dir = tmp_path / "out"
    os.makedirs(out_dir, exist_ok=True)
    output_file = str(out_dir / "book.wav")

    import pytest
    with pytest.raises(ValueError, match="No audio could be generated"):
        converter._convert_one("book.txt", chunks, output_file, text, False, Config.load(), 0, len(chunks), time.time())

    assert not os.path.isfile(output_file)
    assert not os.path.isfile(output_file + ".progress.json")
    assert not os.path.isfile(output_file + ".partial.pcm")
    assert not os.path.isfile(output_file + ".partial")


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


def test_ignores_resume_state_when_total_chunks_mismatches_re_extracted_document(tk_root, tmp_path, monkeypatch):
    """If the same source text now splits into a different number of chunks than the
    interrupted attempt recorded (e.g. the chunking algorithm changed between app
    versions, or a different code path produced a different split), the saved chunk
    index no longer lines up with the current chunk list at all -- resuming would
    resynthesize the wrong chunks or skip real ones, so it must start over instead."""
    converter, calls = _make_converter(tk_root, tmp_path, monkeypatch)

    text = "Sentence number one. " * 200
    chunks = TextChunking.split_into_chunks(text)
    assert len(chunks) >= 2
    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

    out_dir = tmp_path / "out"
    os.makedirs(out_dir, exist_ok=True)
    output_file = str(out_dir / "book.wav")
    # Same text hash, but a total_chunks count that doesn't match len(chunks) at all.
    _seed_resume_state(tmp_path, output_file, completed_chunks=1, total_chunks=len(chunks) + 5, text_hash=text_hash)

    converter._convert_one("book.txt", chunks, output_file, text, False, Config.load(), 0, len(chunks), time.time())

    assert len(calls) == len(chunks), "a total_chunks mismatch must fall back to synthesizing every chunk"


def test_load_resume_state_returns_none_for_corrupted_progress_json(tmp_path):
    """A progress.json truncated or corrupted by a crash mid-write (before the atomic
    os.replace in _save_resume_state) must be treated as "no usable resume state", not
    raise and crash the whole conversion."""
    progress_path = str(tmp_path / "book.wav.progress.json")
    pcm_path = str(tmp_path / "book.wav.partial.pcm")
    with open(pcm_path, "wb") as f:
        f.write(b"\x00\x00")
    with open(progress_path, "w", encoding="utf-8") as f:
        f.write("{not valid json at all")

    result = Converter._load_resume_state(progress_path, pcm_path, "some-hash", 10)
    assert result is None


def test_load_resume_state_returns_none_when_pcm_scratch_file_is_missing(tmp_path):
    """A progress.json can exist without its matching .partial.pcm (e.g. the pcm file
    was deleted by hand, or a previous run's cleanup step ran partway). Without the
    actual audio data to resume, the checkpoint alone is useless and must be ignored."""
    progress_path = str(tmp_path / "book.wav.progress.json")
    pcm_path = str(tmp_path / "book.wav.partial.pcm")  # deliberately never created
    with open(progress_path, "w", encoding="utf-8") as f:
        json.dump({"completed_chunks": 3, "total_chunks": 10, "text_hash": "abc"}, f)

    result = Converter._load_resume_state(progress_path, pcm_path, "abc", 10)
    assert result is None


def test_save_resume_state_survives_unwritable_progress_path(tmp_path):
    """If the progress.json can't be written (e.g. its parent directory was removed out
    from under a long-running conversion), losing that one checkpoint must not raise and
    kill the whole conversion -- the next chunk just tries to checkpoint again."""
    missing_dir_path = str(tmp_path / "does_not_exist" / "book.wav.progress.json")
    Converter._save_resume_state(missing_dir_path, 1, 10, "hash", False, None, {}, 0)  # must not raise
    assert not os.path.isfile(missing_dir_path)


def test_load_resume_state_truncates_pcm_written_past_the_last_checkpoint(tmp_path):
    """Reproduces the crash-between-writes race directly: a chunk's audio got appended to
    the .partial.pcm file, but the process died before _save_resume_state recorded that in
    progress.json. Without truncating back to the last confirmed-good size, resuming would
    re-synthesize that same chunk and append it again, duplicating it in the final audio."""
    progress_path = str(tmp_path / "book.wav.progress.json")
    pcm_path = str(tmp_path / "book.wav.partial.pcm")

    confirmed_bytes = b"\x01\x02" * 50  # what the last successful checkpoint recorded
    unrecorded_extra = b"\x03\x04" * 50  # a chunk appended after that, before the crash
    with open(pcm_path, "wb") as f:
        f.write(confirmed_bytes + unrecorded_extra)
    with open(progress_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "completed_chunks": 1, "total_chunks": 10, "text_hash": "abc",
                "pcm_bytes": len(confirmed_bytes),
            },
            f,
        )

    result = Converter._load_resume_state(progress_path, pcm_path, "abc", 10)
    assert result is not None
    assert result["completed_chunks"] == 1

    with open(pcm_path, "rb") as f:
        on_disk = f.read()
    assert on_disk == confirmed_bytes, "unrecorded trailing audio must be truncated away, not kept"


def test_load_resume_state_rejects_checkpoint_when_pcm_is_smaller_than_recorded():
    """If the pcm file somehow has *less* data than the checkpoint claims (e.g. a partial
    truncated write, or a scratch file replaced by hand), completed_chunks can't be
    trusted either -- resuming would skip real audio silently, so it must start over."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        progress_path = os.path.join(tmp, "book.wav.progress.json")
        pcm_path = os.path.join(tmp, "book.wav.partial.pcm")
        with open(pcm_path, "wb") as f:
            f.write(b"\x00\x00")
        with open(progress_path, "w", encoding="utf-8") as f:
            json.dump({"completed_chunks": 1, "total_chunks": 10, "text_hash": "abc", "pcm_bytes": 9999}, f)

        result = Converter._load_resume_state(progress_path, pcm_path, "abc", 10)
        assert result is None
