import ctypes
import wave

_winmm = ctypes.windll.winmm
_ALIAS = "texttoaudio_player"


def wav_duration_ms(path):
    """Reads a WAV file's duration without opening it for playback -- used to decide
    whether a saved playback position is worth offering to resume from, before MCI is
    ever involved. Returns 0 if the file can't be read as a WAV (wrong format, missing)."""
    try:
        with wave.open(path, "rb") as wav_file:
            return int(1000 * wav_file.getnframes() / wav_file.getframerate())
    except (wave.Error, OSError, ZeroDivisionError):
        return 0


class AudioPlayer:
    """Thin wrapper around the Windows MCI API for WAV/MP3 playback with transport controls.

    Uses ctypes against winmm.dll instead of a third-party package because this app
    targets Windows, and audio libraries like pygame/simpleaudio publish no Windows-ARM64
    wheels, while MCI ships in every Windows install and needs no dependency at all.
    """

    def __init__(self):
        self._current_path = None

    def _send(self, command):
        buf = ctypes.create_unicode_buffer(128)
        result = _winmm.mciSendStringW(command, buf, len(buf), None)
        return result, buf.value

    def _close(self):
        if self._current_path is not None:
            self._send(f"close {_ALIAS}")
            self._current_path = None

    def play(self, path):
        """Stops any current playback and starts playing `path` from the beginning."""
        self._close()
        device_type = "mpegvideo" if path.lower().endswith(".mp3") else "waveaudio"
        rc, _ = self._send(f'open "{path}" type {device_type} alias {_ALIAS}')
        if rc != 0:
            raise RuntimeError(f"Could not open audio file for playback (MCI error {rc}): {path}")
        self._current_path = path
        self._send(f"play {_ALIAS}")

    def pause(self):
        if self._current_path is not None:
            self._send(f"pause {_ALIAS}")

    def resume(self):
        if self._current_path is not None:
            self._send(f"resume {_ALIAS}")

    def stop(self):
        self._close()

    def current_path(self):
        return self._current_path

    def seek_ms(self, position_ms):
        if self._current_path is not None:
            self._send(f"seek {_ALIAS} to {int(position_ms)}")
            self._send(f"play {_ALIAS}")

    def is_playing(self):
        if self._current_path is None:
            return False
        _, mode = self._send(f"status {_ALIAS} mode")
        return mode == "playing"

    def position_ms(self):
        if self._current_path is None:
            return 0
        _, value = self._send(f"status {_ALIAS} position")
        return int(value) if value.isdigit() else 0

    def length_ms(self):
        if self._current_path is None:
            return 0
        _, value = self._send(f"status {_ALIAS} length")
        return int(value) if value.isdigit() else 0
