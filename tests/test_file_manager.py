import os
import tkinter as tk
from tkinter import messagebox

import FileManager


def _make_manager(tk_root, tmp_path, monkeypatch):
    monkeypatch.setattr(FileManager, "CONVERSIONS_ROOT", str(tmp_path / "Conversions"))
    file_list = tk.Listbox(tk_root)
    log_list = tk.Listbox(tk_root)
    label = tk.Label(tk_root)
    changes = []
    manager = FileManager.FileManager(file_list, log_list, label, on_directory_change=lambda: changes.append(1))
    return manager, changes


def test_default_download_directory_is_conversions_root(tk_root, tmp_path, monkeypatch):
    manager, _ = _make_manager(tk_root, tmp_path, monkeypatch)
    assert manager.download_directory == FileManager.CONVERSIONS_ROOT
    assert os.path.isdir(FileManager.CONVERSIONS_ROOT)


def test_create_subfolder_lives_under_conversions_root(tk_root, tmp_path, monkeypatch):
    manager, _ = _make_manager(tk_root, tmp_path, monkeypatch)
    monkeypatch.setattr("FileManager.simpledialog.askstring", lambda *a, **k: "Books")
    manager.create_subfolder()
    expected = os.path.join(FileManager.CONVERSIONS_ROOT, "Books")
    assert manager.download_directory == expected
    assert os.path.isdir(expected)


def test_create_subfolder_sanitizes_invalid_characters(tk_root, tmp_path, monkeypatch):
    manager, _ = _make_manager(tk_root, tmp_path, monkeypatch)
    monkeypatch.setattr("FileManager.simpledialog.askstring", lambda *a, **k: 'Bad<>:"/\\|?*Name')
    manager.create_subfolder()
    assert os.path.basename(manager.download_directory) == "BadName"


def test_create_subfolder_rejects_parent_directory_traversal(tk_root, tmp_path, monkeypatch):
    """Security regression test: stripping '/' and '\\' blocks multi-segment traversal
    like "../../x" (its slashes vanish, leaving a literal, harmless folder name), but a
    name of exactly ".." has no separator to strip and survives intact, resolving to the
    parent of Conversions -- confirmed by testing before this was fixed with a real
    containment check (os.path.commonpath), not just a denylist for ".."."""
    manager, _ = _make_manager(tk_root, tmp_path, monkeypatch)
    original_dir = manager.download_directory
    monkeypatch.setattr("FileManager.simpledialog.askstring", lambda *a, **k: "..")
    manager.create_subfolder()
    assert manager.download_directory == original_dir
    assert os.path.normpath(manager.download_directory).startswith(
        os.path.normpath(FileManager.CONVERSIONS_ROOT)
    )


def test_set_download_directory_asks_for_confirmation(tk_root, tmp_path, monkeypatch):
    manager, changes = _make_manager(tk_root, tmp_path, monkeypatch)
    other_dir = str(tmp_path / "Elsewhere")
    os.makedirs(other_dir)
    monkeypatch.setattr("FileManager.filedialog.askdirectory", lambda **k: other_dir)

    confirm_calls = []

    def fake_confirm(title, message):
        confirm_calls.append((title, message))
        return True

    monkeypatch.setattr("FileManager.messagebox.askyesno", fake_confirm)
    manager.set_download_directory()

    assert len(confirm_calls) == 1
    assert other_dir in confirm_calls[0][1]
    assert manager.download_directory == other_dir


def test_set_download_directory_respects_declined_confirmation(tk_root, tmp_path, monkeypatch):
    manager, _ = _make_manager(tk_root, tmp_path, monkeypatch)
    original_dir = manager.download_directory
    other_dir = str(tmp_path / "Elsewhere")
    os.makedirs(other_dir)
    monkeypatch.setattr("FileManager.filedialog.askdirectory", lambda **k: other_dir)
    monkeypatch.setattr("FileManager.messagebox.askyesno", lambda *a, **k: False)

    manager.set_download_directory()

    assert manager.download_directory == original_dir


def test_reset_download_directory_restores_default(tk_root, tmp_path, monkeypatch):
    manager, _ = _make_manager(tk_root, tmp_path, monkeypatch)
    manager.download_directory = str(tmp_path / "somewhere-else")
    manager.reset_download_directory()
    assert manager.download_directory == FileManager.CONVERSIONS_ROOT


