"""Generates short, warm UI sound cues (app ready, conversion done, error, exit) as WAV
files. Uses simple additive sine synthesis with an attack/release envelope so tones don't
click at the edges -- no audio library needed, just the stdlib `wave` and `math` modules.

Run manually when these need to change: `poetry run python scripts/generate_sounds.py`
"""

import math
import os
import struct
import wave

SOUNDS_DIR = os.path.join(os.path.dirname(__file__), "..", "assets", "sounds")
SAMPLE_RATE = 22050


def _note(freq, duration, volume=0.3, fade=0.02):
    """One sine tone with a short fade-in/out envelope (avoids clicks at the edges)."""
    n_samples = int(SAMPLE_RATE * duration)
    fade_samples = max(1, int(SAMPLE_RATE * fade))
    samples = []
    for i in range(n_samples):
        t = i / SAMPLE_RATE
        envelope = 1.0
        if i < fade_samples:
            envelope = i / fade_samples
        elif i > n_samples - fade_samples:
            envelope = (n_samples - i) / fade_samples
        value = volume * envelope * math.sin(2 * math.pi * freq * t)
        samples.append(value)
    return samples


def _mix(*sample_lists):
    """Concatenates sequential notes and/or overlays simultaneous ones (lists of equal
    length passed together are summed; pass them as separate positional args to overlay,
    or already-concatenated lists to sequence)."""
    length = max(len(s) for s in sample_lists)
    out = [0.0] * length
    for s in sample_lists:
        for i, v in enumerate(s):
            out[i] += v
    peak = max((abs(v) for v in out), default=1.0)
    if peak > 1.0:
        out = [v / peak for v in out]
    return out


def _save(samples, path):
    with wave.open(path, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SAMPLE_RATE)
        frames = b"".join(struct.pack("<h", int(v * 32767)) for v in samples)
        f.writeframes(frames)


# A warm major triad (like a soft coffee-cup "ting") built from the coffee-house theme's
# implied key rather than a generic digital beep: C5-E5-G5, arpeggiated gently.
def sound_ready():
    c5 = _note(523.25, 0.14, volume=0.25)
    e5 = _note(659.25, 0.14, volume=0.25)
    g5 = _note(783.99, 0.22, volume=0.25)
    silence1 = [0.0] * int(SAMPLE_RATE * 0.03)
    silence2 = [0.0] * int(SAMPLE_RATE * 0.03)
    return c5 + silence1 + e5 + silence2 + g5


def sound_conversion_done():
    # A brighter two-note "done!" -- rising fifth, slightly quicker than the ready chime.
    g5 = _note(783.99, 0.10, volume=0.28)
    c6 = _note(1046.50, 0.20, volume=0.28)
    silence = [0.0] * int(SAMPLE_RATE * 0.02)
    return g5 + silence + c6


def sound_error():
    # A soft, low two-note dip -- noticeable but not alarming (no harsh buzzer).
    a4 = _note(440.0, 0.12, volume=0.25)
    f4 = _note(349.23, 0.22, volume=0.25)
    silence = [0.0] * int(SAMPLE_RATE * 0.02)
    return a4 + silence + f4


def sound_exit():
    # A gentle descending close, mirroring the ready chime's triad in reverse.
    g5 = _note(783.99, 0.13, volume=0.25)
    e5 = _note(659.25, 0.13, volume=0.25)
    c5 = _note(523.25, 0.20, volume=0.25)
    silence1 = [0.0] * int(SAMPLE_RATE * 0.03)
    silence2 = [0.0] * int(SAMPLE_RATE * 0.03)
    return g5 + silence1 + e5 + silence2 + c5


def main():
    os.makedirs(SOUNDS_DIR, exist_ok=True)
    sounds = {
        "ready.wav": sound_ready(),
        "conversion_done.wav": sound_conversion_done(),
        "error.wav": sound_error(),
        "exit.wav": sound_exit(),
    }
    for filename, samples in sounds.items():
        _save(samples, os.path.join(SOUNDS_DIR, filename))
        print("wrote", filename)


if __name__ == "__main__":
    main()
