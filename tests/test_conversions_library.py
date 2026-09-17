import json
import os

import ttkbootstrap as ttk

from ConversionsLibrary import ConversionsLibrary


def test_populates_folders_and_files(tk_root, tmp_path):
    os.makedirs(tmp_path / "Books")
    (tmp_path / "Books" / "chapter1.wav").write_bytes(b"data")
    (tmp_path / "note.wav").write_bytes(b"data")

    tree = ttk.Treeview(tk_root, show="tree")
    lib = ConversionsLibrary(tree, str(tmp_path))

    root_items = tree.get_children("")
    texts = [tree.item(i, "text") for i in root_items]
    assert "Books" in texts
    assert "note.wav" in texts


def test_hides_partial_files(tk_root, tmp_path):
    (tmp_path / "finished.wav").write_bytes(b"data")
    (tmp_path / "unfinished.wav.partial").write_bytes(b"data")

    tree = ttk.Treeview(tk_root, show="tree")
    lib = ConversionsLibrary(tree, str(tmp_path))

    texts = [tree.item(i, "text") for i in tree.get_children("")]
    assert "finished.wav" in texts
    assert "unfinished.wav.partial" not in texts


def test_path_for_returns_correct_kind(tk_root, tmp_path):
    os.makedirs(tmp_path / "Podcasts")
    (tmp_path / "episode.wav").write_bytes(b"data")

    tree = ttk.Treeview(tk_root, show="tree")
    lib = ConversionsLibrary(tree, str(tmp_path))

    for item in tree.get_children(""):
        path, kind = lib.path_for(item)
        if tree.item(item, "text") == "Podcasts":
            assert kind == "dir"
        elif tree.item(item, "text") == "episode.wav":
            assert kind == "file"


def test_refresh_reflects_new_files(tk_root, tmp_path):
    tree = ttk.Treeview(tk_root, show="tree")
    lib = ConversionsLibrary(tree, str(tmp_path))
    assert len(tree.get_children("")) == 0

    (tmp_path / "new_file.wav").write_bytes(b"data")
    lib.refresh()
    texts = [tree.item(i, "text") for i in tree.get_children("")]
    assert "new_file.wav" in texts


def test_creates_root_dir_if_missing(tk_root, tmp_path):
    missing_dir = str(tmp_path / "does_not_exist_yet")
    tree = ttk.Treeview(tk_root, show="tree")
    ConversionsLibrary(tree, missing_dir)
    assert os.path.isdir(missing_dir)


def test_voice_column_reads_sidecar_metadata(tk_root, tmp_path):
    (tmp_path / "chapter.wav").write_bytes(b"data")
    (tmp_path / "chapter.wav.json").write_text(
        json.dumps({"engine": "piper", "voice_id": "en_US-ryan-high", "voice_label": "Ryan (US, high)", "text": "hi"})
    )

    tree = ttk.Treeview(tk_root, show="tree")
    lib = ConversionsLibrary(tree, str(tmp_path))

    for item in tree.get_children(""):
        if tree.item(item, "text") == "chapter.wav":
            assert tree.item(item, "values")[2] == "Ryan (US, high)"


def test_sidecar_json_files_are_not_listed_as_entries(tk_root, tmp_path):
    (tmp_path / "chapter.wav").write_bytes(b"data")
    (tmp_path / "chapter.wav.json").write_text(json.dumps({"text": "hi"}))

    tree = ttk.Treeview(tk_root, show="tree")
    lib = ConversionsLibrary(tree, str(tmp_path))

    texts = [tree.item(i, "text") for i in tree.get_children("")]
    assert "chapter.wav" in texts
    assert "chapter.wav.json" not in texts


def test_files_without_sidecar_show_blank_voice(tk_root, tmp_path):
    (tmp_path / "old_file.wav").write_bytes(b"data")

    tree = ttk.Treeview(tk_root, show="tree")
    lib = ConversionsLibrary(tree, str(tmp_path))

    for item in tree.get_children(""):
        if tree.item(item, "text") == "old_file.wav":
            assert tree.item(item, "values") == ("", "", "")


def test_pages_and_chapters_columns_read_sidecar_metadata(tk_root, tmp_path):
    (tmp_path / "book.wav").write_bytes(b"data")
    (tmp_path / "book.wav.json").write_text(
        json.dumps({"voice_label": "Ryan (US, high)", "text": "hi", "pages": 301, "chapters": None})
    )
    (tmp_path / "novel.wav").write_bytes(b"data")
    (tmp_path / "novel.wav.json").write_text(
        json.dumps({"voice_label": "Amy (US, medium)", "text": "hi", "pages": None, "chapters": 12})
    )

    tree = ttk.Treeview(tk_root, show="tree")
    lib = ConversionsLibrary(tree, str(tmp_path))

    for item in tree.get_children(""):
        name = tree.item(item, "text")
        if name == "book.wav":
            assert tree.item(item, "values") == ("301", "", "Ryan (US, high)")
        elif name == "novel.wav":
            assert tree.item(item, "values") == ("", "12", "Amy (US, medium)")


def test_text_for_reads_stored_source_text(tk_root, tmp_path):
    (tmp_path / "chapter.wav").write_bytes(b"data")
    (tmp_path / "chapter.wav.json").write_text(
        json.dumps({"engine": "piper", "voice_id": "en_US-ryan-high", "voice_label": "Ryan (US, high)", "text": "Hello world"})
    )

    tree = ttk.Treeview(tk_root, show="tree")
    lib = ConversionsLibrary(tree, str(tmp_path))

    for item in tree.get_children(""):
        if tree.item(item, "text") == "chapter.wav":
            assert lib.text_for(item) == "Hello world"


def test_text_for_returns_none_without_sidecar(tk_root, tmp_path):
    (tmp_path / "old_file.wav").write_bytes(b"data")

    tree = ttk.Treeview(tk_root, show="tree")
    lib = ConversionsLibrary(tree, str(tmp_path))

    for item in tree.get_children(""):
        if tree.item(item, "text") == "old_file.wav":
            assert lib.text_for(item) is None


def test_text_for_returns_none_for_folders(tk_root, tmp_path):
    os.makedirs(tmp_path / "Books")

    tree = ttk.Treeview(tk_root, show="tree")
    lib = ConversionsLibrary(tree, str(tmp_path))

    for item in tree.get_children(""):
        if tree.item(item, "text") == "Books":
            assert lib.text_for(item) is None


def test_survives_when_icons_fail_to_load(tk_root, tmp_path):
    """Regression test: Treeview.insert(..., image=None, ...) raises a TclError that
    corrupts its whole argument list (not just the image option) on this tkinter
    version -- a folder/file row must never be inserted with image=None literally
    passed, only with the image kwarg omitted entirely when no icon loaded."""
    os.makedirs(tmp_path / "Books")
    (tmp_path / "note.wav").write_bytes(b"data")

    tree = ttk.Treeview(tk_root, show="tree")
    lib = ConversionsLibrary(tree, str(tmp_path))
    lib._folder_icon = None
    lib._audio_icon = None
    lib.refresh()  # must not raise

    texts = [tree.item(i, "text") for i in tree.get_children("")]
    assert "Books" in texts
    assert "note.wav" in texts
