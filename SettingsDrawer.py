import os
import queue
import threading
import tkinter as tk
from tkinter import messagebox

import ttkbootstrap as ttk

import Config
import PiperEngine
from AudioPlayer import AudioPlayer

# Piper's own docs describe noise_scale (0.0-1.0+) as "generator noise" controlling vocal
# variation, and length_scale as speaking rate; the app maps length_scale to a more
# intuitive 0.5-2.0 "speed" (inverted: higher speed -> shorter length_scale -> faster
# speech) with 1.0 as Piper's own natural-rate default. These bands turn the raw number
# into a plain-language description next to each slider, since "0.83" alone doesn't tell
# a listener anything about what they'll actually hear change.
_SPEED_BANDS = [
    (0.75, "Slower"),
    (0.9, "Slightly slower"),
    (1.1, "Normal"),
    (1.5, "Slightly faster"),
    (float("inf"), "Faster"),
]
_EXPRESSIVENESS_BANDS = [
    (0.45, "Flat, monotone"),
    (0.6, "Calm, steady"),
    (0.75, "Balanced, natural"),
    (0.9, "Expressive"),
    (float("inf"), "Highly varied"),
]


def _band_label(value, bands):
    for threshold, label in bands:
        if value <= threshold:
            return label
    return bands[-1][1]


