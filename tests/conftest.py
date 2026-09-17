import logging

import pytest
import ttkbootstrap as ttk

import Config
import ErrorReporter
import LogManager


@pytest.fixture(scope="session")
def tk_root():
    """A single hidden Tk root shared across the whole test session.

    Repeatedly creating and destroying a full Tk() root within one process is a known
    source of Tkinter instability (stray PhotoImage finalizers firing after teardown,
    "main thread is not in main loop" errors leaking into unrelated later tests) --
    tests that need real widgets create them as children of this one shared root instead.
    """
    root = ttk.Window(themename="flatly")
    root.withdraw()
    yield root
    root.destroy()


@pytest.fixture(autouse=True)
def isolated_logging(tmp_path, monkeypatch):
    """Prevents tests from writing to the real ~/.texttoaudio/texttoaudio.log or leaking
    handlers across tests. LogManager uses a module-level named logger
    (logging.getLogger("texttoaudio")) that only adds handlers once, by design, so it
    doesn't spam duplicate log lines during normal app use -- but that same guard means
    tests need explicit isolation, or the second test to construct a LogManager would
    silently keep the first test's (or a previous run's real) handlers."""
    monkeypatch.setattr(LogManager, "LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setattr(LogManager, "LOG_FILE", str(tmp_path / "logs" / "texttoaudio.log"))
    logger = logging.getLogger("texttoaudio")
    original_handlers = logger.handlers[:]
    logger.handlers = []
    yield
    for handler in logger.handlers:
        handler.close()
    logger.handlers = original_handlers


def _pyttsx3_actually_synthesizes():
    """Checking pyttsx3.init().getProperty("voices") alone isn't enough -- GitHub's
    windows-latest runner reports a voice as available but still produces empty/
    unreadable audio when actually asked to synthesize something, so this runs a real,
    tiny end-to-end synthesis (matching Converter._synthesize_chunk's own save_to_file
    + runAndWait pattern) and confirms a real, non-empty WAV comes out the other end."""
    import tempfile
    import wave

    try:
        import pyttsx3

        engine = pyttsx3.init()
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = f"{tmp_dir}/probe.wav"
            engine.save_to_file("Test.", path)
            engine.runAndWait()
            with wave.open(path, "rb") as wav_file:
                return wav_file.getnframes() > 0
    except Exception:
        return False


@pytest.fixture(scope="session")
def requires_pyttsx3_voice():
    """Skips a test that needs pyttsx3 to actually produce audio, on an environment
    where it doesn't -- observed on GitHub's windows-latest CI runner (a voice reports
    as available, but real synthesis still yields no usable audio), not on a real
    Windows install (verified extensively on an actual machine throughout this
    project). This is an environment gap, not an application bug: skipping is the
    correct response here, not a false failure."""
    if not _pyttsx3_actually_synthesizes():
        pytest.skip("pyttsx3 does not produce usable audio in this environment")


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Points Config.CONFIG_PATH at a throwaway file for every test, so nothing (e.g.
    PlaybackControls, built into every MiniPlayer/main-window Playback panel) reads or
    writes the developer's real ~/.texttoaudio/config.json while tests run. A test that
    needs a specific path still monkeypatches it explicitly (harmless double-patch)."""
    monkeypatch.setattr(Config, "CONFIG_PATH", str(tmp_path / "config.json"))


@pytest.fixture(autouse=True)
def no_real_error_reports(monkeypatch):
    """LogManager.add_event() calls ErrorReporter.report() on every "error"-level event,
    which shells out to the real `gh` CLI. Without this, any test that exercises an error
    path would file a live GitHub issue using the developer's own authenticated `gh`
    session -- tests that specifically exercise ErrorReporter re-patch it locally instead."""
    monkeypatch.setattr(ErrorReporter, "report", lambda *a, **k: None)
