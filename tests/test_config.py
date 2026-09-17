import Config


def test_load_returns_defaults_when_no_file_exists(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "CONFIG_PATH", str(tmp_path / "config.json"))
    assert Config.load() == Config.DEFAULTS


def test_save_then_load_round_trips(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "CONFIG_PATH", str(tmp_path / "config.json"))
    settings = {
        "engine": "piper", "voice": "en_US-ryan-high", "playback_speed": 1.5, "playback_tone": 2.0,
        "large_text": True, "sound_effects_enabled": False, "start_in_mini_mode": True,
        "auto_pause_for_other_audio": True,
    }
    Config.save(settings)
    assert Config.load() == settings


def test_save_requires_every_default_key(tmp_path, monkeypatch):
    """Config.save() writes exactly the DEFAULTS keys -- a caller that omits one (as an
    earlier version of SettingsDrawer's _save() did when large_text was added to DEFAULTS
    without updating it) should fail loudly rather than silently drop a setting."""
    import pytest
    monkeypatch.setattr(Config, "CONFIG_PATH", str(tmp_path / "config.json"))
    incomplete = {"engine": "piper", "voice": "en_US-amy-medium", "playback_speed": 1.0}
    with pytest.raises(KeyError):
        Config.save(incomplete)


def test_load_ignores_corrupt_file(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    path.write_text("not valid json", encoding="utf-8")
    monkeypatch.setattr(Config, "CONFIG_PATH", str(path))
    assert Config.load() == Config.DEFAULTS


def test_load_merges_partial_file_with_defaults(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    path.write_text('{"engine": "pyttsx3"}', encoding="utf-8")
    monkeypatch.setattr(Config, "CONFIG_PATH", str(path))
    result = Config.load()
    assert result["engine"] == "pyttsx3"
    assert result["voice"] == Config.DEFAULTS["voice"]


def test_auto_pause_for_other_audio_defaults_off(tmp_path, monkeypatch):
    """A behavior change some users won't want (auto-pausing during calls/notifications)
    must never turn itself on for someone who never opted in -- matching the same
    cautious-default convention as large_text."""
    monkeypatch.setattr(Config, "CONFIG_PATH", str(tmp_path / "config.json"))
    assert Config.load()["auto_pause_for_other_audio"] is False
    assert Config.DEFAULTS["auto_pause_for_other_audio"] is False


def test_auto_pause_for_other_audio_persists_when_enabled(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "CONFIG_PATH", str(tmp_path / "config.json"))
    settings = dict(Config.DEFAULTS)
    settings["auto_pause_for_other_audio"] = True
    Config.save(settings)
    assert Config.load()["auto_pause_for_other_audio"] is True


def test_load_ignores_unknown_keys(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    path.write_text('{"engine": "piper", "made_up_key": "surprise"}', encoding="utf-8")
    monkeypatch.setattr(Config, "CONFIG_PATH", str(path))
    result = Config.load()
    assert "made_up_key" not in result
