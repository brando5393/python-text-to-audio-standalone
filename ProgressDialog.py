import os
import tkinter as tk

import ttkbootstrap as ttk

import AppIcon


def _format_eta(seconds):
    if seconds is None or seconds < 0:
        return "estimating..."
    seconds = int(seconds)
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m remaining"
    if minutes:
        return f"{minutes}m {secs}s remaining"
    return f"{secs}s remaining"


class ProgressDialog(ttk.Toplevel):
    """Shows per-file and overall conversion progress with an estimated time remaining.

    Reads events from Converter.poll_events() -- main.py's poll loop feeds them in via
    `handle_events()` so there's only one poller for the whole app.
    """

    def __init__(self, parent, converter, total_files):
        super().__init__(parent)
        self.title("Converting Files")
        self.geometry("520x420")
        AppIcon.apply(self)
        self.converter = converter
        self.rows = {}  # file path -> row widgets
        self.total_chunks = None
        self.finished = False

        self._build_overall_section()
        self._build_file_list(total_files)
        self._build_footer()

    def _build_overall_section(self):
        frame = ttk.Frame(self, padding=12)
        frame.pack(fill="x")
        self.overall_label = ttk.Label(frame, text="Preparing...", font=("Segoe UI", 10, "bold"))
        self.overall_label.pack(anchor="w")
        self.overall_bar = ttk.Progressbar(frame, mode="determinate", maximum=100, bootstyle="success")
        self.overall_bar.pack(fill="x", pady=(6, 0))
        self.eta_label = ttk.Label(frame, text="", bootstyle="secondary")
        self.eta_label.pack(anchor="w", pady=(4, 0))

    def _build_file_list(self, total_files):
        outer = ttk.Frame(self, padding=(12, 0, 12, 0))
        outer.pack(fill="both", expand=True)

        canvas = tk.Canvas(outer, highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview, bootstyle="round")
        self.list_frame = ttk.Frame(canvas)
        self.list_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.list_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _build_footer(self):
        row = ttk.Frame(self, padding=12)
        row.pack(fill="x", side="bottom")
        self.cancel_btn = ttk.Button(row, text="Cancel Remaining", command=self._cancel, bootstyle="danger-outline")
        self.cancel_btn.pack(side="right")
        ttk.Button(row, text="Hide", command=self.destroy, bootstyle="secondary-outline").pack(
            side="right", padx=(0, 8)
        )

    def _cancel(self):
        self.converter.cancel()
        self.cancel_btn.configure(state="disabled", text="Cancelling...")

    def _row_for(self, file):
        if file not in self.rows:
            frame = ttk.Frame(self.list_frame, padding=(0, 6))
            frame.pack(fill="x")
            name_label = ttk.Label(frame, text=os.path.basename(file), width=30, anchor="w")
            name_label.pack(side="left")
            bar = ttk.Progressbar(frame, mode="determinate", maximum=100, length=160)
            bar.pack(side="left", padx=8)
            status_label = ttk.Label(frame, text="Pending", bootstyle="secondary")
            status_label.pack(side="left")
            self.rows[file] = {"bar": bar, "status": status_label}
        return self.rows[file]

    def handle_events(self, events):
        for event in events:
            kind = event[0]
            if kind == "plan":
                _, file_chunk_counts, total_chunks = event
                self.total_chunks = total_chunks
                for file, _count in file_chunk_counts:
                    self._row_for(file)
                self.overall_label.configure(text=f"Converting {len(file_chunk_counts)} file(s)...")
            elif kind == "progress":
                _, file, file_done, file_total, global_done, total_chunks, elapsed = event
                row = self._row_for(file)
                row["bar"]["value"] = 100 * file_done / file_total
                row["status"].configure(text=f"Converting... {file_done}/{file_total}")

                self.overall_bar["value"] = 100 * global_done / total_chunks if total_chunks else 0
                self.overall_label.configure(text=f"{global_done}/{total_chunks} sections converted")
                rate = elapsed / global_done if global_done else None
                remaining = rate * (total_chunks - global_done) if rate else None
                self.eta_label.configure(text=_format_eta(remaining))
            elif kind == "done":
                _, file, _output = event
                row = self._row_for(file)
                row["bar"]["value"] = 100
                row["status"].configure(text="Done", bootstyle="success")
            elif kind == "error":
                _, file, message = event
                row = self._row_for(file)
                row["status"].configure(text="Failed", bootstyle="danger")
            elif kind == "skipped":
                _, file, reason = event
                row = self._row_for(file)
                row["status"].configure(text=reason or "Skipped", bootstyle="secondary")
            elif kind == "all_done":
                self.finished = True
                self.overall_label.configure(text="Conversion complete")
                self.eta_label.configure(text="")
                self.cancel_btn.configure(state="disabled", text="Done")
