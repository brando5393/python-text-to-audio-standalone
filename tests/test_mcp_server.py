"""Tests the business logic behind mcp_server.py's four MCP tools -- format listing,
job creation/validation, status tracking, and library listing. The raw MCP stdio
protocol plumbing (FastMCP's decorator wiring) is thin glue and isn't re-tested here;
these call the underlying tool functions directly, the same way FastMCP's own decorator
leaves them callable (see mcp_server.py -- @mcp.tool() returns the function unchanged).

Engines are mocked the same way tests/test_converter_*.py already does, so no real
Piper/pyttsx3 synthesis happens here.
"""

import json
import time
import wave

import pytest

# mcp_server.py needs the optional `mcp` dependency group (poetry install --with mcp),
# not installed by a plain `poetry install` -- skip this whole module rather than
# failing collection when it isn't present, so the base test suite still runs clean.
pytest.importorskip("mcp")

import Config
import Converter
import FileManager
import mcp_server
import PiperEngine
import TextExtraction
from JobStore import JobStore


def _write_fake_wav(_text, _voice_id, path, **_kwargs):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(22050)
        w.writeframes(b"\x00\x00" * 100)


@pytest.fixture(autouse=True)
def isolated_job_store(tmp_path, monkeypatch):
    """Every mcp_server test gets its own on-disk job store, instead of the real
    ~/.texttoaudio/mcp_jobs.json a developer might have from actual use."""
    monkeypatch.setattr(mcp_server, "_jobs", JobStore(str(tmp_path / "mcp_jobs.json")))


@pytest.fixture
def fake_piper(monkeypatch):
    monkeypatch.setattr(PiperEngine, "is_engine_installed", lambda: True)
    monkeypatch.setattr(PiperEngine, "is_voice_installed", lambda voice: True)
    monkeypatch.setattr(PiperEngine, "synthesize", _write_fake_wav)


def _wait_for_status(job_id, *, status_in, timeout=20):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = mcp_server.get_conversion_status(job_id)
        if job.get("status") in status_in:
            return job
        time.sleep(0.05)
    raise TimeoutError(f"Job {job_id} did not reach {status_in} within {timeout}s (last: {job})")


def test_list_supported_formats_reuses_text_extraction_constant():
    result = mcp_server.list_supported_formats()
    assert result["supported_extensions"] == list(TextExtraction.SUPPORTED_EXTENSIONS)


def test_convert_file_rejects_missing_path(tmp_path):
    result = mcp_server.convert_file(str(tmp_path / "does_not_exist.txt"))
    assert "error" in result
    assert "not found" in result["error"].lower()


def test_convert_file_rejects_unsupported_extension(tmp_path):
    bad_file = tmp_path / "image.png"
    bad_file.write_bytes(b"\x89PNG")

    result = mcp_server.convert_file(str(bad_file))
    assert "error" in result
    assert "unsupported" in result["error"].lower()


def test_convert_file_starts_a_job_and_returns_immediately(tmp_path, fake_piper, monkeypatch):
    monkeypatch.setattr(Config, "CONFIG_PATH", str(tmp_path / "config.json"))
    Config.save({**Config.DEFAULTS, "engine": "piper", "voice": "en_US-amy-medium"})

    src = tmp_path / "book.txt"
    src.write_text("A short document to convert.", encoding="utf-8")
    out_dir = tmp_path / "out"

    started = time.time()
    result = mcp_server.convert_file(str(src), output_dir=str(out_dir))
    elapsed = time.time() - started

    assert elapsed < 5, "convert_file should return immediately, not block for the whole conversion"
    assert result["status"] == "running"
    assert "job_id" in result
    assert result["engine"] == "piper"
    assert result["voice"] == "en_US-amy-medium"


def test_convert_file_job_eventually_completes_and_reports_output(tmp_path, fake_piper, monkeypatch):
    monkeypatch.setattr(Config, "CONFIG_PATH", str(tmp_path / "config.json"))
    Config.save({**Config.DEFAULTS, "engine": "piper", "voice": "en_US-amy-medium"})

    src = tmp_path / "book.txt"
    src.write_text("Another short document.", encoding="utf-8")
    out_dir = tmp_path / "out"

    result = mcp_server.convert_file(str(src), output_dir=str(out_dir))
    job = _wait_for_status(result["job_id"], status_in={"done", "error", "failed"})

    assert job["status"] == "done"
    assert job["output_files"]
    assert (out_dir / "book.wav").exists()


