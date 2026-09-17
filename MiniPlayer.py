import tkinter as tk

import ttkbootstrap as ttk

import AppIcon
import PlaybackControls

PROGRESS_POLL_MS = 500


def format_time(ms):
    total_seconds = int(ms) // 1000
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes}:{seconds:02d}"


class MiniPlayer(ttk.Toplevel):
    """A small, always-on-top playback-only window -- for keeping Talebrew out of the
    way while listening, without losing access to play/pause/stop/seek."""

    def __init__(self, parent, player, now_playing_var, on_expand):
        super().__init__(parent)
        self.title("Talebrew Mini Player")
        self.geometry("300x260")
        AppIcon.apply(self)
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.player = player
        self.on_expand = on_expand
        self.protocol("WM_DELETE_WINDOW", on_expand)  # closing the mini player returns to the full window
        self._dragging = False

        frame = ttk.Frame(self, padding=12)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Talebrew", font=("Palatino Linotype", 13, "bold")).pack(anchor="w")
        now_playing_label = ttk.Label(frame, textvariable=now_playing_var, wraplength=270, bootstyle="secondary")
        now_playing_label.pack(anchor="w", fill="x", pady=(4, 8))

        self.progress_var = tk.DoubleVar(value=0)
        self.progress_scale = ttk.Scale(
            frame, variable=self.progress_var, from_=0, to=100, orient="horizontal", bootstyle="info",
        )
        self.progress_scale.pack(fill="x")
        self.progress_scale.bind("<ButtonPress-1>", self._start_drag)
        self.progress_scale.bind("<ButtonRelease-1>", self._end_drag)

        self.time_var = tk.StringVar(value="0:00 / 0:00")
        ttk.Label(frame, textvariable=self.time_var, bootstyle="secondary").pack(anchor="e", pady=(2, 8))

        controls = ttk.Frame(frame)
        controls.pack(fill="x")
        ttk.Button(controls, text="▶ Play / Pause", command=self._toggle_pause, bootstyle="info-outline").pack(
            side="left", fill="x", expand=True, padx=(0, 4)
        )
        ttk.Button(controls, text="■ Stop", command=self._stop, bootstyle="danger-outline").pack(
            side="left", fill="x", expand=True, padx=(4, 0)
        )

        ttk.Button(frame, text="⟲ Start Over", command=self._restart, bootstyle="secondary-outline").pack(
            fill="x", pady=(6, 0)
        )
        ttk.Button(frame, text="⤢ Show Full App", command=on_expand, bootstyle="secondary-outline").pack(
            fill="x", pady=(6, 0)
        )

        # Speed/Tone: live playback controls, mirroring the main window's Playback
        # panel -- both just call the same shared AudioPlayer, so a change made in
        # either window takes effect immediately regardless of which one is open.
        PlaybackControls.build(frame, player).pack(fill="x", pady=(10, 0))

        self.after(PROGRESS_POLL_MS, self._update_progress)

    def _toggle_pause(self):
        if self.player.is_playing():
            self.player.pause()
        else:
            self.player.resume()

    def _stop(self):
        self.player.stop()
        self.progress_var.set(0)
        self.time_var.set("0:00 / 0:00")

    def _restart(self):
        if self.player.current_path():
            self.player.seek_ms(0)

    def _start_drag(self, _event):
        self._dragging = True

    def _end_drag(self, _event):
        self._dragging = False
        length = self.player.length_ms()
        if length > 0:
            self.player.seek_ms(self.progress_var.get() / 100 * length)

    def _update_progress(self):
        if not self._dragging:
            length = self.player.length_ms()
            position = self.player.position_ms()
            self.progress_var.set(100 * position / length if length else 0)
            self.time_var.set(f"{format_time(position)} / {format_time(length)}")
        if self.winfo_exists():
            self.after(PROGRESS_POLL_MS, self._update_progress)
