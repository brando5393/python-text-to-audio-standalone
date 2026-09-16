import os
import sys
import tkinter as tk
from tkinter import messagebox

import ttkbootstrap as ttk

import Converter
import FileManager
from AudioPlayer import AudioPlayer
from ConversionsLibrary import ConversionsLibrary
from LogManager import LogManager
from SettingsDialog import SettingsDialog

# A warm "coffee house" theme: espresso brown, caramel, and honey accents on a latte-cream
# ground. Swap THEME for a built-in ttkbootstrap name (e.g. "darkly") to use that instead.
ttk.Theme(
    name="coffeehouse",
    primary="#6f4e37",     # espresso brown
    secondary="#8a7968",   # warm taupe
    success="#a97142",     # caramel
    info="#5f7a61",        # sage / matcha
    warning="#c9932f",     # honey gold
    danger="#a3402c",      # brick / dried cherry
    neutral="#8a7968",
    light={"background": "#f2e8d9", "foreground": "#3b2a1e"},
).register()
THEME = "coffeehouse-light"

player = AudioPlayer()


def confirm_quit():
    """Exits the app cleanly after yes/no prompt"""
    if messagebox.askyesno(title="Close Application", message="Are you sure you want to quit?"):
        player.stop()
        app.destroy()


def styled_listbox(parent, **kwargs):
    """A tk.Listbox colored to match the current ttkbootstrap theme."""
    colors = style.colors
    return tk.Listbox(
        parent,
        activestyle="none",
        relief="flat",
        highlightthickness=1,
        highlightbackground=colors.border,
        highlightcolor=colors.primary,
        background=colors.inputbg,
        foreground=colors.inputfg,
        selectbackground=colors.primary,
        selectforeground=colors.selectfg,
        **kwargs,
    )


def refresh_library():
    library.refresh()


def open_settings():
    SettingsDialog(app, logger)


def do_convert():
    if not explorer.file_list:
        logger.add_event("warn", "No files queued for conversion")
        return
    converter.convert_to_audio(explorer.file_list, explorer.download_directory)
    explorer.clear_files()


def poll_conversions():
    events = converter.poll_events()
    if events:
        refresh_library()
    app.after(300, poll_conversions)


def play_selected_audio(_event=None):
    selection = library_tree.selection()
    if not selection:
        return
    path, kind = library.path_for(selection[0])
    if kind != "file":
        return
    try:
        player.play(path)
        now_playing_var.set(f"Now playing: {path.split(chr(92))[-1]}")
    except Exception as e:
        logger.add_event("error", "Failed to play audio file", str(e))


def toggle_pause():
    if player.is_playing():
        player.pause()
    else:
        player.resume()


def stop_playback():
    player.stop()
    now_playing_var.set("Nothing playing")


# Create the main application window
app = ttk.Window(title="Text to Audio Converter", themename=THEME, size=(1040, 680), minsize=(900, 620))
try:
    # Frozen (cx_Freeze) builds ship assets/ next to the exe; source runs ship it next to main.py.
    app_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(__file__)
    app.iconbitmap(os.path.join(app_dir, "assets", "icon.ico"))
except Exception:
    pass  # Missing icon shouldn't block the app from starting.
style = ttk.Style()

# Header
header = ttk.Label(app, text="Text to Audio Converter", font=("Georgia", 19, "bold"))
header.grid(row=0, column=0, columnspan=3, sticky="w", padx=20, pady=(18, 10))

# Files section
files_frame = ttk.Labelframe(app, text="Files to Convert", padding=10, bootstyle="primary")
files_frame.grid(row=1, column=0, sticky="nsew", padx=(20, 8), pady=8)

file_list_display = styled_listbox(files_frame, height=14)
file_list_scroll = ttk.Scrollbar(files_frame, orient="vertical", command=file_list_display.yview, bootstyle="round")
file_list_display.configure(yscrollcommand=file_list_scroll.set)
file_list_display.grid(row=0, column=0, sticky="nsew")
file_list_scroll.grid(row=0, column=1, sticky="ns")
files_frame.rowconfigure(0, weight=1)
files_frame.columnconfigure(0, weight=1)

# Conversions library section
library_frame = ttk.Labelframe(app, text="Conversions Library", padding=10, bootstyle="primary")
library_frame.grid(row=1, column=1, sticky="nsew", padx=8, pady=8)

library_tree = ttk.Treeview(library_frame, show="tree", height=14, bootstyle="primary")
library_scroll = ttk.Scrollbar(library_frame, orient="vertical", command=library_tree.yview, bootstyle="round")
library_tree.configure(yscrollcommand=library_scroll.set)
library_tree.grid(row=0, column=0, sticky="nsew")
library_scroll.grid(row=0, column=1, sticky="ns")
library_tree.bind("<Double-1>", play_selected_audio)
library_frame.rowconfigure(0, weight=1)
library_frame.columnconfigure(0, weight=1)

