import os
import queue
import sys
import tempfile
import threading
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox

import ttkbootstrap as ttk

import AppIcon
import Config
import ConversionEstimate
import ConversionQueue
import Converter
import FileManager
import PiperEngine
import PlaybackMemory
import SoundEffects
import TextExtraction
import TextSanitization
from AudioPlayer import AudioPlayer, wav_duration_ms
from ConversionsLibrary import ConversionsLibrary
from LogManager import LogManager
from MiniPlayer import MiniPlayer
from ProgressDialog import ProgressDialog
from SettingsDrawer import SettingsDrawer
from UpdateBanner import UpdateBanner

# A warm "coffee house" theme: espresso brown, caramel, and honey accents, with both a
# latte-cream light mode and a dark-roast dark mode (toggle from the Settings drawer).
ttk.Theme(
    name="coffeehouse",
    primary="#6f4e37",     # espresso brown
    secondary="#8a7968",   # warm taupe
    success="#a97142",     # caramel
    info="#5f7a61",        # sage / matcha
    warning="#7a561d",     # deep amber -- darkened from an earlier honey gold (#c9932f), which
                           # measured 2.25:1 contrast (cream text on fill) against WCAG AA's 4.5:1
                           # minimum; this shade measures 5.45:1
    danger="#a3402c",      # brick / dried cherry
    neutral="#8a7968",
    light={"background": "#f2e8d9", "foreground": "#3b2a1e"},
    dark={"background": "#241b14", "foreground": "#f2e8d9"},
).register()
THEME = "coffeehouse-light"

player = AudioPlayer()
progress_dialog = None
mini_player = None
batch_had_error = False
batch_had_done = False


def enter_mini_mode(persist=True):
    global mini_player
    if mini_player is not None:
        return
    app.withdraw()
    mini_player = MiniPlayer(app, player, now_playing_var, on_expand=exit_mini_mode)
    if persist:
        current = Config.load()
        current["start_in_mini_mode"] = True
        Config.save(current)


def exit_mini_mode():
    global mini_player
    if mini_player is not None:
        mini_player.destroy()
        mini_player = None
    app.deiconify()
    current = Config.load()
    current["start_in_mini_mode"] = False
    Config.save(current)


def confirm_quit():
    """Exits the app cleanly after yes/no prompt"""
    if messagebox.askyesno(title="Close Application", message="Are you sure you want to quit?"):
        player.stop()
        SoundEffects.play("exit", blocking=False)
        # Give the exit chime (~0.5s) a moment to actually play before the process ends --
        # destroying the window immediately would cut it off mid-note.
        app.after(500, app.destroy)


def quit_for_update():
    """Closes without the usual confirmation -- the user already explicitly chose
    "Update Now", so asking "are you sure you want to quit?" right after would be a
    redundant, confusing second prompt. The installer needs Talebrew closed to safely
    overwrite its files, so this doesn't play the exit chime or delay for it either."""
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


def restyle_listbox(widget):
    """Re-applies the current theme's colors to a Listbox after a light/dark switch."""
    colors = style.colors
    widget.configure(
        highlightbackground=colors.border,
        highlightcolor=colors.primary,
        background=colors.inputbg,
        foreground=colors.inputfg,
        selectbackground=colors.primary,
        selectforeground=colors.selectfg,
    )


def set_dark_mode(dark):
    style.theme_use("coffeehouse-dark" if dark else "coffeehouse-light")
    restyle_listbox(file_list_display)
    restyle_listbox(app_log_display)
    apply_background(dark)
    explorer.set_dark_mode(dark)


BASE_NAMED_FONT_SIZES = {"TkDefaultFont": 9, "TkTextFont": 9, "TkHeadingFont": 10, "TkMenuFont": 9}
LARGE_TEXT_DELTA = 4


def apply_text_scale(large):
    """Scales UI text app-wide. Adjusting Tk's own named fonts (TkDefaultFont etc.) covers
    every ttk widget that doesn't set an explicit font (buttons, labels, the Settings
    drawer, comboboxes, ...); the handful of widgets with an explicit font (the header,
    and the monospace log) are resized separately since they don't follow the named fonts."""
    delta = LARGE_TEXT_DELTA if large else 0
    for name, base_size in BASE_NAMED_FONT_SIZES.items():
        try:
            tkfont.nametofont(name).configure(size=base_size + delta)
        except tk.TclError:
            pass
    title_label.configure(font=("Palatino Linotype", 21 + delta, "bold"))
    app_log_display.configure(font=("Consolas", 9 + delta))
    library.sync_row_height()  # named fonts alone don't resize a Treeview's fixed
    # per-theme row height -- see ConversionsLibrary.sync_row_height()


