import time
import wave

import numpy as np
import pytest

import AudioPlayer as AudioPlayer_module
from AudioPlayer import AudioPlayer, wav_duration_ms


class FakeOutputStream:
    """Stands in for sounddevice.OutputStream so tests never touch real audio hardware
    -- required for this to run headless on GitHub's windows-latest CI runner, which has
    no real output device. Records enough (started/closed, the callback given to it) for
    tests to drive playback deterministically by calling AudioPlayer._audio_callback
    directly, the same way PortAudio's own audio thread would."""

    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.callback = kwargs.get("callback")
        self.started = False
        self.closed = False
        FakeOutputStream.instances.append(self)

    def start(self):
        self.started = True

    def stop(self):
        self.started = False

    def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def fake_stream(monkeypatch):
    FakeOutputStream.instances.clear()
    monkeypatch.setattr(AudioPlayer_module.sd, "OutputStream", FakeOutputStream)
    yield


def _make_wav(path, seconds=1.0, rate=8000, channels=1, freq=440.0):
    n = int(seconds * rate)
    t = np.arange(n) / rate
    tone = (0.3 * np.sin(2 * np.pi * freq * t) * 32767).astype(np.int16)
    if channels > 1:
        tone = np.tile(tone[:, None], (1, channels))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(tone.tobytes())
    return str(path)


