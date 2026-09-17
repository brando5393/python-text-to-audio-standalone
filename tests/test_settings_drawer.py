import tkinter as tk

import Config
import FileManager
from SettingsDrawer import SettingsDrawer, _band_label, _EXPRESSIVENESS_BANDS, _SPEED_BANDS


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


def test_band_label_covers_the_full_speed_range():
    assert _band_label(0.5, _SPEED_BANDS) == "Slower"
    assert _band_label(0.8, _SPEED_BANDS) == "Slightly slower"
    assert _band_label(1.0, _SPEED_BANDS) == "Normal"
    assert _band_label(1.3, _SPEED_BANDS) == "Slightly faster"
    assert _band_label(2.0, _SPEED_BANDS) == "Faster"


def test_band_label_covers_the_full_expressiveness_range():
    assert _band_label(0.3, _EXPRESSIVENESS_BANDS) == "Flat, monotone"
    assert _band_label(0.5, _EXPRESSIVENESS_BANDS) == "Calm, steady"
    assert _band_label(0.667, _EXPRESSIVENESS_BANDS) == "Balanced, natural"
    assert _band_label(0.85, _EXPRESSIVENESS_BANDS) == "Expressive"
    assert _band_label(1.0, _EXPRESSIVENESS_BANDS) == "Highly varied"


def test_preview_voice_warns_when_nothing_chosen(tk_root, tmp_path, monkeypatch):
    drawer, _, _ = _make_drawer(tk_root, tmp_path, monkeypatch)
    logged = []
    drawer.logger.add_event = lambda status, msg, err="": logged.append((status, msg))

    drawer._preview_voice()

    assert any(status == "warn" for status, _ in logged)
    drawer.destroy()


def test_preview_and_main_players_use_different_mci_aliases(tk_root, tmp_path, monkeypatch):
    """Regression guard: previewing a voice must never interrupt whatever the user is
    actually listening to in the main player, and vice versa."""
    drawer, _, _ = _make_drawer(tk_root, tmp_path, monkeypatch)
    assert drawer._preview_player._alias != "texttoaudio_player"
    drawer.destroy()


def test_speed_label_reflects_current_slider_value(tk_root, tmp_path, monkeypatch):
    drawer, _, _ = _make_drawer(tk_root, tmp_path, monkeypatch)
    drawer.speed_var.set(1.0)
    assert drawer.speed_label_var.get() == "1.00x (Normal)"
    drawer.speed_var.set(0.5)
    assert drawer.speed_label_var.get() == "0.50x (Slower)"
    drawer.speed_var.set(2.0)
    assert drawer.speed_label_var.get() == "2.00x (Faster)"
    drawer.destroy()


def test_expressiveness_label_reflects_current_slider_value(tk_root, tmp_path, monkeypatch):
    drawer, _, _ = _make_drawer(tk_root, tmp_path, monkeypatch)
    drawer.expr_var.set(0.667)
    assert drawer.expr_label_var.get() == "0.67 (Balanced, natural)"
    drawer.expr_var.set(0.3)
    assert drawer.expr_label_var.get() == "0.30 (Flat, monotone)"
    drawer.expr_var.set(1.0)
    assert drawer.expr_label_var.get() == "1.00 (Highly varied)"
    drawer.destroy()
