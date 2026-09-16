import os
import tkinter as tk

_ICONS_DIR = os.path.join(os.path.dirname(__file__), "assets", "icons")


class ConversionsLibrary:
    """Populates a ttk.Treeview with the folder/file structure under the Conversions root."""

    def __init__(self, tree, root_dir):
        self.tree = tree
        self.root_dir = root_dir
        self.tree.heading("#0", text="Conversions", anchor="w")
        # Tk PhotoImage objects must stay referenced or Tk garbage-collects them and the
        # Treeview rows silently lose their icons -- kept alive on self for the widget's lifetime.
        self._folder_icon = self._load_icon("folder.png")
        self._audio_icon = self._load_icon("audio.png")
        self.refresh()

    @staticmethod
    def _load_icon(filename):
        try:
            return tk.PhotoImage(file=os.path.join(_ICONS_DIR, filename))
        except tk.TclError:
            return None

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        os.makedirs(self.root_dir, exist_ok=True)
        self._insert_dir("", self.root_dir)

    def _insert_dir(self, parent_id, path):
        try:
            entries = sorted(os.scandir(path), key=lambda e: (e.is_file(), e.name.lower()))
        except OSError:
            return
        for entry in entries:
            if entry.is_dir():
                node = self.tree.insert(
                    parent_id, "end", text=entry.name, image=self._folder_icon, values=(entry.path, "dir")
                )
                self._insert_dir(node, entry.path)
            elif not entry.name.endswith(".partial"):
                # A ".partial" file is a conversion still in progress (see Converter.py);
                # hide it so a mid-conversion refresh can't be mistaken for a finished file.
                self.tree.insert(
                    parent_id, "end", text=entry.name, image=self._audio_icon, values=(entry.path, "file")
                )

    def path_for(self, item_id):
        """Returns (path, kind) for a tree item, where kind is 'dir' or 'file'."""
        values = self.tree.item(item_id, "values")
        return (values[0], values[1]) if values else (None, None)
