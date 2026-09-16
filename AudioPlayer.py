import ctypes

_winmm = ctypes.windll.winmm
_ALIAS = "texttoaudio_player"


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
