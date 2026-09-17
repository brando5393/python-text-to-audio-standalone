import wave

from AudioPlayer import AudioPlayer, wav_duration_ms


def test_wav_duration_ms_reads_real_file(tmp_path):
    path = tmp_path / "sample.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * 16000 * 2)  # 2 seconds of silence
    assert wav_duration_ms(str(path)) == 2000


def test_wav_duration_ms_returns_zero_for_missing_file():
    assert wav_duration_ms(r"C:\does\not\exist.wav") == 0


def test_wav_duration_ms_returns_zero_for_non_wav_file(tmp_path):
    path = tmp_path / "not_a_wav.wav"
    path.write_bytes(b"this is not a wav file")
    assert wav_duration_ms(str(path)) == 0


def test_two_players_use_independent_mci_aliases(monkeypatch):
    """Regression: a second AudioPlayer instance (e.g. for previewing a voice in
    Settings) must not share the main player's MCI alias, or opening a file in one
    would silently steal control of (and stop) whatever the other had open."""
    commands = []

    def fake_send(self, command):
        commands.append(command)
        return 0, ""

    monkeypatch.setattr(AudioPlayer, "_send", fake_send)

    main_player = AudioPlayer()
    preview_player = AudioPlayer(alias="texttoaudio_preview")
    main_player.play(r"C:\main.wav")
    preview_player.play(r"C:\preview.mp3")

    assert any("alias texttoaudio_player" in c for c in commands)
    assert any("alias texttoaudio_preview" in c for c in commands)
    assert main_player.current_path() == r"C:\main.wav"
    assert preview_player.current_path() == r"C:\preview.mp3"


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


def test_pause_resume_seek_are_no_ops_when_nothing_is_loaded(monkeypatch):
    """Regression: pause/resume/seek must not send any MCI command at all before play()
    has ever been called -- sending one against an alias with nothing open would just
    return a harmless MCI error, but doing so unconditionally (e.g. from a stray
    keyboard-shortcut handler firing before a file is loaded) is still worth guarding
    against explicitly, since it's cheap to verify and easy to silently regress."""
    commands = []
    player = AudioPlayer()
    monkeypatch.setattr(player, "_send", lambda command: (commands.append(command), (0, ""))[1])

    player.pause()
    player.resume()
    player.seek_ms(5000)

    assert commands == []


def test_is_playing_position_and_length_are_zero_when_nothing_is_loaded(monkeypatch):
    player = AudioPlayer()
    monkeypatch.setattr(player, "_send", lambda command: (_ for _ in ()).throw(AssertionError("should not query MCI")))

    assert player.is_playing() is False
    assert player.position_ms() == 0
    assert player.length_ms() == 0


def test_stop_on_one_player_does_not_touch_the_other_players_alias(monkeypatch):
    """Regression: closing the main player must never send an MCI command against the
    preview player's alias (or vice versa) -- the two-alias split exists specifically so
    that stopping one can't silently steal control of, or close, the other."""
    commands = []

    def fake_send(self, command):
        commands.append(command)
        return 0, ""

    monkeypatch.setattr(AudioPlayer, "_send", fake_send)

    main_player = AudioPlayer()
    preview_player = AudioPlayer(alias="texttoaudio_preview")
    main_player.play(r"C:\main.wav")
    preview_player.play(r"C:\preview.mp3")
    commands.clear()

    main_player.stop()

    assert any("texttoaudio_player" in c for c in commands)
    assert not any("texttoaudio_preview" in c for c in commands)
    assert preview_player.current_path() == r"C:\preview.mp3"  # untouched


def test_play_raises_on_mci_open_failure(monkeypatch):
    """If MCI can't open the file at all (bad/missing device, corrupted file), play()
    must surface that as a clear error instead of silently pretending playback started."""
    player = AudioPlayer()
    monkeypatch.setattr(player, "_send", lambda command: (277, "") if command.startswith("open") else (0, ""))

    import pytest

    with pytest.raises(RuntimeError, match="Could not open audio file"):
        player.play(r"C:\bad.wav")
    assert player.current_path() is None


def test_play_quotes_path_containing_spaces_in_the_mci_command(monkeypatch):
    commands = []
    player = AudioPlayer()
    monkeypatch.setattr(player, "_send", lambda command: (commands.append(command), (0, ""))[1])

    player.play(r"C:\My Books\a long title.wav")

    open_cmd = next(c for c in commands if c.startswith("open"))
    assert '"C:\\My Books\\a long title.wav"' in open_cmd


def test_play_uses_mpegvideo_device_type_for_mp3_and_waveaudio_for_wav(monkeypatch):
    commands = []
    player = AudioPlayer()
    monkeypatch.setattr(player, "_send", lambda command: (commands.append(command), (0, ""))[1])

    player.play(r"C:\song.mp3")
    assert "type mpegvideo" in next(c for c in commands if c.startswith("open"))

    commands.clear()
    player.play(r"C:\book.wav")
    assert "type waveaudio" in next(c for c in commands if c.startswith("open"))
