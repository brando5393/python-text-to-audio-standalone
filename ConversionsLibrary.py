import os


class ConversionsLibrary:
    """Populates a ttk.Treeview with the folder/file structure under the Conversions root."""

    def __init__(self, tree, root_dir):
        self.tree = tree
        self.root_dir = root_dir
        self.tree.heading("#0", text="Conversions", anchor="w")
        self.refresh()

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
                node = self.tree.insert(parent_id, "end", text=f"[Folder] {entry.name}", values=(entry.path, "dir"))
                self._insert_dir(node, entry.path)
            else:
                node = self.tree.insert(parent_id, "end", text=entry.name, values=(entry.path, "file"))

    def path_for(self, item_id):
        """Returns (path, kind) for a tree item, where kind is 'dir' or 'file'."""
        values = self.tree.item(item_id, "values")
        return (values[0], values[1]) if values else (None, None)
