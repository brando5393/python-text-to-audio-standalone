import tkinter as tk

import Config
import FileManager
from SettingsDrawer import SettingsDrawer


def _make_drawer(tk_root, tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.setattr(FileManager, "CONVERSIONS_ROOT", str(tmp_path / "Conversions"))
    Config.save(dict(Config.DEFAULTS))

    file_list = tk.Listbox(tk_root)
    log_list = tk.Listbox(tk_root)
    label = tk.Label(tk_root)
    from LogManager import LogManager
    logger = LogManager(log_list)
    explorer = FileManager.FileManager(file_list, log_list, label, on_directory_change=lambda: None)

    theme_calls = []
    scale_calls = []
    drawer = SettingsDrawer(
        tk_root, logger, explorer,
        on_theme_change=theme_calls.append, on_text_scale_change=scale_calls.append,
        on_close=lambda: None, dark_mode=False,
    )
    return drawer, theme_calls, scale_calls


def test_saving_a_drawer_field_preserves_settings_the_drawer_does_not_manage(tk_root, tmp_path, monkeypatch):
    """Regression test: _save() previously constructed a fixed field dict, so any Config
    field the drawer doesn't expose (e.g. start_in_mini_mode, set elsewhere in main.py)
    was silently reset to its default the moment any drawer control changed -- caught
    repeatedly while adding new Config fields this session. _save() now merges onto the
    settings already on disk instead."""
    drawer, _, _ = _make_drawer(tk_root, tmp_path, monkeypatch)

    # Simulate main.py's mini player setting this independently of the drawer.
    current = Config.load()
    current["start_in_mini_mode"] = True
    Config.save(current)

    # Touching an unrelated drawer control (speed) triggers _save() via the var trace.
    drawer.speed_var.set(1.3)

    assert Config.load()["start_in_mini_mode"] is True
    assert Config.load()["speed"] == 1.3
    drawer.destroy()


def test_refresh_from_disk_picks_up_external_changes(tk_root, tmp_path, monkeypatch):
    drawer, _, _ = _make_drawer(tk_root, tmp_path, monkeypatch)
    assert drawer.engine_var.get() == Config.DEFAULTS["engine"]

    current = Config.load()
    current["engine"] = "pyttsx3" if Config.DEFAULTS["engine"] != "pyttsx3" else "piper"
    Config.save(current)

    drawer.refresh_from_disk()
    assert drawer.engine_var.get() == current["engine"]
    drawer.destroy()


def test_reset_voice_settings_preserves_unrelated_fields(tk_root, tmp_path, monkeypatch):
    drawer, _, _ = _make_drawer(tk_root, tmp_path, monkeypatch)
    current = Config.load()
    current["start_in_mini_mode"] = True
    current["engine"] = "pyttsx3"
    Config.save(current)
    drawer.engine_var.set("pyttsx3")

    import tkinter.messagebox as messagebox
    original_askyesno = messagebox.askyesno
    messagebox.askyesno = lambda *a, **k: True
    try:
        drawer._reset_voice_settings()
    finally:
        messagebox.askyesno = original_askyesno

    assert Config.load()["engine"] == Config.DEFAULTS["engine"]
    assert Config.load()["start_in_mini_mode"] is True
    drawer.destroy()
