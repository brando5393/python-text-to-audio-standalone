import os
import queue
import threading
import tkinter as tk

import ttkbootstrap as ttk

import Config
import PiperEngine


class SettingsDrawer(ttk.Frame):
    """A docked side panel (rather than a popup) for voice and app settings.

    Changes save immediately as you make them -- there's no separate Save button,
    since a drawer you can leave open while you work reads as "live", not "pending".
    """

    def __init__(self, parent, logger, explorer, on_theme_change, on_close, dark_mode):
        super().__init__(parent, padding=12)
        self.logger = logger
        self.explorer = explorer
        self.on_theme_change = on_theme_change
        self.settings = Config.load()
        self._download_events = queue.Queue()
        self._loading = True  # suppresses auto-save while initial values are being set

        self.engine_var = tk.StringVar(value=self.settings["engine"])
        self.voice_var = tk.StringVar(value=self.settings["voice"])
        self.speed_var = tk.DoubleVar(value=self.settings["speed"])
        self.expr_var = tk.DoubleVar(value=self.settings["expressiveness"])
        self.appearance_var = tk.StringVar(value="dark" if dark_mode else "light")

        self._build_header(on_close)

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, pady=(10, 0))
        voice_tab = ttk.Frame(notebook, padding=10)
        app_tab = ttk.Frame(notebook, padding=10)
        notebook.add(voice_tab, text="Voice")
        notebook.add(app_tab, text="App")

        self._build_engine_section(voice_tab)
        self._build_voice_section(voice_tab)
        self._build_tuning_section(voice_tab)
        self._build_app_section(app_tab)

        self._refresh_voice_list()
        self._loading = False

        for var in (self.engine_var, self.voice_var, self.speed_var, self.expr_var):
            var.trace_add("write", lambda *_args: self._save())

        self.after(200, self._poll_downloads)

    def _build_header(self, on_close):
        row = ttk.Frame(self)
        row.pack(fill="x")
        ttk.Label(row, text="Settings", font=("Georgia", 13, "bold")).pack(side="left")
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
            frame, text="Install Piper Engine", command=self._install_engine, bootstyle="info-outline"
        )
        self._update_engine_status()

    def _update_engine_status(self):
        if PiperEngine.is_engine_installed():
            self.engine_status.configure(text="Piper engine: installed")
            self.install_engine_btn.pack_forget()
        else:
            self.engine_status.configure(text="Piper engine: not installed yet (~21 MB download)")
            self.install_engine_btn.pack(anchor="w", pady=(4, 0))

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
        self.voice_menu.pack(side="left", padx=(6, 0))

        row2 = ttk.Frame(frame)
        row2.pack(fill="x", pady=(8, 0))
        ttk.Label(row2, text="Download:").pack(side="left")
        self.download_choice = ttk.Combobox(
            row2, values=list(PiperEngine.CURATED_VOICES.keys()), state="readonly", width=18
        )
        self.download_choice.pack(side="left", padx=(6, 6))
        self.download_btn = ttk.Button(row2, text="Get", command=self._download_voice, bootstyle="info-outline")
        self.download_btn.pack(side="left")

        self.download_progress = ttk.Progressbar(frame, mode="determinate", maximum=100)
        self.download_progress.pack(fill="x", pady=(8, 0))

    def _refresh_voice_list(self):
        voices = PiperEngine.list_installed_voices()
        self.voice_menu.configure(values=voices)
        if self.voice_var.get() not in voices and voices:
            self.voice_var.set(voices[0])

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

        ttk.Label(frame, text="Expressiveness").pack(anchor="w", pady=(8, 0))
        ttk.Scale(frame, variable=self.expr_var, from_=0.3, to=1.0, orient="horizontal").pack(fill="x")

    def _save(self):
        if self._loading:
            return
        Config.save({
            "engine": self.engine_var.get(),
            "voice": self.voice_var.get(),
            "speed": round(self.speed_var.get(), 2),
            "expressiveness": round(self.expr_var.get(), 2),
        })

    # -- App tab ---------------------------------------------------------------------

    def _build_app_section(self, parent):
        location = ttk.Labelframe(parent, text="Save Location", padding=10, bootstyle="primary")
        location.pack(fill="x")
        ttk.Button(
            location, text="Change Save Folder", command=self.explorer.set_download_directory,
            bootstyle="secondary-outline",
        ).pack(fill="x", pady=(0, 6))
        ttk.Button(
            location, text="New Folder", command=self.explorer.create_subfolder, bootstyle="secondary-outline"
        ).pack(fill="x", pady=(0, 6))
        ttk.Button(
            location, text="Open in File Explorer", command=self._open_save_folder, bootstyle="secondary-outline"
        ).pack(fill="x")

        appearance = ttk.Labelframe(parent, text="Appearance", padding=10, bootstyle="primary")
        appearance.pack(fill="x", pady=(10, 0))
        ttk.Radiobutton(
            appearance, text="Light", variable=self.appearance_var, value="light", command=self._apply_appearance
        ).pack(anchor="w")
        ttk.Radiobutton(
            appearance, text="Dark", variable=self.appearance_var, value="dark", command=self._apply_appearance
        ).pack(anchor="w")

    def _open_save_folder(self):
        try:
            os.startfile(self.explorer.download_directory)
        except Exception as e:
            self.logger.add_event("error", "Failed to open folder", str(e))

    def _apply_appearance(self):
        self.on_theme_change(self.appearance_var.get() == "dark")
