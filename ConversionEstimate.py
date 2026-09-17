"""Rough pre-conversion estimates shown in the Files to Convert pane -- how long a
file will roughly take to synthesize, before conversion actually starts. The real
conversion shows a live ETA recalculated from its own observed speed (see
ProgressDialog.py), which is always more accurate than this; this exists only to help
someone choose an engine/voice for a file before committing to converting it.

Throughput figures come from real measurements taken this project (not vendor specs):
pyttsx3 converted a ~700,000-character novel in under 3 minutes (README, native SAPI);
Piper "high"/"medium" tier voices took ~31s per 3000-character chunk on this ARM64
machine under x64 emulation; Piper "low" tier voices measured about 5x faster than
that for the same text. Actual speed varies with machine load and text content, so
this is presented as an approximation, not a guarantee.
"""

PYTTSX3_CHARS_PER_SEC = 700_000 / 180
PIPER_LOW_CHARS_PER_SEC = 3000 / (31 / 5)
PIPER_STANDARD_CHARS_PER_SEC = 3000 / 31


def estimate_seconds(char_count, engine, voice_id):
    """Rough estimated synthesis time in seconds for `char_count` characters of text
    with the given engine/voice."""
    if engine == "pyttsx3":
        rate = PYTTSX3_CHARS_PER_SEC
    elif voice_id and voice_id.endswith("-low"):
        rate = PIPER_LOW_CHARS_PER_SEC
    else:
        rate = PIPER_STANDARD_CHARS_PER_SEC
    return char_count / rate


def format_duration(seconds):
    """Formats a duration in seconds as a short human string, e.g. "45s", "3m 20s",
    "2h 15m" -- only as much precision as is useful at that scale."""
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    minutes, seconds = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {seconds}s" if seconds else f"{minutes}m"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m" if minutes else f"{hours}h"
