import logging
import logging.handlers
import os
import queue

LOG_DIR = os.path.join(os.path.expanduser("~"), ".texttoaudio")
LOG_FILE = os.path.join(LOG_DIR, "texttoaudio.log")

LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warn": logging.WARNING,
    "alert": logging.WARNING,
    "error": logging.ERROR,
}

LEVEL_COLORS = {
    logging.DEBUG: "#888888",
    logging.INFO: "#1c1c1c",
    logging.WARNING: "#a9720c",
    logging.ERROR: "#b3261e",
}

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
        self.out_queue.put((self.format(record), LEVEL_COLORS.get(record.levelno, "#1c1c1c")))


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
