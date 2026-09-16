import ctypes
import os

import Config

_SOUNDS_DIR = os.path.join(os.path.dirname(__file__), "assets", "sounds")
_ALIAS = "texttoaudio_sfx"
_winmm = ctypes.windll.winmm

SOUNDS = {
    "ready": "ready.wav",
    "conversion_done": "conversion_done.wav",
    "error": "error.wav",
    "exit": "exit.wav",
}


def play(name, blocking=False):
    """Plays a short UI sound cue by name (see SOUNDS), unless disabled in Settings.

    Uses its own MCI alias, separate from AudioPlayer's, so a UI cue never interrupts
    (or gets interrupted by) whatever audiobook is currently playing. Failures are
    logged-worthy but never fatal -- a missing sound file or busy audio device shouldn't
    block using the app.
    """
    if not Config.load().get("sound_effects_enabled", True):
        return
    filename = SOUNDS.get(name)
    if filename is None:
        return
    path = os.path.join(_SOUNDS_DIR, filename)
    if not os.path.isfile(path):
        return

    try:
        _winmm.mciSendStringW(f"close {_ALIAS}", None, 0, None)  # in case a previous cue is still open
        rc = _winmm.mciSendStringW(f'open "{path}" type waveaudio alias {_ALIAS}', None, 0, None)
        if rc != 0:
            return
        command = f"play {_ALIAS} wait" if blocking else f"play {_ALIAS}"
        _winmm.mciSendStringW(command, None, 0, None)
        if blocking:
            _winmm.mciSendStringW(f"close {_ALIAS}", None, 0, None)
    except Exception:
        pass