def toggle_settings_drawer():
    if drawer_wrapper.winfo_ismapped():
        drawer_wrapper.grid_remove()
    else:
        settings_drawer.refresh_from_disk()
        drawer_wrapper.grid()


def refresh_library():
    library.refresh()


def start_conversion(files, output_dir):
    """Shared by a normal Convert click, a re-convert, and resuming an interrupted batch
    from last session -- all three just need a file list and a destination."""
    global progress_dialog

    # A re-convert overwrites the same output file it's re-synthesizing, and Windows
    # won't allow that while Talebrew's own player still has it open -- most visibly
    # when someone re-converts a file they were just listening to. Releasing it here
    # instead of surfacing "Access is denied" turns a real failure this app already hit
    # into a no-op the user never has to think about.
    currently_playing = player.current_path()
    if currently_playing:
        for file in files:
            base_name = os.path.splitext(os.path.basename(file))[0]
            expected_output = os.path.join(output_dir, base_name + ".wav")
            if os.path.normcase(expected_output) == os.path.normcase(currently_playing):
                player.stop()
                now_playing_var.set("Nothing playing")
                break

    ConversionQueue.save(files, output_dir)
    progress_dialog = ProgressDialog(app, converter, len(files))
    converter.convert_to_audio(files, output_dir)


def do_convert():
    if not explorer.file_list:
        logger.add_event("warn", "No files queued for conversion")
        return
    start_conversion(explorer.file_list, explorer.download_directory)
    explorer.clear_files()


def on_file_selection_change(_event=None):
    """Loads the selected file's own engine/voice override into the per-file controls,
    so switching which file is selected doesn't leave stale values from whichever file
    was selected before."""
    per_file_voice_menu.configure(values=PiperEngine.list_installed_voices())
    selection = file_list_display.curselection()
    if not selection:
        file_info_var.set("")
        return
    item = explorer.file_list[selection[0]]
    per_file_engine_var.set(item["engine"] or "default")
    if item["voice"]:
        per_file_voice_menu.set(item["voice"])
    elif per_file_voice_menu["values"]:
        per_file_voice_menu.set(per_file_voice_menu["values"][0])
    request_file_info(item["path"])
    refresh_file_info_label()


def _resolve_per_file_choice():
    engine = per_file_engine_var.get()
    if engine == "default":
        return None, None
    voice = per_file_voice_menu.get() if engine == "piper" else None
    return engine, voice


def apply_engine_to_selected():
    selection = file_list_display.curselection()
    if not selection:
        logger.add_event("warn", "No file selected to set a voice for")
        return
    engine, voice = _resolve_per_file_choice()
    explorer.set_engine_for_item(selection[0], engine, voice)
    refresh_file_info_label()


def apply_engine_to_all_files():
    if not explorer.file_list:
        logger.add_event("warn", "No files queued to apply a voice to")
        return
    engine, voice = _resolve_per_file_choice()
    explorer.apply_engine_to_all(engine, voice)
    refresh_file_info_label()


# Pages/chapters/estimated-time info for the selected queued file, shown before
# conversion starts (the real conversion shows a live, continuously-recalculated ETA
# instead -- see ProgressDialog -- which is always more accurate than this guess).
# Extraction runs on a background thread since it can take a moment for a large
# document, and is cached per path so re-selecting the same file is instant.
_file_info_cache = {}
_file_info_queue = queue.Queue()


def request_file_info(path):
    if path in _file_info_cache:
        return

    def work():
        try:
            text = TextSanitization.sanitize(TextExtraction.extract_text(path))
            pages, chapters = TextExtraction.extract_structure_counts(path)
            _file_info_queue.put((path, {"pages": pages, "chapters": chapters, "char_count": len(text)}))
        except Exception:
            _file_info_queue.put((path, None))

    threading.Thread(target=work, daemon=True).start()


def poll_file_info():
    try:
        while True:
            path, info = _file_info_queue.get_nowait()
            _file_info_cache[path] = info
            refresh_file_info_label()
    except queue.Empty:
        pass
    app.after(300, poll_file_info)


