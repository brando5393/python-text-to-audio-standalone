import json
import os
import uuid

APP_DATA_DIR = os.path.join(os.path.expanduser("~"), ".texttoaudio")
BOOKMARKS_PATH = os.path.join(APP_DATA_DIR, "bookmarks.json")

# {path: [{"id": ..., "name": ..., "position_ms": ...}, ...]}, following the same
# JSON-backed, atomic-write, corrupted-file-is-empty pattern as PlaybackMemory.py --
# a distinct file/module because a bookmark is a *named*, multi-per-file marker the
# user creates on purpose, not the single silent auto-resume position PlaybackMemory
# tracks, and conflating the two would mean a bookmark jump could stomp -- or be
# stomped by -- the auto-resume position, and vice versa.


def add_bookmark(path, name, position_ms):
    """Adds a new named bookmark for `path` and returns its id (needed to delete this
    exact bookmark later, since names aren't required to be unique)."""
    bookmarks = _load()
    entry_id = uuid.uuid4().hex
    bookmarks.setdefault(path, []).append({"id": entry_id, "name": name, "position_ms": int(position_ms)})
    _save(bookmarks)
    return entry_id


def list_bookmarks(path):
    """Returns this file's bookmarks in the order they were added, or [] if none."""
    return list(_load().get(path, []))


def delete_bookmark(path, bookmark_id):
    bookmarks = _load()
    entries = bookmarks.get(path)
    if not entries:
        return
    remaining = [b for b in entries if b["id"] != bookmark_id]
    if len(remaining) == len(entries):
        return  # nothing matched -- no-op rather than an error, same spirit as clear_position()
    if remaining:
        bookmarks[path] = remaining
    else:
        del bookmarks[path]
    _save(bookmarks)


def _load():
    try:
        with open(BOOKMARKS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _save(bookmarks):
    os.makedirs(APP_DATA_DIR, exist_ok=True)
    tmp_path = BOOKMARKS_PATH + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(bookmarks, f)
        os.replace(tmp_path, BOOKMARKS_PATH)
    except OSError:
        pass
