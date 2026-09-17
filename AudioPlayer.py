import ctypes
import wave

_winmm = ctypes.windll.winmm
DEFAULT_ALIAS = "texttoaudio_player"


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

    def __init__(self, alias=DEFAULT_ALIAS):
        # A distinct alias lets a second player (e.g. Settings' voice preview) run
        # independently of the main one -- MCI aliases are OS-level, not scoped to the
        # Python object, so two players sharing one alias would each silently steal
        # control of (and stop) whatever the other had open.
        self._alias = alias
        self._current_path = None

    def _send(self, command):
        buf = ctypes.create_unicode_buffer(128)
        result = _winmm.mciSendStringW(command, buf, len(buf), None)
        return result, buf.value

    def _close(self):
        if self._current_path is not None:
            self._send(f"close {self._alias}")
            self._current_path = None

    def play(self, path):
        """Stops any current playback and starts playing `path` from the beginning."""
        self._close()
        device_type = "mpegvideo" if path.lower().endswith(".mp3") else "waveaudio"
        rc, _ = self._send(f'open "{path}" type {device_type} alias {self._alias}')
        if rc != 0:
            raise RuntimeError(f"Could not open audio file for playback (MCI error {rc}): {path}")
        self._current_path = path
        self._send(f"play {self._alias}")

    def pause(self):
        if self._current_path is not None:
            self._send(f"pause {self._alias}")

    def resume(self):
        if self._current_path is not None:
            self._send(f"resume {self._alias}")

    def stop(self):
        self._close()

    def current_path(self):
        return self._current_path

    def seek_ms(self, position_ms):
        if self._current_path is not None:
            self._send(f"seek {self._alias} to {int(position_ms)}")
            self._send(f"play {self._alias}")

    def is_playing(self):
        if self._current_path is None:
            return False
        _, mode = self._send(f"status {self._alias} mode")
        return mode == "playing"

    def position_ms(self):
        if self._current_path is None:
            return 0
        _, value = self._send(f"status {self._alias} position")
        return int(value) if value.isdigit() else 0

    def length_ms(self):
        if self._current_path is None:
            return 0
        _, value = self._send(f"status {self._alias} length")
        return int(value) if value.isdigit() else 0