def _wait_until(predicate, timeout=3.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return predicate()


# -- wav_duration_ms (unchanged behavior from the MCI-era player) --------------------


def test_wav_duration_ms_reads_real_file(tmp_path):
    path = _make_wav(tmp_path / "sample.wav", seconds=2.0, rate=16000)
    assert wav_duration_ms(path) == 2000


def test_wav_duration_ms_returns_zero_for_missing_file():
    assert wav_duration_ms(r"C:\does\not\exist.wav") == 0


def test_wav_duration_ms_returns_zero_for_non_wav_file(tmp_path):
    path = tmp_path / "not_a_wav.wav"
    path.write_bytes(b"this is not a wav file")
    assert wav_duration_ms(str(path)) == 0


# -- basic transport ------------------------------------------------------------------


def test_current_path_is_none_before_playing():
    player = AudioPlayer()
    assert player.current_path() is None


def test_play_sets_current_path_and_reports_length(tmp_path):
    path = _make_wav(tmp_path / "book.wav", seconds=1.0, rate=8000)
    player = AudioPlayer()
    player.play(path)
    try:
        assert player.current_path() == path
        assert player.length_ms() == 1000
        assert player.is_playing() is True
    finally:
        player.stop()


def test_stop_clears_current_path(tmp_path):
    path = _make_wav(tmp_path / "book.wav")
    player = AudioPlayer()
    player.play(path)
    player.stop()
    assert player.current_path() is None
    assert player.is_playing() is False


def test_pause_stops_the_stream_and_resume_restarts_it(tmp_path):
    path = _make_wav(tmp_path / "book.wav")
    player = AudioPlayer()
    player.play(path)
    try:
        stream = FakeOutputStream.instances[-1]
        assert stream.started is True
        player.pause()
        assert stream.started is False
        assert player.is_playing() is False
        player.resume()
        assert stream.started is True
        assert player.is_playing() is True
    finally:
        player.stop()


def test_pause_resume_seek_are_no_ops_when_nothing_is_loaded():
    player = AudioPlayer()
    player.pause()
    player.resume()
    player.seek_ms(5000)
    assert player.is_playing() is False
    assert player.position_ms() == 0
    assert player.length_ms() == 0


def test_seek_updates_reported_position(tmp_path):
    path = _make_wav(tmp_path / "book.wav", seconds=4.0, rate=8000)
    player = AudioPlayer()
    player.play(path)
    try:
        player.seek_ms(2500)
        assert player.position_ms() == 2500
    finally:
        player.stop()


def test_seek_resumes_playback_if_paused(tmp_path):
    path = _make_wav(tmp_path / "book.wav", seconds=4.0, rate=8000)
    player = AudioPlayer()
    player.play(path)
    player.pause()
    assert player.is_playing() is False
    player.seek_ms(1000)
    assert player.is_playing() is True
    player.stop()


def test_play_raises_for_a_file_that_is_not_a_wav_or_recognized_audio_format(tmp_path):
    bad = tmp_path / "bad.wav"
    bad.write_bytes(b"not really audio")
    player = AudioPlayer()
    with pytest.raises(Exception):
        player.play(str(bad))


# -- speed / tone -----------------------------------------------------------------------


def test_set_speed_clamps_to_supported_range():
    player = AudioPlayer()
    player.set_speed(10)
    assert player.get_speed() == 2.5
    player.set_speed(0.01)
    assert player.get_speed() == 0.5


def test_set_tone_clamps_to_supported_range():
    player = AudioPlayer()
    player.set_tone(30)
    assert player.get_tone() == 6.0
    player.set_tone(-30)
    assert player.get_tone() == -6.0


def test_default_speed_and_tone_are_neutral():
    player = AudioPlayer()
    assert player.get_speed() == 1.0
    assert player.get_tone() == 0.0


def test_set_speed_while_playing_resets_the_buffer_to_the_current_position(tmp_path):
    """Regression: an in-progress speed/tone change must take effect immediately on
    already-buffered-but-unheard audio, not only once it finishes playing -- so changing
    it drops anything produced-but-not-yet-heard and restarts production from exactly
    what's currently audible, using the new value."""
    path = _make_wav(tmp_path / "book.wav", seconds=3.0, rate=8000)
    player = AudioPlayer()
    player.play(path)
    try:
        assert _wait_until(lambda: player._produced_output_frames > 0)
        player.set_speed(1.8)
        assert player.get_speed() == 1.8
        assert player._produce_from == player._heard_source_frame
        assert len(player._chunks) == 0
    finally:
        player.stop()


def test_set_tone_while_playing_resets_the_buffer_to_the_current_position(tmp_path):
    path = _make_wav(tmp_path / "book.wav", seconds=3.0, rate=8000)
    player = AudioPlayer()
    player.play(path)
    try:
        assert _wait_until(lambda: player._produced_output_frames > 0)
        player.set_tone(4.0)
        assert player.get_tone() == 4.0
        assert player._produce_from == player._heard_source_frame
        assert len(player._chunks) == 0
    finally:
        player.stop()


def test_playback_produces_and_delivers_real_audio(tmp_path):
    """End-to-end: the producer thread actually runs AudioStretch on real WAV samples
    and the audio callback actually delivers non-silent frames -- not just that the
    plumbing doesn't crash."""
    path = _make_wav(tmp_path / "book.wav", seconds=2.0, rate=8000)
    player = AudioPlayer()
    player.play(path)
    try:
        assert _wait_until(lambda: player._produced_output_frames > 200)
        outdata = np.zeros((200, 1), dtype=np.float32)
        player._audio_callback(outdata, 200, None, None)
        assert np.abs(outdata).max() > 0.0
    finally:
        player.stop()


# -- multi-instance isolation (the property the MCI-alias split used to guarantee) ----


def test_two_independent_players_do_not_share_state(tmp_path):
    path_a = _make_wav(tmp_path / "a.wav", seconds=2.0, rate=8000)
    path_b = _make_wav(tmp_path / "b.wav", seconds=3.0, rate=8000)

    main_player = AudioPlayer()
    preview_player = AudioPlayer(alias="texttoaudio_preview")
    assert main_player._alias != preview_player._alias

    main_player.play(path_a)
    preview_player.play(path_b)
    try:
        assert main_player.current_path() == path_a
        assert preview_player.current_path() == path_b
        assert main_player.length_ms() == 2000
        assert preview_player.length_ms() == 3000

        main_player.set_speed(1.5)
        assert preview_player.get_speed() == 1.0  # untouched by the other player

        main_player.stop()
        assert main_player.current_path() is None
        assert preview_player.current_path() == path_b  # untouched by stopping the other
    finally:
        preview_player.stop()


def test_two_players_get_independent_output_streams(tmp_path):
    path_a = _make_wav(tmp_path / "a.wav")
    path_b = _make_wav(tmp_path / "b.wav")
    main_player = AudioPlayer()
    preview_player = AudioPlayer(alias="texttoaudio_preview")
    main_player.play(path_a)
    preview_player.play(path_b)
    try:
        assert len(FakeOutputStream.instances) == 2
        assert FakeOutputStream.instances[0] is not FakeOutputStream.instances[1]
    finally:
        main_player.stop()
        preview_player.stop()
