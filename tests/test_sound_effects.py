import os

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


def test_disabled_sound_effects_do_not_call_mci(tmp_path, monkeypatch):
    # A wall-clock timing assertion here would depend on real audio hardware being
    # present, which CI runners don't have (mciSendStringW returns near-instantly with
    # no sound device attached, the same as the disabled/no-op path) -- this failed on
    # GitHub Actions' windows-latest runner for exactly that reason. A call spy on the
    # MCI entry point itself is deterministic regardless of the environment's audio setup.
    monkeypatch.setattr(Config, "CONFIG_PATH", str(tmp_path / "config.json"))
    Config.save({**Config.DEFAULTS, "sound_effects_enabled": False})

    calls = []
    monkeypatch.setattr(sfx._winmm, "mciSendStringW", lambda *a, **k: calls.append(a) or 0)
    sfx.play("ready", blocking=True)
    assert calls == [], "disabled sound effects should never touch the MCI API"


def test_enabled_sound_effects_call_mci(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "CONFIG_PATH", str(tmp_path / "config.json"))
    Config.save({**Config.DEFAULTS, "sound_effects_enabled": True})

    calls = []
    monkeypatch.setattr(sfx._winmm, "mciSendStringW", lambda *a, **k: calls.append(a) or 0)
    sfx.play("ready", blocking=True)
    assert any("open" in str(c) for c in calls), "enabled playback should issue an MCI open command"
    assert any("play" in str(c) for c in calls), "enabled playback should issue an MCI play command"
