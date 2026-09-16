import logging

import pytest
import ttkbootstrap as ttk

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
