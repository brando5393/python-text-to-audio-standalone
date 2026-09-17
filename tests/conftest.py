import logging

import pytest
import ttkbootstrap as ttk

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


def _pyttsx3_voice_available():
    try:
        import pyttsx3
        return bool(pyttsx3.init().getProperty("voices"))
    except Exception:
        return False


@pytest.fixture(scope="session")
def requires_pyttsx3_voice():
    """Skips a test that needs pyttsx3 to actually produce audio, on an environment
    with no SAPI voice registered at all -- observed on GitHub's windows-latest CI
    runner, not on a real Windows install (every real target machine for this app
    ships at least one SAPI voice by default). This is an environment gap, not an
    application bug: skipping is the correct response, not a false failure."""
    if not _pyttsx3_voice_available():
        pytest.skip("No SAPI voice registered in this environment")


@pytest.fixture(autouse=True)
def no_real_error_reports(monkeypatch):
    """LogManager.add_event() calls ErrorReporter.report() on every "error"-level event,
    which shells out to the real `gh` CLI. Without this, any test that exercises an error
    path would file a live GitHub issue using the developer's own authenticated `gh`
    session -- tests that specifically exercise ErrorReporter re-patch it locally instead."""
    monkeypatch.setattr(ErrorReporter, "report", lambda *a, **k: None)
