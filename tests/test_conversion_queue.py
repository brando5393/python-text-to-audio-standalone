import ConversionQueue


def test_save_and_load_round_trip(tmp_path, monkeypatch):
    pending_path = tmp_path / "pending_conversion.json"
    monkeypatch.setattr(ConversionQueue, "PENDING_PATH", str(pending_path))

    ConversionQueue.save(["a.txt", "b.pdf"], str(tmp_path / "out"))
    data = ConversionQueue.load()

    assert data["files"] == ["a.txt", "b.pdf"]
    assert data["output_dir"] == str(tmp_path / "out")


def test_load_returns_none_when_nothing_pending(tmp_path, monkeypatch):
    monkeypatch.setattr(ConversionQueue, "PENDING_PATH", str(tmp_path / "pending_conversion.json"))
    assert ConversionQueue.load() is None


def test_clear_removes_pending_state(tmp_path, monkeypatch):
    pending_path = tmp_path / "pending_conversion.json"
    monkeypatch.setattr(ConversionQueue, "PENDING_PATH", str(pending_path))

    ConversionQueue.save(["a.txt"], str(tmp_path / "out"))
    assert ConversionQueue.load() is not None

    ConversionQueue.clear()
    assert ConversionQueue.load() is None


def test_clear_is_safe_when_nothing_to_clear(tmp_path, monkeypatch):
    monkeypatch.setattr(ConversionQueue, "PENDING_PATH", str(tmp_path / "pending_conversion.json"))
    ConversionQueue.clear()  # must not raise


def test_load_returns_none_for_corrupted_file(tmp_path, monkeypatch):
    """A crash mid-write could in theory leave a corrupted pending_conversion.json
    behind -- on next launch this must be treated as "nothing to auto-resume" rather
    than raising and blocking the app from starting."""
    pending_path = tmp_path / "pending_conversion.json"
    monkeypatch.setattr(ConversionQueue, "PENDING_PATH", str(pending_path))
    pending_path.write_text("{not valid json", encoding="utf-8")

    assert ConversionQueue.load() is None


def test_load_returns_none_when_files_list_is_empty(tmp_path, monkeypatch):
    """An empty files list is not a usable pending batch (nothing to actually resume),
    even if the JSON itself is well-formed -- this can happen if a batch was saved right
    as its last file was removed from the queue."""
    pending_path = tmp_path / "pending_conversion.json"
    monkeypatch.setattr(ConversionQueue, "PENDING_PATH", str(pending_path))

    ConversionQueue.save([], str(tmp_path / "out"))
    assert ConversionQueue.load() is None


def test_save_and_load_round_trip_with_empty_output_dir_is_rejected(tmp_path, monkeypatch):
    """An empty output_dir string is falsy, so a batch saved with no destination folder
    must not be offered back as resumable -- there would be nowhere to write the files."""
    pending_path = tmp_path / "pending_conversion.json"
    monkeypatch.setattr(ConversionQueue, "PENDING_PATH", str(pending_path))

    ConversionQueue.save(["a.txt"], "")
    assert ConversionQueue.load() is None
