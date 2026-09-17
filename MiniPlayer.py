import tkinter as tk

import ttkbootstrap as ttk

import AppIcon
import PlaybackControls
import SleepTimer

PROGRESS_POLL_MS = 500
SLEEP_TIMER_TICK_MS = 1000


def format_time(ms):
    total_seconds = int(ms) // 1000
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes}:{seconds:02d}"


class MiniPlayer(ttk.Toplevel):
    """A small, always-on-top playback-only window -- for keeping Talebrew out of the
    way while listening, without losing access to play/pause/stop/seek."""

    def __init__(self, parent, player, now_playing_var, on_expand, sleep_timer=None):
        super().__init__(parent)
        self.title("Talebrew Mini Player")
        AppIcon.apply(self)
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.player = player
        self.on_expand = on_expand
        # Shares the main window's SleepTimer instance (passed in by main.py) so a
        # timer started from one window is reflected in the other -- both windows
        # control the same single playback session, so their sleep timers must too.
        # Falls back to a private instance so this class stays constructible on its
        # own, e.g. from tests that don't wire up a shared timer.
        self.sleep_timer = sleep_timer if sleep_timer is not None else SleepTimer.SleepTimer()
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

        self.sleep_timer_choice_var = tk.StringVar(value=SleepTimer.LABELS_BY_MINUTES[0])
        self.sleep_timer_menu = ttk.Combobox(
            frame, textvariable=self.sleep_timer_choice_var, state="readonly", values=SleepTimer.CHOICES,
        )
        self.sleep_timer_menu.bind("<<ComboboxSelected>>", self._on_sleep_timer_choice)
        self.sleep_timer_menu.pack(fill="x", pady=(6, 0))

        # Speed/Tone: live playback controls, mirroring the main window's Playback
        # panel -- both just call the same shared AudioPlayer, so a change made in
        # either window takes effect immediately regardless of which one is open.
        PlaybackControls.build(frame, player).pack(fill="x", pady=(10, 0))

        # Sized to its own actual content rather than a hardcoded guess -- a fixed
        # literal here previously drifted out of sync with what got added to the frame
        # over time (the seek bar and time readout ended up needing more height than the
        # window had), silently clipping the Play/Pause, Stop, Start Over, and Show Full
        # App buttons off the bottom of a non-resizable window. This also keeps it
        # correct if "Larger text" (see main.py's apply_text_scale) is on, since that
        # grows every widget's natural size too.
        self.update_idletasks()
        self.geometry(f"{self.winfo_reqwidth()}x{self.winfo_reqheight()}")

        self.after(PROGRESS_POLL_MS, self._update_progress)
        self.after(SLEEP_TIMER_TICK_MS, self._tick_sleep_timer)

    def _on_sleep_timer_choice(self, _event=None):
        minutes = SleepTimer.MINUTES_BY_LABEL.get(self.sleep_timer_choice_var.get(), 0)
        if minutes <= 0:
            self.sleep_timer.cancel()
        else:
            self.sleep_timer.start(minutes)

    def _tick_sleep_timer(self):
        if self.sleep_timer.is_active():
            if self.sleep_timer.is_expired():
                self.sleep_timer.cancel()
                self.sleep_timer_choice_var.set(SleepTimer.LABELS_BY_MINUTES[0])
                if self.player.is_playing():
                    self.player.pause()  # pause, not stop -- keeps the resume position
            else:
                self.sleep_timer_choice_var.set(f"Sleep: {self.sleep_timer.remaining_minutes_label()} min left")
        if self.winfo_exists():
            self.after(SLEEP_TIMER_TICK_MS, self._tick_sleep_timer)

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
