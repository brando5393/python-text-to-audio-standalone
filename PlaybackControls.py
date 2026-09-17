"""A compact "Speed" / "Tone" widget pair, live-bound to an AudioPlayer and persisted to
Config -- used by both the main window's and the Mini Player's Playback panels, so the
same widget-building code (and the same plain-language band labels, e.g. "1.20x
(Slightly faster)") isn't duplicated between them.

Speed and Tone used to be synthesis-time sliders in Settings' Voice tab (SettingsDrawer.py
had its own _SPEED_BANDS/_band_label for this). They're live playback controls now --
AudioPlayer.set_speed()/set_tone() apply instantly to whatever's currently playing or
paused, no re-conversion needed -- so they moved to where playback itself happens.
"""

import tkinter as tk

import ttkbootstrap as ttk

import Config

SPEED_BANDS = [
    (0.75, "Slower"),
    (0.9, "Slightly slower"),
    (1.1, "Normal"),
    (1.5, "Slightly faster"),
    (float("inf"), "Faster"),
]
TONE_BANDS = [
    (-3.0, "Deeper"),
    (-0.5, "Slightly deeper"),
    (0.5, "Normal"),
    (3.0, "Slightly higher"),
    (float("inf"), "Higher"),
]


def band_label(value, bands):
    for threshold, label in bands:
        if value <= threshold:
            return label
    return bands[-1][1]


def build(parent, player):
    """Builds the Speed/Tone controls into `parent` and wires them live to `player`.
    Starts from (and saves back to) Config's last-used playback_speed/playback_tone, so
    the chosen values persist across restarts and files. Returns the container frame --
    callers just need to grid/pack it into their own layout."""
    settings = Config.load()
    frame = ttk.Frame(parent)
    frame.columnconfigure(0, weight=1)
    frame.columnconfigure(1, weight=0)

    speed_var = tk.DoubleVar(value=settings["playback_speed"])
    tone_var = tk.DoubleVar(value=settings["playback_tone"])

    ttk.Label(frame, text="Speed", bootstyle="secondary").grid(row=0, column=0, sticky="w")
    speed_label_var = tk.StringVar()
    ttk.Label(frame, textvariable=speed_label_var, bootstyle="secondary").grid(row=0, column=1, sticky="e")
    ttk.Scale(frame, variable=speed_var, from_=0.5, to=2.5, orient="horizontal").grid(
        row=1, column=0, columnspan=2, sticky="ew", pady=(0, 6)
    )

    ttk.Label(frame, text="Tone", bootstyle="secondary").grid(row=2, column=0, sticky="w")
    tone_label_var = tk.StringVar()
    ttk.Label(frame, textvariable=tone_label_var, bootstyle="secondary").grid(row=2, column=1, sticky="e")
    ttk.Scale(frame, variable=tone_var, from_=-6, to=6, orient="horizontal").grid(
        row=3, column=0, columnspan=2, sticky="ew"
    )

    def _apply_speed(*_args):
        value = round(speed_var.get(), 2)
        speed_label_var.set(f"{value:.2f}x ({band_label(value, SPEED_BANDS)})")
        player.set_speed(value)
        current = Config.load()
        current["playback_speed"] = value
        Config.save(current)

    def _apply_tone(*_args):
        value = round(tone_var.get(), 2)
        tone_label_var.set(f"{value:+.1f} st ({band_label(value, TONE_BANDS)})")
        player.set_tone(value)
        current = Config.load()
        current["playback_tone"] = value
        Config.save(current)

    speed_var.trace_add("write", _apply_speed)
    tone_var.trace_add("write", _apply_tone)

    player.set_speed(speed_var.get())
    player.set_tone(tone_var.get())
    _apply_speed()
    _apply_tone()

    # Exposed for tests (and any caller that wants to drive the sliders programmatically)
    # rather than having to dig through frame.winfo_children() to find them.
    frame.speed_var = speed_var
    frame.tone_var = tone_var

    return frame