def refresh_file_info_label():
    selection = file_list_display.curselection()
    if not selection:
        file_info_var.set("")
        return
    item = explorer.file_list[selection[0]]
    info = _file_info_cache.get(item["path"])
    if item["path"] not in _file_info_cache:
        file_info_var.set("Reading file...")
        return
    if info is None:
        file_info_var.set("Could not read this file")
        return

    settings = Config.load()
    effective_engine = item["engine"] or settings["engine"]
    effective_voice = item["voice"] or settings["voice"]

    structure_parts = []
    if info["pages"]:
        structure_parts.append(f"{info['pages']} pages")
    if info["chapters"]:
        structure_parts.append(f"{info['chapters']} chapters")
    structure_text = ", ".join(structure_parts) if structure_parts else "No page/chapter info"

    estimate_seconds = ConversionEstimate.estimate_seconds(info["char_count"], effective_engine, effective_voice)
    estimate_text = ConversionEstimate.format_duration(estimate_seconds)
    file_info_var.set(f"{structure_text}\nEst. conversion time: {estimate_text}")


def poll_conversions():
    global batch_had_error, batch_had_done
    events = converter.poll_events()
    if events:
        if any(event[0] in ("done", "error") for event in events):
            refresh_library()
        if progress_dialog is not None and progress_dialog.winfo_exists():
            progress_dialog.handle_events(events)
        for event in events:
            if event[0] == "plan":
                batch_had_error = False  # a new batch is starting
                batch_had_done = False
            elif event[0] == "error":
                batch_had_error = True
            elif event[0] == "done":
                batch_had_done = True
            elif event[0] == "all_done":
                ConversionQueue.clear()  # the batch is no longer "in progress" either way
                if batch_had_error:
                    SoundEffects.play("error")
                elif batch_had_done:
                    SoundEffects.play("conversion_done")
                # else: everything in the batch was skipped -- nothing worth chiming for.
    app.after(300, poll_conversions)


def play_selected_audio(_event=None):
    selection = library_tree.selection()
    if not selection:
        return
    path, kind = library.path_for(selection[0])
    if kind != "file":
        return
    try:
        resume_position_ms = _resolve_resume_position(path)
        player.play(path)
        if resume_position_ms:
            player.seek_ms(resume_position_ms)
        now_playing_var.set(f"Now playing: {path.split(chr(92))[-1]}")
    except Exception as e:
        logger.add_event("error", "Failed to play audio file", str(e))


