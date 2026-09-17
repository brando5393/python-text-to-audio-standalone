import json
import os

APP_DATA_DIR = os.path.join(os.path.expanduser("~"), ".texttoaudio")
POSITIONS_PATH = os.path.join(APP_DATA_DIR, "playback_positions.json")

# How close to either end counts as "not really partway through" -- a saved position
# inside the first few seconds isn't worth resuming into, and one inside the last few
# seconds means the file was essentially finished, not abandoned mid-listen.
RESUME_EDGE_MS = 5000


def save_position(path, position_ms):
    positions = _load()
    positions[path] = position_ms
    _save(positions)


def get_position(path):
    return _load().get(path)


def clear_position(path):
    positions = _load()
    if path in positions:
        del positions[path]
        _save(positions)


def is_resumable(position_ms, duration_ms):
    """Whether a saved position is worth offering to resume from, given the file's
    actual duration -- not right at the start, and not close enough to the end that the
    file was effectively already finished."""
    if not position_ms or position_ms < RESUME_EDGE_MS:
        return False
    if duration_ms and position_ms > duration_ms - RESUME_EDGE_MS:
        return False
    return True


def _load():
    try:
        with open(POSITIONS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _save(positions):
    os.makedirs(APP_DATA_DIR, exist_ok=True)
    tmp_path = POSITIONS_PATH + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(positions, f)
        os.replace(tmp_path, POSITIONS_PATH)
    except OSError:
        pass