class SettingsDrawer(ttk.Frame):
    """A docked side panel (rather than a popup) for voice and app settings.

    Changes save immediately as you make them -- there's no separate Save button,
    since a drawer you can leave open while you work reads as "live", not "pending".
    """

    def __init__(self, parent, logger, explorer, on_theme_change, on_text_scale_change, on_close, dark_mode):
        super().__init__(parent, padding=12)
        self.logger = logger
        self.explorer = explorer
        self.on_theme_change = on_theme_change
        self.on_text_scale_change = on_text_scale_change
        self.settings = Config.load()
        self._download_events = queue.Queue()
        self._preview_player = AudioPlayer(alias="texttoaudio_preview")  # own alias -- must
        # never share one with the main player, or previewing a voice here would stop
        # whatever the user is actually listening to (and vice versa)
        self._loading = True  # suppresses auto-save while initial values are being set

        self.engine_var = tk.StringVar(value=self.settings["engine"])
        self.voice_var = tk.StringVar(value=self.settings["voice"])
        self.speed_var = tk.DoubleVar(value=self.settings["speed"])
        self.expr_var = tk.DoubleVar(value=self.settings["expressiveness"])
        self.large_text_var = tk.BooleanVar(value=self.settings["large_text"])
        self.sound_effects_var = tk.BooleanVar(value=self.settings["sound_effects_enabled"])
        self.appearance_var = tk.StringVar(value="dark" if dark_mode else "light")

        self._build_header(on_close)

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, pady=(10, 0))
        voice_tab = ttk.Frame(notebook, padding=10)
        app_tab = ttk.Frame(notebook, padding=10)
        accessibility_tab = ttk.Frame(notebook, padding=10)
        notebook.add(voice_tab, text="Voice")
        notebook.add(app_tab, text="App")
        notebook.add(accessibility_tab, text="Accessibility")

        self._build_engine_section(voice_tab)
        self._build_voice_section(voice_tab)
        self._build_tuning_section(voice_tab)
        self._build_app_section(app_tab)
        self._build_accessibility_section(accessibility_tab)

        self._refresh_voice_list()
        self._loading = False

        for var in (
            self.engine_var, self.voice_var, self.speed_var, self.expr_var,
            self.large_text_var, self.sound_effects_var,
        ):
            var.trace_add("write", lambda *_args: self._save())

        self.after(200, self._poll_downloads)

    def refresh_from_disk(self):
        """Re-reads settings from disk into the drawer's controls.

        The drawer is created once and toggled visible/hidden rather than rebuilt, so
        without this its fields would go stale the moment anything outside the drawer
        changes config.json -- and since all four fields save together, touching even
        one unrelated control (e.g. the speed slider) would silently overwrite the
        others back to those stale values. Called every time the drawer is opened.
        """
        self._loading = True
        settings = Config.load()
        self.engine_var.set(settings["engine"])
        self._refresh_voice_list()
        self.voice_var.set(settings["voice"])
        self.speed_var.set(settings["speed"])
        self.expr_var.set(settings["expressiveness"])
        self.large_text_var.set(settings["large_text"])
        self.sound_effects_var.set(settings["sound_effects_enabled"])
        self._update_engine_status()
        self._loading = False

    def _build_header(self, on_close):
        row = ttk.Frame(self)
        row.pack(fill="x")
        ttk.Label(row, text="Settings", font=("Palatino Linotype", 14, "bold")).pack(side="left")
        ttk.Button(row, text="Close", command=on_close, bootstyle="secondary-outline").pack(side="right")

    # -- Voice tab -----------------------------------------------------------------

    def _build_engine_section(self, parent):
        frame = ttk.Labelframe(parent, text="Engine", padding=10, bootstyle="primary")
        frame.pack(fill="x")
        ttk.Radiobutton(
            frame, text="Piper (natural, offline neural voice)", variable=self.engine_var, value="piper"
        ).pack(anchor="w")
        ttk.Radiobutton(
            frame, text="System voice (pyttsx3 / Windows SAPI, always available)",
            variable=self.engine_var, value="pyttsx3",
        ).pack(anchor="w")

        self.engine_status = ttk.Label(frame, bootstyle="secondary")
        self.engine_status.pack(anchor="w", pady=(6, 0))
        self.install_engine_btn = ttk.Button(
            frame, text="⬇ Install Piper Engine", command=self._install_engine, bootstyle="info-outline"
        )
        self._update_engine_status()

    def _update_engine_status(self):
        engine_installed = PiperEngine.is_engine_installed()
        voice_installed = PiperEngine.is_voice_installed(self.voice_var.get()) if self.voice_var.get() else False

        if not engine_installed:
            self.engine_status.configure(
                text="Piper engine: not installed yet (~21 MB download)", bootstyle="secondary"
            )
            self.install_engine_btn.pack(anchor="w", pady=(4, 0))
        elif not voice_installed:
            self.engine_status.configure(
                text="Piper engine installed, but no voice is downloaded yet (see below)", bootstyle="warning"
            )
            self.install_engine_btn.pack_forget()
        elif self.engine_var.get() == "piper":
            self.engine_status.configure(text=f"Ready: using {self.voice_var.get()}", bootstyle="success")
            self.install_engine_btn.pack_forget()
        else:
            self.engine_status.configure(
                text=f"Piper is ready ({self.voice_var.get()}), but System voice is selected above",
                bootstyle="secondary",
            )
            self.install_engine_btn.pack_forget()

    def _install_engine(self):
        self.install_engine_btn.configure(state="disabled", text="Installing...")

        def work():
            try:
                PiperEngine.install_engine()
                self._download_events.put(("engine_done", None))
            except Exception as e:
                self._download_events.put(("engine_error", str(e)))

        threading.Thread(target=work, daemon=True).start()

    def _build_voice_section(self, parent):
        frame = ttk.Labelframe(parent, text="Voice", padding=10, bootstyle="primary")
        frame.pack(fill="x", pady=(10, 0))

        row = ttk.Frame(frame)
        row.pack(fill="x")
        ttk.Label(row, text="Active voice:").pack(side="left")
        self.voice_menu = ttk.Combobox(row, textvariable=self.voice_var, state="readonly", width=20)
        self.voice_menu.pack(side="left", padx=(6, 6))
        # Every other icon button in the app pairs its glyph with a word (e.g. "⬇ Get",
        # "▶ Preview This Voice") -- this one used to be a bare "✕" with no accessible
        # name beyond that glyph, which tells a screen-reader user (or anyone who can't
        # see it well enough to guess) nothing about what it does.
        ttk.Button(
            row, text="✕ Delete", width=10, command=self._delete_voice, bootstyle="danger-outline"
        ).pack(side="left")

        row2 = ttk.Frame(frame)
        row2.pack(fill="x", pady=(8, 0))
        ttk.Label(row2, text="Download:").pack(side="left")
        self.download_choice = ttk.Combobox(
            row2, values=list(PiperEngine.CURATED_VOICES.keys()), state="readonly", width=18
        )
        self.download_choice.pack(side="left", padx=(6, 6))
        self.download_btn = ttk.Button(row2, text="⬇ Get", command=self._download_voice, bootstyle="info-outline")
        self.download_btn.pack(side="left")

        self.preview_btn = ttk.Button(
            frame, text="▶ Preview This Voice", command=self._preview_voice, bootstyle="secondary-outline"
        )
        self.preview_btn.pack(fill="x", pady=(6, 0))
        ttk.Label(
            frame,
            text="Hear a short sample of the selected download choice, without downloading its full voice model.",
            bootstyle="secondary", wraplength=220,
        ).pack(anchor="w", pady=(2, 0))

        self.download_progress = ttk.Progressbar(frame, mode="determinate", maximum=100)
        self.download_progress.pack(fill="x", pady=(8, 0))

        ttk.Label(
            frame,
            text='Tip: "low" quality voices synthesize much faster than "high" ones (roughly '
            "5x faster, measured) -- worth trying for long documents if speed matters more than "
            "how natural the voice sounds.",
            bootstyle="secondary", wraplength=220,
        ).pack(anchor="w", pady=(8, 0))

    def _refresh_voice_list(self):
        voices = PiperEngine.list_installed_voices()
        self.voice_menu.configure(values=voices)
        if self.voice_var.get() not in voices:
            self.voice_var.set(voices[0] if voices else "")

    def _delete_voice(self):
        voice_id = self.voice_var.get()
        if not voice_id:
            return
        size_mb = PiperEngine.voice_size_bytes(voice_id) / (1024 * 1024)
        confirmed = messagebox.askyesno(
            "Delete Voice",
            f"Delete '{voice_id}' and free up {size_mb:.0f} MB?\n\n"
            "You can download it again later from the list below.",
        )
        if not confirmed:
            return
        PiperEngine.delete_voice(voice_id)
        self.logger.add_event("info", f"Deleted voice: {voice_id}")
        self._refresh_voice_list()

    def _download_voice(self):
        label = self.download_choice.get()
        if not label:
            return
        voice_key = PiperEngine.CURATED_VOICES[label]
        self.download_btn.configure(state="disabled")

        def work():
            try:
                voice_id = PiperEngine.download_voice(
                    voice_key, lambda frac: self._download_events.put(("progress", frac))
                )
                self._download_events.put(("voice_done", voice_id))
            except Exception as e:
                self._download_events.put(("voice_error", str(e)))

        threading.Thread(target=work, daemon=True).start()

    def _preview_voice(self):
        label = self.download_choice.get()
        if not label:
            self.logger.add_event("warn", "Pick a voice from the download list first, to preview it")
            return
        voice_key = PiperEngine.CURATED_VOICES[label]
        self.preview_btn.configure(state="disabled", text="Loading preview...")

        def work():
            try:
                sample_path = PiperEngine.download_sample(voice_key)
                self._download_events.put(("preview_ready", sample_path))
            except Exception as e:
                self._download_events.put(("preview_error", str(e)))

        threading.Thread(target=work, daemon=True).start()

    def _poll_downloads(self):
        try:
            while True:
                kind, payload = self._download_events.get_nowait()
                if kind == "progress":
                    self.download_progress["value"] = payload * 100
                elif kind == "voice_done":
                    self.download_progress["value"] = 100
                    self.download_btn.configure(state="normal")
                    self._refresh_voice_list()
                    self.voice_var.set(payload)
                    self.logger.add_event("info", f"Downloaded voice: {payload}")
                elif kind == "voice_error":
                    self.download_btn.configure(state="normal")
                    self.logger.add_event("error", "Failed to download voice", payload)
                elif kind == "preview_ready":
                    self.preview_btn.configure(state="normal", text="▶ Preview This Voice")
                    try:
                        self._preview_player.play(payload)
                    except Exception as e:
                        self.logger.add_event("error", "Failed to play voice preview", str(e))
                elif kind == "preview_error":
                    self.preview_btn.configure(state="normal", text="▶ Preview This Voice")
                    self.logger.add_event("error", "Failed to load voice preview", payload)
                elif kind == "engine_done":
                    self._update_engine_status()
                    self.logger.add_event("info", "Piper engine installed")
                elif kind == "engine_error":
                    self.install_engine_btn.configure(state="normal", text="Install Piper Engine")
                    self.logger.add_event("error", "Failed to install Piper engine", payload)
        except queue.Empty:
            pass
        if self.winfo_exists():
            self.after(200, self._poll_downloads)

    def _build_tuning_section(self, parent):
        frame = ttk.Labelframe(parent, text="Tuning (Piper voices)", padding=10, bootstyle="primary")
        frame.pack(fill="x", pady=(10, 0))

        ttk.Label(frame, text="Speed").pack(anchor="w")
        ttk.Scale(frame, variable=self.speed_var, from_=0.5, to=2.0, orient="horizontal").pack(fill="x")
        self.speed_label_var = tk.StringVar()
        ttk.Label(frame, textvariable=self.speed_label_var, bootstyle="secondary").pack(anchor="w")

        ttk.Label(frame, text="Expressiveness").pack(anchor="w", pady=(8, 0))
        ttk.Scale(frame, variable=self.expr_var, from_=0.3, to=1.0, orient="horizontal").pack(fill="x")
        self.expr_label_var = tk.StringVar()
        ttk.Label(frame, textvariable=self.expr_label_var, bootstyle="secondary").pack(anchor="w")

        self.speed_var.trace_add("write", self._update_speed_label)
        self.expr_var.trace_add("write", self._update_expr_label)
        self._update_speed_label()
        self._update_expr_label()

    def _update_speed_label(self, *_args):
        value = self.speed_var.get()
        self.speed_label_var.set(f"{value:.2f}x ({_band_label(value, _SPEED_BANDS)})")

    def _update_expr_label(self, *_args):
        value = self.expr_var.get()
        self.expr_label_var.set(f"{value:.2f} ({_band_label(value, _EXPRESSIVENESS_BANDS)})")

    def _save(self):
        # Merges onto the current settings on disk (rather than constructing a fixed
        # field list) so a setting the drawer doesn't manage -- like start_in_mini_mode,
        # set elsewhere in the app -- is never accidentally dropped when the drawer
        # saves. This bit repeatedly: every time a new Config field was added, every
        # save/reset call site here needed updating too, or Config.save() (which
        # requires every DEFAULTS key present) would KeyError.
        if self._loading:
            return
        current = Config.load()
        current.update({
            "engine": self.engine_var.get(),
            "voice": self.voice_var.get(),
            "speed": round(self.speed_var.get(), 2),
            "expressiveness": round(self.expr_var.get(), 2),
            "large_text": self.large_text_var.get(),
            "sound_effects_enabled": self.sound_effects_var.get(),
        })
        Config.save(current)
        self.on_text_scale_change(self.large_text_var.get())
        self._update_engine_status()

    # -- App tab ---------------------------------------------------------------------

    def _build_app_section(self, parent):
        location = ttk.Labelframe(parent, text="Save Location", padding=10, bootstyle="primary")
        location.pack(fill="x")
        ttk.Button(
            location, text="⚏ Change Save Folder", command=self.explorer.set_download_directory,
            bootstyle="secondary-outline",
        ).pack(fill="x", pady=(0, 6))
        ttk.Button(
            location, text="+ New Folder", command=self.explorer.create_subfolder, bootstyle="secondary-outline"
        ).pack(fill="x", pady=(0, 6))
        ttk.Button(
            location, text="↗ Open in File Explorer", command=self._open_save_folder, bootstyle="secondary-outline"
        ).pack(fill="x")

        appearance = ttk.Labelframe(parent, text="Appearance", padding=10, bootstyle="primary")
        appearance.pack(fill="x", pady=(10, 0))
        ttk.Radiobutton(
            appearance, text="Light", variable=self.appearance_var, value="light", command=self._apply_appearance
        ).pack(anchor="w")
        ttk.Radiobutton(
            appearance, text="Dark", variable=self.appearance_var, value="dark", command=self._apply_appearance
        ).pack(anchor="w")

        reset = ttk.Labelframe(parent, text="Reset", padding=10, bootstyle="danger")
        reset.pack(fill="x", pady=(10, 0))
        ttk.Button(
            reset, text="↺ Reset Save Folder", command=self._reset_save_folder, bootstyle="secondary-outline"
        ).pack(fill="x", pady=(0, 6))
        ttk.Button(
            reset, text="↺ Reset Voice Settings", command=self._reset_voice_settings, bootstyle="secondary-outline"
        ).pack(fill="x", pady=(0, 6))
        ttk.Button(
            reset, text="↺ Reset Appearance", command=self._reset_appearance, bootstyle="secondary-outline"
        ).pack(fill="x", pady=(0, 10))
        ttk.Button(reset, text="↺ Reset Everything", command=self._reset_everything, bootstyle="danger").pack(
            fill="x"
        )

    def _open_save_folder(self):
        try:
            os.startfile(self.explorer.download_directory)
        except Exception as e:
            self.logger.add_event("error", "Failed to open folder", str(e))

    def _reset_save_folder(self):
        if messagebox.askyesno("Reset Save Folder", "Reset the save folder back to the default Conversions folder?"):
            self.explorer.reset_download_directory()

    def _reset_voice_settings(self):
        if messagebox.askyesno("Reset Voice Settings", "Reset engine, voice, speed, and expressiveness to defaults?"):
            self._loading = True
            current = Config.load()
            current.update({
                "engine": Config.DEFAULTS["engine"],
                "voice": Config.DEFAULTS["voice"],
                "speed": Config.DEFAULTS["speed"],
                "expressiveness": Config.DEFAULTS["expressiveness"],
            })
            Config.save(current)
            self.engine_var.set(Config.DEFAULTS["engine"])
            self._refresh_voice_list()
            self.voice_var.set(Config.DEFAULTS["voice"])
            self.speed_var.set(Config.DEFAULTS["speed"])
            self.expr_var.set(Config.DEFAULTS["expressiveness"])
            self._loading = False
            self.logger.add_event("info", "Voice settings reset to defaults")

    def _reset_appearance(self):
        if messagebox.askyesno("Reset Appearance", "Switch back to the default light appearance?"):
            self.appearance_var.set("light")
            self._apply_appearance()

    def _reset_everything(self):
        if messagebox.askyesno(
            "Reset Everything",
            "Reset save folder, voice settings, appearance, and accessibility options all back to their defaults?",
        ):
            self.explorer.reset_download_directory()
            self._loading = True
            Config.save(dict(Config.DEFAULTS))
            self.engine_var.set(Config.DEFAULTS["engine"])
            self._refresh_voice_list()
            self.voice_var.set(Config.DEFAULTS["voice"])
            self.speed_var.set(Config.DEFAULTS["speed"])
            self.expr_var.set(Config.DEFAULTS["expressiveness"])
            self.large_text_var.set(Config.DEFAULTS["large_text"])
            self.on_text_scale_change(Config.DEFAULTS["large_text"])
            self.sound_effects_var.set(Config.DEFAULTS["sound_effects_enabled"])
            self._loading = False
            self.appearance_var.set("light")
            self._apply_appearance()
            self.logger.add_event("info", "All settings reset to defaults")

    def _apply_appearance(self):
        self.on_theme_change(self.appearance_var.get() == "dark")

    # -- Accessibility tab -------------------------------------------------------------

    def _build_accessibility_section(self, parent):
        text_frame = ttk.Labelframe(parent, text="Readability", padding=10, bootstyle="primary")
        text_frame.pack(fill="x")
        ttk.Checkbutton(
            text_frame, text="Larger text throughout the app", variable=self.large_text_var, bootstyle="round-toggle"
        ).pack(anchor="w")

        sound_frame = ttk.Labelframe(parent, text="Sound Cues", padding=10, bootstyle="primary")
        sound_frame.pack(fill="x", pady=(10, 0))
        ttk.Checkbutton(
            sound_frame, text="Play a sound for app ready / conversion done / errors / exit",
            variable=self.sound_effects_var, bootstyle="round-toggle",
        ).pack(anchor="w")

        statement_frame = ttk.Labelframe(parent, text="Accessibility Statement", padding=10, bootstyle="primary")
        statement_frame.pack(fill="both", expand=True, pady=(10, 0))
        statement = tk.Text(statement_frame, wrap="word", height=14, borderwidth=0, highlightthickness=0)
        statement.insert("1.0", ACCESSIBILITY_STATEMENT)
        statement.configure(state="disabled")
        statement.pack(fill="both", expand=True)


ACCESSIBILITY_STATEMENT = """Talebrew aims to be usable with a keyboard alone and to keep text \
readable at a glance. Here's what's actually been verified, and what isn't there yet.

Verified:
- Every control (buttons, dropdowns, sliders) can be reached and operated with Tab / Shift+Tab \
and Enter/Space, and file and folder lists respond to arrow keys once focused.
- Text and background colors meet WCAG AA contrast (4.5:1) in both the light and dark themes. \
This was measured directly: one accent color fell short at 2.25:1 and was darkened until it passed.
- Status is never color only. Log entries carry a text label (INFO, WARNING, ERROR) alongside \
their color.
- The "Larger text" toggle above scales UI text app-wide, and speech rate is adjustable \
separately in the Voice tab.
- Sound cues mark app-ready, conversion-done, error, and exit moments audibly, which helps if \
the window isn't in view. Toggle them off above if you'd rather not have them.

Known limitation:
- Talebrew is built with Tkinter, which has limited support for Windows screen readers (Narrator, \
NVDA, JAWS) compared to native Windows apps: it doesn't fully implement the accessibility APIs \
those tools rely on. If you use a screen reader and hit rough edges, please open an issue."""
