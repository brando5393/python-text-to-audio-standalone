import Bookmarks as bm


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(bm, "APP_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(bm, "BOOKMARKS_PATH", str(tmp_path / "bookmarks.json"))


def test_add_and_list_round_trip(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    bm.add_bookmark(r"C:\Books\a.wav", "Chapter 2", 65000)
    entries = bm.list_bookmarks(r"C:\Books\a.wav")
    assert len(entries) == 1
    assert entries[0]["name"] == "Chapter 2"
    assert entries[0]["position_ms"] == 65000
    assert entries[0]["id"]  # a non-empty id was assigned


def test_add_bookmark_returns_its_id(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    entry_id = bm.add_bookmark(r"C:\Books\a.wav", "Start", 0)
    entries = bm.list_bookmarks(r"C:\Books\a.wav")
    assert entries[0]["id"] == entry_id


def test_multiple_bookmarks_per_file_keep_insertion_order(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    bm.add_bookmark(r"C:\Books\a.wav", "Intro", 0)
    bm.add_bookmark(r"C:\Books\a.wav", "Chapter 2", 65000)
    bm.add_bookmark(r"C:\Books\a.wav", "Cliffhanger", 120000)

    names = [b["name"] for b in bm.list_bookmarks(r"C:\Books\a.wav")]
    assert names == ["Intro", "Chapter 2", "Cliffhanger"]


def test_bookmarks_are_tracked_independently_per_file(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    bm.add_bookmark(r"C:\Books\a.wav", "A's mark", 1000)
    bm.add_bookmark(r"C:\Books\b.wav", "B's mark", 2000)

    assert [e["name"] for e in bm.list_bookmarks(r"C:\Books\a.wav")] == ["A's mark"]
    assert [e["name"] for e in bm.list_bookmarks(r"C:\Books\b.wav")] == ["B's mark"]


def test_list_bookmarks_returns_empty_list_when_none_saved(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    assert bm.list_bookmarks(r"C:\Books\never.wav") == []


def test_delete_bookmark_removes_only_that_entry(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    keep_id = bm.add_bookmark(r"C:\Books\a.wav", "Keep me", 1000)
    remove_id = bm.add_bookmark(r"C:\Books\a.wav", "Remove me", 2000)

    bm.delete_bookmark(r"C:\Books\a.wav", remove_id)

    entries = bm.list_bookmarks(r"C:\Books\a.wav")
    assert len(entries) == 1
    assert entries[0]["id"] == keep_id


def test_delete_bookmark_removes_empty_file_entry_entirely(tmp_path, monkeypatch):
    """Once a file's last bookmark is deleted, its key should be gone from storage
    entirely rather than left behind as an empty list."""
    _isolate(tmp_path, monkeypatch)
    entry_id = bm.add_bookmark(r"C:\Books\a.wav", "Only one", 1000)
    bm.delete_bookmark(r"C:\Books\a.wav", entry_id)

    raw = bm._load()
    assert r"C:\Books\a.wav" not in raw


def test_delete_bookmark_is_safe_for_unknown_file(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    bm.delete_bookmark(r"C:\Books\never.wav", "some-id")  # must not raise


def test_delete_bookmark_is_safe_for_unknown_id(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    bm.add_bookmark(r"C:\Books\a.wav", "Keep me", 1000)
    bm.delete_bookmark(r"C:\Books\a.wav", "not-a-real-id")  # must not raise
    assert len(bm.list_bookmarks(r"C:\Books\a.wav")) == 1


def test_list_bookmarks_returns_none_when_file_is_corrupted(tmp_path, monkeypatch):
    """A crash mid-write, before the atomic os.replace in _save, could in theory leave
    a partially-written or otherwise corrupted JSON file behind. Reading it back must
    fall back to "nothing saved" rather than raising."""
    _isolate(tmp_path, monkeypatch)
    with open(bm.BOOKMARKS_PATH, "w", encoding="utf-8") as f:
        f.write("{not valid json")

    assert bm.list_bookmarks(r"C:\Books\a.wav") == []


def test_add_bookmark_overwrites_a_corrupted_file(tmp_path, monkeypatch):
    """Adding a new bookmark must recover cleanly from a corrupted file on disk
    instead of merging garbage into it or failing outright."""
    _isolate(tmp_path, monkeypatch)
    with open(bm.BOOKMARKS_PATH, "w", encoding="utf-8") as f:
        f.write("not even json")

    bm.add_bookmark(r"C:\Books\a.wav", "Recovered", 5000)
    entries = bm.list_bookmarks(r"C:\Books\a.wav")
    assert len(entries) == 1
    assert entries[0]["name"] == "Recovered"
