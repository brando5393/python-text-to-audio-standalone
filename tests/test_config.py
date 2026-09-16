import Config


def test_load_returns_defaults_when_no_file_exists(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "CONFIG_PATH", str(tmp_path / "config.json"))
    assert Config.load() == Config.DEFAULTS


def test_save_then_load_round_trips(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "CONFIG_PATH", str(tmp_path / "config.json"))
    settings = {"engine": "piper", "voice": "en_US-ryan-high", "speed": 1.5, "expressiveness": 0.8}
    Config.save(settings)
    assert Config.load() == settings


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


def test_load_ignores_unknown_keys(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    path.write_text('{"engine": "piper", "made_up_key": "surprise"}', encoding="utf-8")
    monkeypatch.setattr(Config, "CONFIG_PATH", str(path))
    result = Config.load()
    assert "made_up_key" not in result
