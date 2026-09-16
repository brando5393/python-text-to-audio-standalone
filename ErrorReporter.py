import hashlib
import json
import os
import subprocess
import threading

APP_DATA_DIR = os.path.join(os.path.expanduser("~"), ".texttoaudio")
REPORTED_PATH = os.path.join(APP_DATA_DIR, "reported_errors.json")
REPO = "brando5393/talebrew"
LABEL = "bug"
TITLE_MAX_CHARS = 100


def report(human_message, technical_detail):
    """Opens a GitHub issue for an application error, in the background.

    Uses the `gh` CLI rather than an embedded API token, so this only ever does anything
    on a machine where the developer has already run `gh auth login` themselves -- on
    anyone else's machine (e.g. someone who installed the packaged app) it silently does
    nothing instead of requiring a bundled credential, which would be a real way for a
    write-scoped GitHub token to leak out of a distributed app.

    Deduplicated by the error's own signature so a recurring bug opens exactly one issue
    ever, not one per occurrence -- a flaky error shouldn't flood the tracker.
    """
    threading.Thread(target=_report_worker, args=(human_message, technical_detail), daemon=True).start()


def _report_worker(human_message, technical_detail):
    try:
        signature = hashlib.sha256((technical_detail or human_message).encode("utf-8")).hexdigest()
        if _already_reported(signature):
            return

        title = _truncate(f"Error: {human_message.strip()}", TITLE_MAX_CHARS)
        body = "\n".join([
            "**Human-readable message**",
            "",
            human_message.strip() or "(none)",
            "",
            "**Error output**",
            "",
            "```",
            technical_detail.strip() or "(none)",
            "```",
            "",
            "*Filed automatically by Talebrew when this error occurred.*",
        ])

        result = subprocess.run(
            ["gh", "issue", "create", "--repo", REPO, "--title", title, "--body", body, "--label", LABEL],
            capture_output=True, text=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode == 0:
            _mark_reported(signature)
    except Exception:
        pass  # Best-effort only -- a failure reporting an error must never itself raise.


def _truncate(text, limit):
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _already_reported(signature):
    try:
        with open(REPORTED_PATH, "r", encoding="utf-8") as f:
            return signature in json.load(f)
    except (OSError, json.JSONDecodeError):
        return False


def _mark_reported(signature):
    seen = set()
    try:
        with open(REPORTED_PATH, "r", encoding="utf-8") as f:
            seen = set(json.load(f))
    except (OSError, json.JSONDecodeError):
        pass
    seen.add(signature)
    os.makedirs(APP_DATA_DIR, exist_ok=True)
    try:
        with open(REPORTED_PATH, "w", encoding="utf-8") as f:
            json.dump(sorted(seen), f)
    except OSError:
        pass
