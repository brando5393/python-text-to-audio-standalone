import os
from tkinter import filedialog, simpledialog

import LogManager as logger
import TextExtraction

CONVERSIONS_ROOT = os.path.join(os.path.expanduser("~"), "Documents", "TextToAudio", "Conversions")

_FILE_TYPES = [
    ("Supported documents", " ".join(f"*{ext}" for ext in TextExtraction.SUPPORTED_EXTENSIONS)),
    ("All files", "*.*"),
]


class FileManager:
    """This class handles all interactions with the user's file system."""

    def __init__(self, file_list_display, app_log_display, download_directory_label, on_directory_change=None):
        self.file_list = []  # Contains all files selected for conversion
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
                    self.file_list.append(file)
                    filename = os.path.basename(file)
                    self.file_list_display.insert('end', filename)
                    index = self.file_list_display.size() - 1
                    self.file_list_display.itemconfigure(index, foreground='blue')
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
            if new_download_directory:
                self.download_directory = new_download_directory
                self._refresh_directory_label()
            else:
                self.logger.add_event("warn", "No directory selected for download")
        except Exception as e:
            self.logger.add_event("error", "Failed to set download directory", str(e))

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
            os.makedirs(new_dir, exist_ok=True)
            self.download_directory = new_dir
            self._refresh_directory_label()
            self.logger.add_event("info", f"Created folder and set as save destination: {new_dir}")
        except Exception as e:
            self.logger.add_event("error", "Failed to create folder", str(e))