def _resolve_resume_position(path):
    """Offers to resume from where playback last left off on this file, if it's worth
    asking about -- not right at the start, and not close enough to the end that it was
    effectively already finished. Checked via the file's own WAV header rather than
    opening it for playback first, so nothing plays before the user has decided."""
    saved_ms = PlaybackMemory.get_position(path)
    if not PlaybackMemory.is_resumable(saved_ms, wav_duration_ms(path)):
        return 0
    minutes, seconds = divmod(saved_ms // 1000, 60)
    resume = messagebox.askyesno(
        "Resume Playback", f"You were {minutes}:{seconds:02d} into this file last time.\n\nResume from there?",
    )
    return saved_ms if resume else 0


def restart_playback():
    """Jumps back to the beginning of whatever is currently loaded, regardless of any
    saved resume position -- for when you want to hear a file from the start on purpose."""
    if player.current_path():
        player.seek_ms(0)


def track_playback_position():
    """Keeps the saved position for the currently playing file up to date, so closing
    the app (or it crashing) doesn't lose more than a few seconds of progress. Also
    detects a file finishing naturally (stopped, at/near the end) and clears its saved
    position, so a finished file starts fresh next time instead of "resuming" at 100%.
    """
    path = player.current_path()
    if path:
        if player.is_playing():
            PlaybackMemory.save_position(path, player.position_ms())
        else:
            length = player.length_ms()
            position = player.position_ms()
            if length and position >= length - PlaybackMemory.RESUME_EDGE_MS:
                PlaybackMemory.clear_position(path)
    app.after(5000, track_playback_position)


def reconvert_selected():
    """Re-synthesizes a previously converted file using whatever voice is selected now.

    Converted audio is otherwise permanently locked to the voice active at the moment
    it was made, which defeats the point of being able to change voices -- someone who
    switches to a new voice would have to track down and re-add every original document
    to hear their existing library in it. The source text used for each conversion is
    kept in a sidecar file precisely so this can work without the original document.
    """
    selection = library_tree.selection()
    if not selection:
        logger.add_event("warn", "No file selected to re-convert")
        return
    path, kind = library.path_for(selection[0])
    if kind != "file":
        logger.add_event("warn", "Select an audio file, not a folder, to re-convert")
        return
    text = library.text_for(selection[0])
    if not text:
        logger.add_event(
            "warn", "No stored text for this file, it can't be re-converted",
            "It was likely converted before this feature existed -- convert the original document again instead",
        )
        return

    output_dir = os.path.dirname(path)
    base_name = os.path.splitext(os.path.basename(path))[0]
    tmp_dir = tempfile.mkdtemp(prefix="tta_reconvert_")
    text_path = os.path.join(tmp_dir, base_name + ".txt")
    with open(text_path, "w", encoding="utf-8") as f:
        f.write(text)

    start_conversion([text_path], output_dir)


def toggle_pause():
    if player.is_playing():
        path = player.current_path()
        if path:
            PlaybackMemory.save_position(path, player.position_ms())
        player.pause()
    else:
        player.resume()


def stop_playback():
    path = player.current_path()
    if path:
        PlaybackMemory.save_position(path, player.position_ms())
    player.stop()
    now_playing_var.set("Nothing playing")


# Must happen before the first window is created (see AppIcon.claim_taskbar_identity).
AppIcon.claim_taskbar_identity()

# Create the main application window
app = ttk.Window(title="Talebrew — Every story, brewed aloud.", themename=THEME, size=(1040, 680), minsize=(900, 620))
# Withdrawn immediately and only shown again once the icon is set (near the end of this
# file, right before mainloop): Windows' taskbar button caches whatever icon the window
# had the moment it first became visible, so setting the icon after a frame has already
# been shown with Tk's default "feather" icon leaves the taskbar stuck on that default
# even though the title bar updates correctly.
app.withdraw()
AppIcon.apply(app)
app_dir = AppIcon.APP_DIR
style = ttk.Style()

# Subtle background texture (faint paper grain + a large, barely-visible watermark of the
# app's own icon) -- created first so it naturally sits behind every other widget in the
# stacking order. It only shows through the margins/gaps between panels, since the panels
# themselves paint their own themed background over it -- by design, not a limitation:
# that keeps it from ever showing behind text or competing with real content.
background_photo = None


def apply_background(dark):
    global background_photo
    filename = "background-dark.png" if dark else "background-light.png"
    try:
        background_photo = tk.PhotoImage(file=os.path.join(app_dir, "assets", filename))
        background_label.configure(image=background_photo, background=style.colors.bg)
    except (tk.TclError, NameError):
        pass  # Missing/unloadable texture is cosmetic only -- never block the app.


background_label = tk.Label(app, borderwidth=0, highlightthickness=0)
background_label.place(x=0, y=0, relwidth=1, relheight=1)
apply_background(dark=False)

# Header
header_block = ttk.Frame(app)
header_block.grid(row=0, column=0, columnspan=3, sticky="w", padx=20, pady=(16, 10))
title_label = ttk.Label(header_block, text="Talebrew", font=("Palatino Linotype", 21, "bold"))
title_label.pack(anchor="w")
ttk.Label(header_block, text="Every story, brewed aloud.", bootstyle="secondary").pack(anchor="w")

settings_toggle_btn = ttk.Button(app, text="⚙ Settings", command=toggle_settings_drawer, bootstyle="secondary-outline")
settings_toggle_btn.grid(row=0, column=3, sticky="e", padx=(0, 20), pady=(18, 10))

# Files section
files_frame = ttk.Labelframe(app, text="Files to Convert", padding=10, bootstyle="primary")
files_frame.grid(row=1, column=0, sticky="nsew", padx=(20, 8), pady=8)

file_list_display = styled_listbox(files_frame, height=14)
file_list_scroll = ttk.Scrollbar(files_frame, orient="vertical", command=file_list_display.yview, bootstyle="round")
file_list_display.configure(yscrollcommand=file_list_scroll.set)
file_list_display.grid(row=0, column=0, sticky="nsew")
file_list_scroll.grid(row=0, column=1, sticky="ns")
file_list_display.bind("<<ListboxSelect>>", on_file_selection_change)
files_frame.rowconfigure(0, weight=1)
files_frame.columnconfigure(0, weight=1)

file_info_var = tk.StringVar(value="")
ttk.Label(files_frame, textvariable=file_info_var, bootstyle="secondary", justify="left").grid(
    row=1, column=0, columnspan=2, sticky="w", pady=(8, 0)
)

# Per-file voice: each queued file can use its own engine/voice, set here before
# conversion starts, instead of only the one global choice in Settings.
per_file_frame = ttk.Labelframe(files_frame, text="Selected File's Voice", padding=8, bootstyle="secondary")
per_file_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))

