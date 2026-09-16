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
