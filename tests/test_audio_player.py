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