per_file_engine_var = tk.StringVar(value="default")
ttk.Radiobutton(per_file_frame, text="Use Settings default", variable=per_file_engine_var, value="default").pack(
    anchor="w"
)
ttk.Radiobutton(per_file_frame, text="Piper", variable=per_file_engine_var, value="piper").pack(anchor="w")
ttk.Radiobutton(per_file_frame, text="System voice", variable=per_file_engine_var, value="pyttsx3").pack(anchor="w")

per_file_voice_row = ttk.Frame(per_file_frame)
per_file_voice_row.pack(fill="x", pady=(4, 0))
ttk.Label(per_file_voice_row, text="Voice:").pack(side="left")
per_file_voice_menu = ttk.Combobox(per_file_voice_row, state="readonly", width=16)
per_file_voice_menu.pack(side="left", padx=(6, 0))

per_file_buttons = ttk.Frame(per_file_frame)
per_file_buttons.pack(fill="x", pady=(8, 0))
ttk.Button(
    per_file_buttons, text="Apply to Selected", command=apply_engine_to_selected, bootstyle="secondary-outline"
).pack(side="left", fill="x", expand=True, padx=(0, 4))
ttk.Button(
    per_file_buttons, text="Apply to All", command=apply_engine_to_all_files, bootstyle="secondary-outline"
).pack(side="left", fill="x", expand=True, padx=(4, 0))

# Conversions library section
library_frame = ttk.Labelframe(app, text="Conversions Library", padding=10, bootstyle="primary")
library_frame.grid(row=1, column=1, sticky="nsew", padx=8, pady=8)

library_tree = ttk.Treeview(library_frame, height=14, bootstyle="primary")
library_scroll = ttk.Scrollbar(library_frame, orient="vertical", command=library_tree.yview, bootstyle="round")
library_tree.configure(yscrollcommand=library_scroll.set)
library_tree.grid(row=0, column=0, sticky="nsew")
library_scroll.grid(row=0, column=1, sticky="ns")
library_tree.bind("<Double-1>", play_selected_audio)
library_frame.rowconfigure(0, weight=1)
library_frame.columnconfigure(0, weight=1)

refresh_library_btn = ttk.Button(library_frame, text="↻ Refresh", command=refresh_library, bootstyle="secondary-outline")
refresh_library_btn.grid(row=1, column=0, sticky="ew", pady=(8, 0))

reconvert_btn = ttk.Button(
    library_frame, text="🔁 Re-convert Voice", command=reconvert_selected, bootstyle="secondary-outline"
)
reconvert_btn.grid(row=2, column=0, sticky="ew", pady=(6, 0))

# Actions section
controls_frame = ttk.Labelframe(app, text="Actions", padding=10, bootstyle="primary")
controls_frame.grid(row=1, column=2, sticky="new", padx=8, pady=8)

# Player section
player_frame = ttk.Labelframe(app, text="Playback", padding=10, bootstyle="secondary")
player_frame.grid(row=2, column=2, sticky="new", padx=8, pady=(0, 8))

now_playing_var = tk.StringVar(value="Nothing playing. Double-click a file in the Conversions Library.")
now_playing_label = ttk.Label(player_frame, textvariable=now_playing_var, wraplength=180, bootstyle="secondary")
now_playing_label.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

pause_btn = ttk.Button(player_frame, text="▶ Play / Pause", command=toggle_pause, bootstyle="info-outline")
stop_playback_btn = ttk.Button(player_frame, text="■ Stop", command=stop_playback, bootstyle="danger-outline")
pause_btn.grid(row=1, column=0, sticky="ew", padx=(0, 4))
stop_playback_btn.grid(row=1, column=1, sticky="ew", padx=(4, 0))
restart_btn = ttk.Button(
    player_frame, text="⟲ Start Over", command=restart_playback, bootstyle="secondary-outline"
)
restart_btn.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0))
mini_player_btn = ttk.Button(
    player_frame, text="⤡ Mini Player", command=lambda: enter_mini_mode(), bootstyle="secondary-outline"
)
mini_player_btn.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(6, 0))
player_frame.columnconfigure(0, weight=1)
player_frame.columnconfigure(1, weight=1)

