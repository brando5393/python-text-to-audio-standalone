from AudioPlayer import AudioPlayer


def test_current_path_is_none_before_playing():
    player = AudioPlayer()
    assert player.current_path() is None


def test_current_path_reflects_internal_state(monkeypatch):
    player = AudioPlayer()
    monkeypatch.setattr(player, "_send", lambda command: (0, ""))
    player.play(r"C:\some\file.wav")
    assert player.current_path() == r"C:\some\file.wav"
    player.stop()
    assert player.current_path() is None
