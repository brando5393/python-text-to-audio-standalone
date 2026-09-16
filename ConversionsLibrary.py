import json
import os
import tkinter as tk

_ICONS_DIR = os.path.join(os.path.dirname(__file__), "assets", "icons")


class ConversionsLibrary:
    """Populates a ttk.Treeview with the folder/file structure under the Conversions root."""

    def __init__(self, tree, root_dir):
        self.tree = tree
        self.root_dir = root_dir
        self._item_data = {}  # item id -> (path, "dir"/"file"); kept off the Treeview's own
        # "values" so that column stays free to show the voice label instead.

        self.tree["columns"] = ("voice",)
        self.tree["show"] = "tree headings"
        self.tree.heading("#0", text="Conversions", anchor="w")
        self.tree.heading("voice", text="Voice", anchor="w")
        self.tree.column("voice", width=130, anchor="w", stretch=False)

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
        self._item_data = {}
        os.makedirs(self.root_dir, exist_ok=True)
        self._insert_dir("", self.root_dir)

    def _insert_dir(self, parent_id, path):
        try:
            entries = sorted(os.scandir(path), key=lambda e: (e.is_file(), e.name.lower()))
        except OSError:
            return
        for entry in entries:
            if entry.is_dir():
                kwargs = {"image": self._folder_icon} if self._folder_icon is not None else {}
                node = self.tree.insert(parent_id, "end", text=entry.name, **kwargs)
                self._item_data[node] = (entry.path, "dir")
                self._insert_dir(node, entry.path)
            elif entry.name.endswith(".json"):
                continue  # Sidecar metadata for re-conversion, not a user-facing entry.
            elif not entry.name.endswith(".partial"):
                # A ".partial" file is a conversion still in progress (see Converter.py);
                # hide it so a mid-conversion refresh can't be mistaken for a finished file.
                kwargs = {"image": self._audio_icon} if self._audio_icon is not None else {}
                node = self.tree.insert(
                    parent_id, "end", text=entry.name, values=(self._voice_label_for(entry.path),), **kwargs
                )
                self._item_data[node] = (entry.path, "file")

    @staticmethod
    def _voice_label_for(audio_path):
        try:
            with open(audio_path + ".json", "r", encoding="utf-8") as f:
                return json.load(f).get("voice_label", "")
        except (OSError, json.JSONDecodeError):
            return ""  # No sidecar -- likely converted before this feature existed.

    def path_for(self, item_id):
        """Returns (path, kind) for a tree item, where kind is 'dir' or 'file'."""
        return self._item_data.get(item_id, (None, None))

    def text_for(self, item_id):
        """Returns the stored source text for a converted file, or None if unavailable
        (no sidecar, e.g. converted before this feature existed, or the sidecar was
        deleted/moved on its own)."""
        path, kind = self.path_for(item_id)
        if kind != "file":
            return None
        try:
            with open(path + ".json", "r", encoding="utf-8") as f:
                return json.load(f).get("text") or None
        except (OSError, json.JSONDecodeError):
            return None
