import os

import PiperEngine as pe


def test_voice_size_bytes_zero_when_not_installed(tmp_path, monkeypatch):
    monkeypatch.setattr(pe, "VOICES_DIR", str(tmp_path))
    assert pe.voice_size_bytes("nonexistent-voice") == 0


def test_voice_size_bytes_sums_both_files(tmp_path, monkeypatch):
    monkeypatch.setattr(pe, "VOICES_DIR", str(tmp_path))
    (tmp_path / "test-voice.onnx").write_bytes(b"x" * 100)
    (tmp_path / "test-voice.onnx.json").write_bytes(b"y" * 20)
    assert pe.voice_size_bytes("test-voice") == 120


def test_is_voice_installed_false_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(pe, "VOICES_DIR", str(tmp_path))
    assert pe.is_voice_installed("missing-voice") is False


def test_is_voice_installed_true_when_present(tmp_path, monkeypatch):
    monkeypatch.setattr(pe, "VOICES_DIR", str(tmp_path))
    (tmp_path / "present-voice.onnx").write_bytes(b"data")
    assert pe.is_voice_installed("present-voice") is True


def test_delete_voice_removes_both_files(tmp_path, monkeypatch):
    monkeypatch.setattr(pe, "VOICES_DIR", str(tmp_path))
    (tmp_path / "gone-voice.onnx").write_bytes(b"data")
    (tmp_path / "gone-voice.onnx.json").write_bytes(b"{}")
    pe.delete_voice("gone-voice")
    assert not os.path.exists(tmp_path / "gone-voice.onnx")
    assert not os.path.exists(tmp_path / "gone-voice.onnx.json")


def test_delete_voice_does_not_touch_other_voices(tmp_path, monkeypatch):
    monkeypatch.setattr(pe, "VOICES_DIR", str(tmp_path))
    (tmp_path / "keep-me.onnx").write_bytes(b"data")
    (tmp_path / "delete-me.onnx").write_bytes(b"data")
    pe.delete_voice("delete-me")
    assert os.path.exists(tmp_path / "keep-me.onnx")


def test_list_installed_voices_returns_sorted_ids(tmp_path, monkeypatch):
    monkeypatch.setattr(pe, "VOICES_DIR", str(tmp_path))
    (tmp_path / "zeta-voice.onnx").write_bytes(b"x")
    (tmp_path / "alpha-voice.onnx").write_bytes(b"x")
    (tmp_path / "alpha-voice.onnx.json").write_bytes(b"{}")
    assert pe.list_installed_voices() == ["alpha-voice", "zeta-voice"]


def test_list_installed_voices_empty_dir_returns_empty_list(tmp_path, monkeypatch):
    monkeypatch.setattr(pe, "VOICES_DIR", str(tmp_path / "does_not_exist"))
    assert pe.list_installed_voices() == []


def test_curated_voices_keys_and_paths_are_well_formed():
    assert len(pe.CURATED_VOICES) >= 20
    for label, voice_key in pe.CURATED_VOICES.items():
        assert isinstance(label, str) and label
        parts = voice_key.split("/")
        assert len(parts) == 5, f"expected lang/lang_region/speaker/quality/voice-id for {label!r}"
        lang, lang_region, speaker, quality, voice_id = parts
        assert voice_id == f"{lang_region}-{speaker}-{quality}"