def _add_fake_files(manager, monkeypatch, *paths):
    monkeypatch.setattr("FileManager.filedialog.askopenfilenames", lambda **k: paths)
    manager.add_files()


def test_added_files_default_to_no_engine_override(tk_root, tmp_path, monkeypatch):
    manager, _ = _make_manager(tk_root, tmp_path, monkeypatch)
    _add_fake_files(manager, monkeypatch, r"C:\Books\a.pdf")
    assert manager.file_list == [{"path": r"C:\Books\a.pdf", "engine": None, "voice": None}]
    assert manager.file_list_display.get(0) == "a.pdf"


def test_set_engine_for_item_updates_only_that_item(tk_root, tmp_path, monkeypatch):
    manager, _ = _make_manager(tk_root, tmp_path, monkeypatch)
    _add_fake_files(manager, monkeypatch, r"C:\Books\a.pdf", r"C:\Books\b.pdf")

    manager.set_engine_for_item(0, "piper", "en_US-ryan-high")

    assert manager.file_list[0]["engine"] == "piper"
    assert manager.file_list[0]["voice"] == "en_US-ryan-high"
    assert manager.file_list[1]["engine"] is None  # untouched


def test_set_engine_for_item_display_shows_the_override(tk_root, tmp_path, monkeypatch):
    manager, _ = _make_manager(tk_root, tmp_path, monkeypatch)
    _add_fake_files(manager, monkeypatch, r"C:\Books\a.pdf")

    manager.set_engine_for_item(0, "piper", "en_US-ryan-high")
    assert "Piper" in manager.file_list_display.get(0)
    assert "Ryan" in manager.file_list_display.get(0)

    manager.set_engine_for_item(0, "pyttsx3", None)
    assert "System voice" in manager.file_list_display.get(0)

    manager.set_engine_for_item(0, None, None)
    assert manager.file_list_display.get(0) == "a.pdf"


def test_set_engine_for_item_ignores_out_of_range_index(tk_root, tmp_path, monkeypatch):
    manager, _ = _make_manager(tk_root, tmp_path, monkeypatch)
    _add_fake_files(manager, monkeypatch, r"C:\Books\a.pdf")
    manager.set_engine_for_item(5, "piper", "en_US-ryan-high")  # must not raise
    assert manager.file_list[0]["engine"] is None


def test_files_with_override_display_a_different_color_than_default(tk_root, tmp_path, monkeypatch):
    """Regression: every row previously got the same color regardless of whether it had
    a per-file override, so a customized file was visually indistinguishable from one
    just using the Settings default."""
    manager, _ = _make_manager(tk_root, tmp_path, monkeypatch)
    _add_fake_files(manager, monkeypatch, r"C:\Books\a.pdf", r"C:\Books\b.pdf")

    manager.set_engine_for_item(0, "piper", "en_US-ryan-high")

    default_color = manager.file_list_display.itemcget(1, "foreground")
    override_color = manager.file_list_display.itemcget(0, "foreground")
    assert default_color != override_color


def test_apply_engine_to_all_updates_every_item(tk_root, tmp_path, monkeypatch):
    manager, _ = _make_manager(tk_root, tmp_path, monkeypatch)
    _add_fake_files(manager, monkeypatch, r"C:\Books\a.pdf", r"C:\Books\b.pdf", r"C:\Books\c.pdf")

    manager.apply_engine_to_all("piper", "en_US-ryan-high")

    assert all(item["engine"] == "piper" and item["voice"] == "en_US-ryan-high" for item in manager.file_list)
    for i in range(3):
        assert "Piper: Ryan" in manager.file_list_display.get(i)


def test_remove_file_removes_matching_entry_from_file_list(tk_root, tmp_path, monkeypatch):
    manager, _ = _make_manager(tk_root, tmp_path, monkeypatch)
    _add_fake_files(manager, monkeypatch, r"C:\Books\a.pdf", r"C:\Books\b.pdf")
    manager.file_list_display.selection_set(0)

    manager.remove_file()

    assert len(manager.file_list) == 1
    assert manager.file_list[0]["path"] == r"C:\Books\b.pdf"


def test_clear_files_empties_the_list(tk_root, tmp_path, monkeypatch):
    manager, _ = _make_manager(tk_root, tmp_path, monkeypatch)
    _add_fake_files(manager, monkeypatch, r"C:\Books\a.pdf")
    manager.clear_files()
    assert manager.file_list == []
    assert manager.file_list_display.size() == 0
