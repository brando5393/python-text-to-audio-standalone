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
