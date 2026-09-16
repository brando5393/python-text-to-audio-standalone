import tkinter as tk

import ttkbootstrap as ttk


class MiniPlayer(ttk.Toplevel):
    """A small, always-on-top playback-only window -- for keeping Talebrew out of the
    way while listening, without losing access to play/pause/stop."""

    def __init__(self, parent, player, now_playing_var, on_expand):
        super().__init__(parent)
        self.title("Talebrew Mini Player")
        self.geometry("300x130")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.player = player
        self.on_expand = on_expand
        self.protocol("WM_DELETE_WINDOW", on_expand)  # closing the mini player returns to the full window

        frame = ttk.Frame(self, padding=12)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Talebrew", font=("Palatino Linotype", 13, "bold")).pack(anchor="w")
        now_playing_label = ttk.Label(frame, textvariable=now_playing_var, wraplength=270, bootstyle="secondary")
        now_playing_label.pack(anchor="w", fill="x", pady=(4, 10))

        controls = ttk.Frame(frame)
        controls.pack(fill="x")
        ttk.Button(controls, text="▶ Play / Pause", command=self._toggle_pause, bootstyle="info-outline").pack(
            side="left", fill="x", expand=True, padx=(0, 4)
        )
        ttk.Button(controls, text="■ Stop", command=self._stop, bootstyle="danger-outline").pack(
            side="left", fill="x", expand=True, padx=(4, 0)
        )

        ttk.Button(frame, text="⤢ Show Full App", command=on_expand, bootstyle="secondary-outline").pack(
            fill="x", pady=(10, 0)
        )

    def _toggle_pause(self):
        if self.player.is_playing():
            self.player.pause()
        else:
            self.player.resume()

    def _stop(self):
        self.player.stop()
