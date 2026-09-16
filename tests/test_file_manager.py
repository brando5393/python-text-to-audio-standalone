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
