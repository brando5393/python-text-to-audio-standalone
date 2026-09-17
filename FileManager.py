import os
from tkinter import filedialog, messagebox, simpledialog

import LogManager as logger
import PiperEngine
import TextExtraction

CONVERSIONS_ROOT = os.path.join(os.path.expanduser("~"), "Documents", "TextToAudio", "Conversions")

_FILE_TYPES = [
    ("Supported documents", " ".join(f"*{ext}" for ext in TextExtraction.SUPPORTED_EXTENSIONS)),
    ("All files", "*.*"),
]


class FileManager:
    """This class handles all interactions with the user's file system."""

    def __init__(self, file_list_display, app_log_display, download_directory_label, on_directory_change=None):
        # Each entry is {"path": str, "engine": str|None, "voice": str|None} -- engine/voice
        # None means "use whatever Settings currently says" (the default for every newly
        # added file); a per-file override only exists once explicitly set for that item.
        self.file_list = []
        self.on_directory_change = on_directory_change

        os.makedirs(CONVERSIONS_ROOT, exist_ok=True)
        self.download_directory = CONVERSIONS_ROOT

        self.download_directory_label = download_directory_label  # Reference to the label
        self.file_list_display = file_list_display  # Reference to the listbox
        self.app_log_display = app_log_display
        self.logger = logger.LogManager(self.app_log_display)
        self._refresh_directory_label()

    def _refresh_directory_label(self):
        self.download_directory_label.config(text=f"Saving to: {self.download_directory}")
        if self.on_directory_change:
            self.on_directory_change()

    def add_files(self):
        """Add one or more files to the file list for conversion."""
        try:
            files_to_convert = filedialog.askopenfilenames(filetypes=_FILE_TYPES)
            if files_to_convert:
                for file in files_to_convert:
                    self.file_list.append({"path": file, "engine": None, "voice": None})
                    self.file_list_display.insert("end", self._display_label(self.file_list[-1]))
                    index = self.file_list_display.size() - 1
                    self.file_list_display.itemconfigure(index, foreground="blue")
            else:
                self.logger.add_event("warn", "No files selected for conversion")
        except Exception as e:
            self.logger.add_event("error", "Failed to add files for conversion", str(e))

    def remove_file(self):
        """Remove a single file from the file list."""
        try:
            selected_item = self.file_list_display.curselection()
            if selected_item:
                item_index = int(selected_item[0])
                self.file_list.pop(item_index)
                self.file_list_display.delete(item_index)
            else:
                self.logger.add_event("warn", "No file selected for removal")
        except Exception as e:
            self.logger.add_event("error", "Failed to remove file", str(e))

    @staticmethod
    def _display_label(item):
        filename = os.path.basename(item["path"])
        if item["engine"] == "piper":
            voice_label = PiperEngine.FRIENDLY_NAMES.get(item["voice"], item["voice"] or "default voice")
            return f"{filename}  [Piper: {voice_label}]"
        if item["engine"] == "pyttsx3":
            return f"{filename}  [System voice]"
        return filename

    def set_engine_for_item(self, index, engine, voice):
        """Sets an explicit engine/voice override for a single queued file. `engine`
        of None clears the override, reverting that file back to using Settings."""
        if not (0 <= index < len(self.file_list)):
            return
        self.file_list[index]["engine"] = engine
        self.file_list[index]["voice"] = voice
        self._refresh_display()

    def apply_engine_to_all(self, engine, voice):
        """Applies the same explicit engine/voice override to every queued file at once."""
        for item in self.file_list:
            item["engine"] = engine
            item["voice"] = voice
        self._refresh_display()

    def _refresh_display(self):
        selection = self.file_list_display.curselection()
        self.file_list_display.delete(0, "end")
        for index, item in enumerate(self.file_list):
            self.file_list_display.insert("end", self._display_label(item))
            self.file_list_display.itemconfigure(index, foreground="blue")
        for index in selection:
            self.file_list_display.selection_set(index)

    def clear_files(self):
        """Clear all files currently selected for conversion."""
        try:
            self.file_list.clear()
            self.file_list_display.delete(0, 'end')
        except Exception as e:
            self.logger.add_event("error", "Failed to clear files", str(e))

    def set_download_directory(self):
        """Specify a new directory where audio files will be placed after conversion."""
        try:
            new_download_directory = filedialog.askdirectory(initialdir=self.download_directory)
            if not new_download_directory:
                self.logger.add_event("warn", "No directory selected for download")
                return
            confirmed = messagebox.askyesno(
                "Change Save Folder", f"Save converted files to:\n\n{new_download_directory}\n\nfrom now on?"
            )
            if not confirmed:
                self.logger.add_event("warn", "Save folder change cancelled")
                return
            self.download_directory = new_download_directory
            self._refresh_directory_label()
        except Exception as e:
            self.logger.add_event("error", "Failed to set download directory", str(e))

    def reset_download_directory(self):
        """Resets the save destination back to the Conversions root."""
        self.download_directory = CONVERSIONS_ROOT
        self._refresh_directory_label()
        self.logger.add_event("info", "Save folder reset to default")

    def create_subfolder(self):
        """Creates a new named folder under the Conversions root (e.g. 'Books', 'Podcasts')
        and makes it the active save destination."""
        try:
            name = simpledialog.askstring("New Folder", "Folder name (created under Conversions):")
            if not name:
                self.logger.add_event("warn", "No folder name entered")
                return
            safe_name = "".join(c for c in name.strip() if c not in '<>:"/\\|?*')
            if not safe_name:
                self.logger.add_event("warn", "Folder name was empty after removing invalid characters")
                return
            new_dir = os.path.join(CONVERSIONS_ROOT, safe_name)

            # Stripping separators above blocks multi-segment traversal (e.g. "../../x"
            # collapses to a literal, harmless folder name once its slashes are gone), but
            # a name of exactly ".." survives that filter intact and resolves to the
            # parent of Conversions -- confirmed by testing, not just reasoning about it.
            # A real containment check catches that and any other resolution trick, rather
            # than trying to keep enumerating individual bad strings.
            root_real = os.path.realpath(CONVERSIONS_ROOT)
            new_dir_real = os.path.realpath(new_dir)
            if os.path.commonpath([root_real, new_dir_real]) != root_real:
                self.logger.add_event("warn", "Folder name would escape the Conversions folder", name)
                return

            os.makedirs(new_dir, exist_ok=True)
            self.download_directory = new_dir
            self._refresh_directory_label()
            self.logger.add_event("info", f"Created folder and set as save destination: {new_dir}")
        except Exception as e:
            self.logger.add_event("error", "Failed to create folder", str(e))
