import logging
import logging.handlers
import os
import queue

import ErrorReporter

LOG_DIR = os.path.join(os.path.expanduser("~"), ".texttoaudio")
LOG_FILE = os.path.join(LOG_DIR, "texttoaudio.log")

LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warn": logging.WARNING,
    "alert": logging.WARNING,
    "error": logging.ERROR,
}

# One palette per theme, not one hardcoded set -- these used to be a single dict that
# was only ever checked against the light theme (see the old WARNING comment, "5.45:1
# contrast on the light theme bg"). Measured against the dark theme's real input
# background, INFO came out at just 1.09:1 (near-black text on a near-black background --
# effectively invisible) and WARNING/ERROR both fell below 2.5:1. Each shade below is
# individually verified >=4.5:1 against its own theme's input background; see
# test_log_manager.py.
LEVEL_COLORS_LIGHT = {
    logging.DEBUG: "#696969",
    logging.INFO: "#3b2a1e",  # the light theme's own default text color
    logging.WARNING: "#7a561d",
    logging.ERROR: "#b3261e",
}
LEVEL_COLORS_DARK = {
    logging.DEBUG: "#8a8a8a",
    logging.INFO: "#f2e8d9",  # the dark theme's own default text color
    logging.WARNING: "#b7812b",
    logging.ERROR: "#e35f57",
}

_dark_mode = False  # kept in sync via set_dark_mode(); matches the app's own default
# starting theme (coffeehouse-light) so colors are right from first launch.


def set_dark_mode(dark):
    """Keeps the log's per-level colors in sync with the active theme. A plain module
    global (not a Tk call) so it's safe to read from _QueueHandler.emit(), which may run
    on a background conversion thread via add_event()."""
    global _dark_mode
    _dark_mode = dark


def _current_level_colors():
    return LEVEL_COLORS_DARK if _dark_mode else LEVEL_COLORS_LIGHT


POLL_INTERVAL_MS = 150


class _QueueHandler(logging.Handler):
    """Puts formatted records on a plain thread-safe queue.

    add_event() may be called from a background conversion thread, but Tk widgets (and
    even widget.after()) may only safely be touched from the main thread. This handler
    does no Tk work at all; LogManager drains the queue from a main-thread-owned poll loop.
    """

    def __init__(self, out_queue):
        super().__init__()
        self.out_queue = out_queue

    def emit(self, record):
        colors = _current_level_colors()
        self.out_queue.put((self.format(record), colors.get(record.levelno, colors[logging.INFO])))


class LogManager:
    """Application-wide logging: rotating log file on disk plus a live, color-coded on-screen feed."""

    def __init__(self, app_log_display, level="info", max_rows=500):
        os.makedirs(LOG_DIR, exist_ok=True)
        self.app_log_display = app_log_display
        self.max_rows = max_rows
        self._display_queue = queue.Queue()

        self.logger = logging.getLogger("texttoaudio")
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False

        if not self.logger.handlers:
            file_handler = logging.handlers.RotatingFileHandler(
                LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
            )
            file_handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s | %(message)s"))
            self.logger.addHandler(file_handler)

            display_handler = _QueueHandler(self._display_queue)
            display_handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s | %(message)s", "%H:%M:%S"))
            self.logger.addHandler(display_handler)

        self.logger.setLevel(LEVELS.get(level, logging.INFO))

        # Scheduled here (main thread, at construction time) and re-scheduled only from
        # within its own callback, so the Tk API is never touched off the main thread.
        self.app_log_display.after(POLL_INTERVAL_MS, self._poll_display_queue)

    def _poll_display_queue(self):
        try:
            while True:
                message, color = self._display_queue.get_nowait()
                self.app_log_display.insert("end", message)
                index = self.app_log_display.size() - 1
                self.app_log_display.itemconfigure(index, foreground=color)
                self.app_log_display.see(index)
            overflow = self.app_log_display.size() - self.max_rows
            if overflow > 0:
                self.app_log_display.delete(0, overflow - 1)
        except queue.Empty:
            pass
        except Exception:
            # The display widget may already be destroyed during shutdown.
            return
        self.app_log_display.after(POLL_INTERVAL_MS, self._poll_display_queue)

    def add_event(self, status, msg, err=""):
        """Log an event. `status` is one of debug/info/warn/alert/error for backward compatibility."""
        level = LEVELS.get(status.lower(), logging.INFO)
        full_message = f"{msg.strip()}" + (f" | {err.strip()}" if err and err.strip() else "")
        self.logger.log(level, full_message)
        if status.lower() == "error":
            ErrorReporter.report(msg, err)