def test_convert_file_uses_per_call_engine_and_voice_override(tmp_path, fake_piper, monkeypatch):
    monkeypatch.setattr(Config, "CONFIG_PATH", str(tmp_path / "config.json"))
    Config.save({**Config.DEFAULTS, "engine": "pyttsx3", "voice": "en_US-amy-medium"})

    src = tmp_path / "book.txt"
    src.write_text("Uses an explicit override, not the global default.", encoding="utf-8")
    out_dir = tmp_path / "out"

    result = mcp_server.convert_file(str(src), engine="piper", voice="en_US-ryan-high", output_dir=str(out_dir))
    assert result["engine"] == "piper"
    assert result["voice"] == "en_US-ryan-high"

    job = _wait_for_status(result["job_id"], status_in={"done", "error", "failed"})
    with open(out_dir / "book.wav.json", encoding="utf-8") as f:
        sidecar = json.load(f)
    assert sidecar["engine"] == "piper"
    assert sidecar["voice_id"] == "en_US-ryan-high"


def test_get_conversion_status_unknown_job_id():
    result = mcp_server.get_conversion_status("nonexistent-job-id")
    assert "error" in result


def test_list_conversions_reads_sidecar_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(FileManager, "CONVERSIONS_ROOT", str(tmp_path))

    (tmp_path / "book.wav").write_bytes(b"data")
    (tmp_path / "book.wav.json").write_text(
        json.dumps({
            "engine": "piper", "voice_id": "en_US-ryan-high", "voice_label": "Ryan (US, high)",
            "text": "hi", "pages": 42, "chapters": 7,
        })
    )

    result = mcp_server.list_conversions()
    assert result["conversions_root"] == str(tmp_path)
    entries = {entry["name"]: entry for entry in result["files"]}
    assert entries["book.wav"]["pages"] == 42
    assert entries["book.wav"]["chapters"] == 7
    assert entries["book.wav"]["voice"] == "Ryan (US, high)"
    assert entries["book.wav"]["engine"] == "piper"


def test_list_conversions_handles_missing_root_gracefully(tmp_path, monkeypatch):
    monkeypatch.setattr(FileManager, "CONVERSIONS_ROOT", str(tmp_path / "does_not_exist"))
    result = mcp_server.list_conversions()
    assert result["files"] == []


def test_list_conversions_omits_partial_and_sidecar_files(tmp_path, monkeypatch):
    monkeypatch.setattr(FileManager, "CONVERSIONS_ROOT", str(tmp_path))
    (tmp_path / "finished.wav").write_bytes(b"data")
    (tmp_path / "unfinished.wav.partial").write_bytes(b"data")
    (tmp_path / "finished.wav.json").write_text(json.dumps({"text": "hi"}))

    names = {entry["name"] for entry in mcp_server.list_conversions()["files"]}
    assert names == {"finished.wav"}


def test_converter_runs_headless_with_no_tk_widget(tmp_path, fake_piper, monkeypatch):
    """The underlying fix this server depends on: Converter/LogManager must not require
    a Tk widget at all."""
    monkeypatch.setattr(Config, "CONFIG_PATH", str(tmp_path / "config.json"))
    Config.save({**Config.DEFAULTS, "engine": "piper", "voice": "en_US-amy-medium"})

    converter = Converter.Converter(app_log_display=None)
    src = tmp_path / "note.txt"
    src.write_text("Headless conversion smoke test.", encoding="utf-8")
    out_dir = tmp_path / "out"

    converter.convert_to_audio([str(src)], str(out_dir))

    deadline = time.time() + 20
    events = []
    while time.time() < deadline:
        events.extend(converter.poll_events())
        if any(e[0] == "all_done" for e in events):
            break
        time.sleep(0.05)

    assert any(e[0] == "done" for e in events)
    assert (out_dir / "note.wav").exists()
