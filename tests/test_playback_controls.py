import Config
import PlaybackControls
from PlaybackControls import SPEED_BANDS, TONE_BANDS, band_label


class FakePlayer:
    def __init__(self):
        self.speed_calls = []
        self.tone_calls = []

    def set_speed(self, multiplier):
        self.speed_calls.append(multiplier)

    def set_tone(self, semitones):
        self.tone_calls.append(semitones)


def test_band_label_covers_the_full_speed_range():
    assert band_label(0.5, SPEED_BANDS) == "Slower"
    assert band_label(0.8, SPEED_BANDS) == "Slightly slower"
    assert band_label(1.0, SPEED_BANDS) == "Normal"
    assert band_label(1.3, SPEED_BANDS) == "Slightly faster"
    assert band_label(2.0, SPEED_BANDS) == "Faster"


def test_band_label_covers_the_full_tone_range():
    assert band_label(-5.0, TONE_BANDS) == "Deeper"
    assert band_label(-1.0, TONE_BANDS) == "Slightly deeper"
    assert band_label(0.0, TONE_BANDS) == "Normal"
    assert band_label(2.0, TONE_BANDS) == "Slightly higher"
    assert band_label(5.0, TONE_BANDS) == "Higher"


def test_build_applies_persisted_defaults_to_the_player_immediately(tk_root, tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "CONFIG_PATH", str(tmp_path / "config.json"))
    current = Config.load()
    current["playback_speed"] = 1.4
    current["playback_tone"] = -2.0
    Config.save(current)

    player = FakePlayer()
    frame = PlaybackControls.build(tk_root, player)
    try:
        assert player.speed_calls[-1] == 1.4
        assert player.tone_calls[-1] == -2.0
    finally:
        frame.destroy()


def test_moving_the_speed_slider_updates_the_player_and_persists(tk_root, tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "CONFIG_PATH", str(tmp_path / "config.json"))
    Config.save(dict(Config.DEFAULTS))

    player = FakePlayer()
    frame = PlaybackControls.build(tk_root, player)
    try:
        frame.speed_var.set(1.7)
        assert player.speed_calls[-1] == 1.7
        assert Config.load()["playback_speed"] == 1.7
    finally:
        frame.destroy()


def test_moving_the_tone_slider_updates_the_player_and_persists(tk_root, tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "CONFIG_PATH", str(tmp_path / "config.json"))
    Config.save(dict(Config.DEFAULTS))

    player = FakePlayer()
    frame = PlaybackControls.build(tk_root, player)
    try:
        frame.tone_var.set(3.0)
        assert player.tone_calls[-1] == 3.0
        assert Config.load()["playback_tone"] == 3.0
    finally:
        frame.destroy()