refresh_library_btn = ttk.Button(library_frame, text="Refresh", command=refresh_library, bootstyle="secondary-outline")
refresh_library_btn.grid(row=1, column=0, sticky="ew", pady=(8, 0))

# Actions section
controls_frame = ttk.Labelframe(app, text="Actions", padding=10, bootstyle="primary")
controls_frame.grid(row=1, column=2, sticky="new", padx=(8, 20), pady=8)

# Player section
player_frame = ttk.Labelframe(app, text="Playback", padding=10, bootstyle="secondary")
player_frame.grid(row=2, column=2, sticky="new", padx=(8, 20), pady=(0, 8))

now_playing_var = tk.StringVar(value="Nothing playing — double-click a file in the Conversions Library")
now_playing_label = ttk.Label(player_frame, textvariable=now_playing_var, wraplength=180, bootstyle="secondary")
now_playing_label.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

pause_btn = ttk.Button(player_frame, text="Play / Pause", command=toggle_pause, bootstyle="info-outline")
stop_playback_btn = ttk.Button(player_frame, text="Stop", command=stop_playback, bootstyle="danger-outline")
pause_btn.grid(row=1, column=0, sticky="ew", padx=(0, 4))
stop_playback_btn.grid(row=1, column=1, sticky="ew", padx=(4, 0))
player_frame.columnconfigure(0, weight=1)
player_frame.columnconfigure(1, weight=1)

# Log section
log_frame = ttk.Labelframe(app, text="Activity Log", padding=10, bootstyle="secondary")
log_frame.grid(row=3, column=0, columnspan=3, sticky="nsew", padx=20, pady=(8, 8))

app_log_display = styled_listbox(log_frame, height=8, font=("Consolas", 9))
log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=app_log_display.yview, bootstyle="round")
app_log_display.configure(yscrollcommand=log_scroll.set)
app_log_display.grid(row=0, column=0, sticky="nsew")
log_scroll.grid(row=0, column=1, sticky="ns")
log_frame.rowconfigure(0, weight=1)
log_frame.columnconfigure(0, weight=1)

# Directory + exit bar
bottom_bar = ttk.Frame(app, padding=(20, 0, 20, 16))
bottom_bar.grid(row=4, column=0, columnspan=3, sticky="ew")
bottom_bar.columnconfigure(0, weight=1)

download_directory_label = ttk.Label(bottom_bar, bootstyle="secondary")
download_directory_label.grid(row=0, column=0, sticky="w")

new_folder_button = ttk.Button(bottom_bar, text="New Folder", bootstyle="secondary-outline")
new_folder_button.grid(row=0, column=1, padx=(8, 8))

change_directory_button = ttk.Button(bottom_bar, text="Change Save Folder", bootstyle="secondary-outline")
change_directory_button.grid(row=0, column=2, padx=(0, 8))

exit_btn = ttk.Button(bottom_bar, text="Exit", command=confirm_quit, bootstyle="danger-outline")
exit_btn.grid(row=0, column=3)

app.columnconfigure(0, weight=2)
app.columnconfigure(1, weight=2)
app.columnconfigure(2, weight=1)
app.rowconfigure(1, weight=1)
app.rowconfigure(3, weight=1)

# Wire up the app's logic
logger = LogManager(app_log_display)
library = ConversionsLibrary(library_tree, FileManager.CONVERSIONS_ROOT)
explorer = FileManager.FileManager(file_list_display, app_log_display, download_directory_label, refresh_library)
converter = Converter.Converter(app_log_display)

change_directory_button.configure(command=explorer.set_download_directory)
new_folder_button.configure(command=explorer.create_subfolder)

add_files_btn = ttk.Button(controls_frame, text="Add Files", command=explorer.add_files, bootstyle="primary")
del_file_btn = ttk.Button(
    controls_frame, text="Remove Selected", command=explorer.remove_file, bootstyle="secondary-outline"
)
del_all_btn = ttk.Button(
    controls_frame, text="Remove All", command=explorer.clear_files, bootstyle="secondary-outline"
)
convert_btn = ttk.Button(controls_frame, text="Convert to Audio", bootstyle="success", command=do_convert)
settings_btn = ttk.Button(controls_frame, text="Voice Settings...", command=open_settings, bootstyle="secondary-outline")

add_files_btn.grid(row=0, column=0, sticky="ew", pady=(0, 6))
del_file_btn.grid(row=1, column=0, sticky="ew", pady=(0, 6))
del_all_btn.grid(row=2, column=0, sticky="ew", pady=(0, 18))
convert_btn.grid(row=3, column=0, sticky="ew", ipady=4)
settings_btn.grid(row=4, column=0, sticky="ew", pady=(6, 0))
controls_frame.columnconfigure(0, weight=1)

logger.add_event("info", "Application started successfully")
app.after(300, poll_conversions)

app.mainloop()