# Settings drawer (docked, hidden until toggled)
drawer_wrapper = ttk.Frame(app, width=260)
drawer_wrapper.grid(row=1, column=3, rowspan=2, sticky="nsew", padx=(0, 20), pady=8)
drawer_wrapper.grid_propagate(False)
drawer_wrapper.grid_remove()

# Log section
log_frame = ttk.Labelframe(app, text="Activity Log", padding=10, bootstyle="secondary")
log_frame.grid(row=3, column=0, columnspan=4, sticky="nsew", padx=20, pady=(8, 8))

app_log_display = styled_listbox(log_frame, height=8, font=("Consolas", 9))
log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=app_log_display.yview, bootstyle="round")
app_log_display.configure(yscrollcommand=log_scroll.set)
app_log_display.grid(row=0, column=0, sticky="nsew")
log_scroll.grid(row=0, column=1, sticky="ns")
log_frame.rowconfigure(0, weight=1)
log_frame.columnconfigure(0, weight=1)

# Directory + exit bar
bottom_bar = ttk.Frame(app, padding=(20, 0, 20, 16))
bottom_bar.grid(row=4, column=0, columnspan=4, sticky="ew")
bottom_bar.columnconfigure(0, weight=1)

download_directory_label = ttk.Label(bottom_bar, bootstyle="secondary")
download_directory_label.grid(row=0, column=0, sticky="w")

exit_btn = ttk.Button(bottom_bar, text="Exit", command=confirm_quit, bootstyle="danger-outline")
exit_btn.grid(row=0, column=1)

app.columnconfigure(0, weight=2)
app.columnconfigure(1, weight=2)
app.columnconfigure(2, weight=1)
app.columnconfigure(3, weight=0)
app.rowconfigure(1, weight=1)
app.rowconfigure(3, weight=1)

# Wire up the app's logic
logger = LogManager(app_log_display)
library = ConversionsLibrary(library_tree, FileManager.CONVERSIONS_ROOT)
explorer = FileManager.FileManager(file_list_display, app_log_display, download_directory_label, refresh_library)
converter = Converter.Converter(app_log_display)

settings_drawer = SettingsDrawer(
    drawer_wrapper, logger, explorer,
    on_theme_change=set_dark_mode, on_text_scale_change=apply_text_scale,
    on_close=toggle_settings_drawer, dark_mode=False,
)
settings_drawer.pack(fill="both", expand=True)
apply_text_scale(Config.load()["large_text"])

update_banner = UpdateBanner(app, logger, on_before_install_quit=quit_for_update)

add_files_btn = ttk.Button(controls_frame, text="+ Add Files", command=explorer.add_files, bootstyle="primary")
del_file_btn = ttk.Button(
    controls_frame, text="− Remove Selected", command=explorer.remove_file, bootstyle="secondary-outline"
)
del_all_btn = ttk.Button(
    controls_frame, text="✕ Remove All", command=explorer.clear_files, bootstyle="secondary-outline"
)
convert_btn = ttk.Button(controls_frame, text="▶ Convert to Audio", bootstyle="success", command=do_convert)

add_files_btn.grid(row=0, column=0, sticky="ew", pady=(0, 6))
del_file_btn.grid(row=1, column=0, sticky="ew", pady=(0, 6))
del_all_btn.grid(row=2, column=0, sticky="ew", pady=(0, 6))
convert_btn.grid(row=3, column=0, sticky="ew", ipady=4)
controls_frame.columnconfigure(0, weight=1)

logger.add_event("info", "Application started successfully")
SoundEffects.play("ready")
app.after(300, poll_conversions)
app.after(2000, update_banner.check_in_background)  # delayed so it never slows down launch
app.after(5000, track_playback_position)
app.after(300, poll_file_info)

pending_batch = ConversionQueue.load()
if pending_batch:
    resumable_files = [f for f in pending_batch["files"] if os.path.isfile(f)]
    missing_count = len(pending_batch["files"]) - len(resumable_files)
    if missing_count:
        logger.add_event(
            "warn", f"{missing_count} file(s) from an interrupted conversion could no longer be found",
        )
    if resumable_files:
        logger.add_event(
            "info", f"Resuming {len(resumable_files)} file(s) from a conversion interrupted last session",
        )
        start_conversion(resumable_files, pending_batch["output_dir"])
    else:
        ConversionQueue.clear()

if Config.load()["start_in_mini_mode"]:
    enter_mini_mode(persist=False)  # already persisted from last session; no need to re-save
else:
    app.deiconify()  # first time the main window is shown -- see the withdraw() note above

app.mainloop()
