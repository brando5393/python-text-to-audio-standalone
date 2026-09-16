import json
import os

APP_DATA_DIR = os.path.join(os.path.expanduser("~"), ".texttoaudio")
PENDING_PATH = os.path.join(APP_DATA_DIR, "pending_conversion.json")


def save(files, output_dir):
    """Records an in-progress batch so it can be automatically resumed on next launch
    if the app closes, or crashes, before the batch finishes. Cleared once the batch
    completes (see clear())."""
    os.makedirs(APP_DATA_DIR, exist_ok=True)
    try:
        with open(PENDING_PATH, "w", encoding="utf-8") as f:
            json.dump({"files": list(files), "output_dir": output_dir}, f)
    except OSError:
        pass  # Losing this just means an interrupted batch won't auto-resume -- not fatal.


def clear():
    try:
        os.remove(PENDING_PATH)
    except OSError:
        pass


def load():
    """Returns {"files": [...], "output_dir": ...} left over from an interrupted batch,
    or None if there isn't one."""
    try:
        with open(PENDING_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    if not data.get("files") or not data.get("output_dir"):
        return None
    return data
