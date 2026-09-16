import queue
import threading

import ttkbootstrap as ttk

import AppUpdater


class UpdateBanner(ttk.Frame):
    """A dismissible banner that appears when a newer release is found on GitHub.
    Hidden (not gridded) until an update is actually available."""

    def __init__(self, parent, logger, on_before_install_quit):
        super().__init__(parent, padding=(12, 8), bootstyle="info")
        self.logger = logger
        self.on_before_install_quit = on_before_install_quit
        self.update = None
        self._events = queue.Queue()

        self.message_var = ttk.StringVar(value="")
        self.message_label = ttk.Label(self, textvariable=self.message_var, bootstyle="@info")
        self.message_label.pack(side="left", fill="x", expand=True)

        self.update_btn = ttk.Button(self, text="⬇ Update Now", command=self._start_update, bootstyle="light")
        self.update_btn.pack(side="right", padx=(6, 0))
        ttk.Button(self, text="Dismiss", command=self.hide, bootstyle="light-outline").pack(side="right")

        self.after(200, self._poll)

    def check_in_background(self):
        def work():
            update = AppUpdater.check_for_update()
            if update is not None:
                self._events.put(("found", update))

        threading.Thread(target=work, daemon=True).start()

    def show(self):
        # place() rather than grid() -- this banner is occasional/transient, and floating
        # it over the top of the window avoids renumbering every other widget's grid row.
        self.place(relx=0.5, rely=0.05, anchor="n", relwidth=0.6)

    def hide(self):
        self.place_forget()

    def _start_update(self):
        if self.update is None:
            return
        self.update_btn.configure(state="disabled", text="Downloading...")

        def work():
            try:
                path = AppUpdater.download_installer(self.update)
                self._events.put(("downloaded", path))
            except Exception as e:
                self._events.put(("error", str(e)))

        threading.Thread(target=work, daemon=True).start()

    def _poll(self):
        try:
            while True:
                kind, payload = self._events.get_nowait()
                if kind == "found":
                    self.update = payload
                    self.message_var.set(f"Talebrew {payload.version} is available.")
                    self.show()
                    self.logger.add_event("info", f"Update available: {payload.version}")
                elif kind == "downloaded":
                    self.logger.add_event("info", "Update downloaded, launching installer")
                    try:
                        AppUpdater.launch_installer(payload)
                    except Exception as e:
                        self.logger.add_event("error", "Failed to launch installer", str(e))
                        self.update_btn.configure(state="normal", text="⬇ Update Now")
                        continue
                    self.message_var.set("Installer launched -- closing Talebrew so it can finish...")
                    self.after(1500, self.on_before_install_quit)
                elif kind == "error":
                    self.logger.add_event("error", "Update failed", payload)
                    self.update_btn.configure(state="normal", text="⬇ Update Now")
        except queue.Empty:
            pass
        if self.winfo_exists():
            self.after(200, self._poll)
