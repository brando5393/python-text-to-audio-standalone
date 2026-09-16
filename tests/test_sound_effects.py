import os
import time

import Config
import SoundEffects as sfx


def test_all_sound_files_exist_and_are_valid_wav():
    import wave
    for name, filename in sfx.SOUNDS.items():
        path = os.path.join(sfx._SOUNDS_DIR, filename)
        assert os.path.isfile(path), f"missing sound file for {name!r}: {path}"
        with wave.open(path, "rb") as w:
            assert w.getnframes() > 0
            assert w.getnframes() / w.getframerate() < 2.0, f"{name} is suspiciously long for a UI cue"


def test_unknown_sound_name_is_a_no_op():
    sfx.play("not-a-real-sound", blocking=True)  # should not raise


def test_disabled_sound_effects_do_not_play(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "CONFIG_PATH", str(tmp_path / "config.json"))
    Config.save({**Config.DEFAULTS, "sound_effects_enabled": False})

    t0 = time.time()
    sfx.play("ready", blocking=True)
    elapsed = time.time() - t0
    assert elapsed < 0.1, "disabled sound effects should be an instant no-op"


def test_enabled_sound_effects_actually_play(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "CONFIG_PATH", str(tmp_path / "config.json"))
    Config.save({**Config.DEFAULTS, "sound_effects_enabled": True})

    t0 = time.time()
    sfx.play("ready", blocking=True)
    elapsed = time.time() - t0
    assert elapsed > 0.3, "enabled playback should take roughly the sound's real duration"
