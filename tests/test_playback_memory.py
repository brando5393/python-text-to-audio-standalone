import PlaybackMemory as pm


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "APP_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(pm, "POSITIONS_PATH", str(tmp_path / "playback_positions.json"))


def test_save_and_get_position_round_trip(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    pm.save_position(r"C:\Books\a.wav", 12345)
    assert pm.get_position(r"C:\Books\a.wav") == 12345


def test_positions_are_tracked_independently_per_file(tmp_path, monkeypatch):
    """Regression: saving progress for one file must never affect, or be confused
    with, another file's own saved position."""
    _isolate(tmp_path, monkeypatch)
    pm.save_position(r"C:\Books\a.wav", 10000)
    pm.save_position(r"C:\Books\b.wav", 90000)

    assert pm.get_position(r"C:\Books\a.wav") == 10000
    assert pm.get_position(r"C:\Books\b.wav") == 90000

    pm.save_position(r"C:\Books\a.wav", 15000)
    assert pm.get_position(r"C:\Books\a.wav") == 15000
    assert pm.get_position(r"C:\Books\b.wav") == 90000  # untouched by updating a's position


def test_get_position_returns_none_when_never_saved(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    assert pm.get_position(r"C:\Books\never_played.wav") is None


def test_clear_position_removes_only_that_file(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    pm.save_position(r"C:\Books\a.wav", 10000)
    pm.save_position(r"C:\Books\b.wav", 20000)

    pm.clear_position(r"C:\Books\a.wav")

    assert pm.get_position(r"C:\Books\a.wav") is None
    assert pm.get_position(r"C:\Books\b.wav") == 20000


def test_clear_position_is_safe_when_nothing_saved(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    pm.clear_position(r"C:\Books\a.wav")  # must not raise


def test_is_resumable_false_when_no_saved_position():
    assert pm.is_resumable(None, 100000) is False
    assert pm.is_resumable(0, 100000) is False


def test_is_resumable_false_near_the_start():
    assert pm.is_resumable(2000, 100000) is False


def test_is_resumable_false_near_the_end():
    assert pm.is_resumable(98000, 100000) is False


def test_is_resumable_true_partway_through():
    assert pm.is_resumable(50000, 100000) is True


def test_is_resumable_true_when_duration_unknown():
    # Duration might not be readable for some reason -- still resumable as long as the
    # saved position itself is clearly past the start.
    assert pm.is_resumable(50000, 0) is True
