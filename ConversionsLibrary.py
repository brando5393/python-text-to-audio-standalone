import json
import os
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

_ICONS_DIR = os.path.join(os.path.dirname(__file__), "assets", "icons")


def scan_conversions_dir(path):
    """Returns the immediate children of `path` (one directory level only) in the same
    order the Conversions Library tree displays them: folders before files, each group
    sorted alphabetically, with sidecar ".json" metadata, in-progress ".pcm" scratch
    audio, and still-converting ".partial" files filtered out. Each item is
    (os.DirEntry, "dir"|"file").

    Pulled out of ConversionsLibrary._insert_dir so the same folder-walk/filter logic
    can be reused by a caller with no Tk widget at all (see list_conversions() below,
    used by the MCP server) instead of being reimplemented from scratch.
    """
    try:
        entries = sorted(os.scandir(path), key=lambda e: (e.is_file(), e.name.lower()))
    except OSError:
        return []
    result = []
    for entry in entries:
        if entry.is_dir():
            result.append((entry, "dir"))
        elif entry.name.endswith(".json") or entry.name.endswith(".pcm") or entry.name.endswith(".partial"):
            continue
        else:
            result.append((entry, "file"))
    return result


def list_conversions(root_dir):
    """Recursively lists every converted audio file under root_dir with its sidecar
    metadata (pages/chapters/voice/engine), in the same order and with the same
    filtering as the Conversions Library tree -- for a headless caller (e.g. the MCP
    server's list_conversions tool) that needs the same data without building any Tk
    widgets. Reuses scan_conversions_dir() for the walk and
    ConversionsLibrary._sidecar_for() for metadata, rather than re-deriving either."""
    results = []
    for entry, kind in scan_conversions_dir(root_dir):
        if kind == "dir":
            results.extend(list_conversions(entry.path))
        else:
            sidecar = ConversionsLibrary._sidecar_for(entry.path)
            results.append({
                "path": entry.path,
                "name": entry.name,
                "pages": sidecar.get("pages"),
                "chapters": sidecar.get("chapters"),
                "voice": sidecar.get("voice_label"),
                "engine": sidecar.get("engine"),
            })
    return results


class ConversionsLibrary:
    """Populates a ttk.Treeview with the folder/file structure under the Conversions root."""

    def __init__(self, tree, root_dir):
        self.tree = tree
        self.root_dir = root_dir
        self._item_data = {}  # item id -> (path, "dir"/"file"); kept off the Treeview's own
        # "values" so that column stays free to show the voice label instead.

        self.tree["columns"] = ("pages", "chapters", "voice")
        self.tree["show"] = "tree headings"
        self.tree.heading("#0", text="Conversions", anchor="w")
        self.tree.heading("pages", text="Pages", anchor="w")
        self.tree.heading("chapters", text="Chapters", anchor="w")
        self.tree.heading("voice", text="Voice", anchor="w")
        self.tree.column("pages", width=70, anchor="w", stretch=False)
        self.tree.column("chapters", width=80, anchor="w", stretch=False)
        self.tree.column("voice", width=130, anchor="w", stretch=False)

        # A ttk Treeview's row height is a fixed pixel number the theme computes once
        # from the font's metrics at setup time -- it does *not* re-derive itself if the
        # font is resized afterward (confirmed directly: toggling "Larger text" grew the
        # named font but left every row exactly as tall as before, cramming bigger glyphs
        # into unchanged rows). Capturing the gap between the two here, while the font is
        # still at its un-scaled base size, lets sync_row_height() re-apply that same gap
        # on top of whatever size the font is later resized to.
        style = ttk.Style()
        base_rowheight = style.lookup("Treeview", "rowheight") or 20
        base_linespace = tkfont.nametofont("TkDefaultFont").metrics("linespace")
        self._row_padding = int(base_rowheight) - base_linespace

        # Tk PhotoImage objects must stay referenced or Tk garbage-collects them and the
        # Treeview rows silently lose their icons -- kept alive on self for the widget's lifetime.
        self._folder_icon = self._load_icon("folder.png")
        self._audio_icon = self._load_icon("audio.png")
        self.refresh()

    def sync_row_height(self):
        """Re-applies the Treeview's row-height padding on top of the current
        TkDefaultFont size. Call this any time that font's size changes (see
        main.py's apply_text_scale), or "Larger text" mode leaves rows too short
        for their own enlarged text."""
        style = ttk.Style()
        linespace = tkfont.nametofont("TkDefaultFont").metrics("linespace")
        style.configure("Treeview", rowheight=linespace + self._row_padding)

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
        for entry, kind in scan_conversions_dir(path):
            if kind == "dir":
                kwargs = {"image": self._folder_icon} if self._folder_icon is not None else {}
                node = self.tree.insert(parent_id, "end", text=entry.name, **kwargs)
                self._item_data[node] = (entry.path, "dir")
                self._insert_dir(node, entry.path)
            else:
                kwargs = {"image": self._audio_icon} if self._audio_icon is not None else {}
                sidecar = self._sidecar_for(entry.path)
                values = (
                    sidecar.get("pages") or "Unknown",
                    sidecar.get("chapters") or "Unknown",
                    sidecar.get("voice_label") or "",
                )
                node = self.tree.insert(parent_id, "end", text=entry.name, values=values, **kwargs)
                self._item_data[node] = (entry.path, "file")

    @staticmethod
    def _sidecar_for(audio_path):
        try:
            with open(audio_path + ".json", "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}  # No sidecar -- likely converted before this feature existed.

    def ordered_file_paths(self):
        """Returns every converted file's path, flattened in the tree's current
        display order (folders depth-first, files within each folder alphabetically --
        whatever _insert_dir actually produced), for queue/playlist "next"/"previous"
        playback. Folders themselves are skipped; only playable files are included."""
        paths = []

        def walk(parent_id):
            for item_id in self.tree.get_children(parent_id):
                path, kind = self._item_data.get(item_id, (None, None))
                if kind == "file":
                    paths.append(path)
                elif kind == "dir":
                    walk(item_id)

        walk("")
        return paths

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
        return self._sidecar_for(path).get("text") or None
