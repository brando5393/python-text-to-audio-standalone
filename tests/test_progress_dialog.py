"""Tests for ProgressDialog -- the window that shows per-file and overall progress while
a conversion is running. Previously had no test coverage at all: _format_eta's own
boundary math (hour/minute rollovers) and handle_events' event-driven state machine (which
drives the progress bars and status labels users actually watch during a long conversion)
were both completely unverified."""

import tkinter as tk

import ProgressDialog
from ProgressDialog import ProgressDialog as Dialog, _format_eta


class FakeConverter:
    def __init__(self):
        self.cancel_calls = 0

    def cancel(self):
        self.cancel_calls += 1


def test_format_eta_none_means_still_estimating():
    assert _format_eta(None) == "estimating..."


def test_format_eta_negative_means_still_estimating():
    assert _format_eta(-5) == "estimating..."


def test_format_eta_seconds_only():
    assert _format_eta(45) == "45s remaining"


def test_format_eta_minutes_and_seconds():
    assert _format_eta(125) == "2m 5s remaining"


def test_format_eta_exact_hour_shows_zero_minutes():
    assert _format_eta(3600) == "1h 0m remaining"


def test_format_eta_hours_and_minutes():
    assert _format_eta(3600 + 120) == "1h 2m remaining"


def test_plan_event_creates_a_row_per_file_and_updates_overall_label(tk_root):
    dialog = Dialog(tk_root, FakeConverter(), total_files=2)
    dialog.handle_events([("plan", [(r"C:\a.txt", 3), (r"C:\b.txt", 5)], 8)])

    assert dialog.total_chunks == 8
    assert set(dialog.rows.keys()) == {r"C:\a.txt", r"C:\b.txt"}
    assert dialog.overall_label.cget("text") == "Converting 2 file(s)..."
    dialog.destroy()


def test_progress_event_updates_file_and_overall_bars(tk_root):
    dialog = Dialog(tk_root, FakeConverter(), total_files=1)
    dialog.handle_events([("plan", [(r"C:\a.txt", 4)], 4)])
    dialog.handle_events([("progress", r"C:\a.txt", 2, 4, 2, 4, 10.0)])

    row = dialog.rows[r"C:\a.txt"]
    assert row["bar"]["value"] == 50.0
    assert row["status"].cget("text") == "Converting... 2/4"
    assert dialog.overall_bar["value"] == 50.0
    assert dialog.overall_label.cget("text") == "2/4 sections converted"
    dialog.destroy()


def test_progress_event_computes_eta_from_elapsed_and_rate(tk_root):
    """2 of 4 total sections done in 10s -> 5s/section -> 2 sections left -> 10s ETA."""
    dialog = Dialog(tk_root, FakeConverter(), total_files=1)
    dialog.handle_events([("plan", [(r"C:\a.txt", 4)], 4)])
    dialog.handle_events([("progress", r"C:\a.txt", 2, 4, 2, 4, 10.0)])
    assert dialog.eta_label.cget("text") == "10s remaining"
    dialog.destroy()


def test_progress_event_with_zero_total_chunks_does_not_divide_by_zero(tk_root):
    """Defensive: total_chunks could be reported as 0 (e.g. every file skipped as
    unsupported before any chunk existed) -- the overall bar math must not raise."""
    dialog = Dialog(tk_root, FakeConverter(), total_files=1)
    dialog.handle_events([("progress", r"C:\a.txt", 0, 1, 0, 0, 1.0)])
    assert dialog.overall_bar["value"] == 0
    dialog.destroy()


def test_done_event_marks_row_complete(tk_root):
    dialog = Dialog(tk_root, FakeConverter(), total_files=1)
    dialog.handle_events([("plan", [(r"C:\a.txt", 2)], 2)])
    dialog.handle_events([("done", r"C:\a.txt", r"C:\out\a.wav")])

    row = dialog.rows[r"C:\a.txt"]
    assert row["bar"]["value"] == 100
    assert row["status"].cget("text") == "Done"
    dialog.destroy()


def test_error_event_marks_row_failed(tk_root):
    dialog = Dialog(tk_root, FakeConverter(), total_files=1)
    dialog.handle_events([("plan", [(r"C:\a.txt", 2)], 2)])
    dialog.handle_events([("error", r"C:\a.txt", "boom")])

    assert dialog.rows[r"C:\a.txt"]["status"].cget("text") == "Failed"
    dialog.destroy()


def test_skipped_event_shows_the_given_reason(tk_root):
    dialog = Dialog(tk_root, FakeConverter(), total_files=1)
    dialog.handle_events([("plan", [(r"C:\a.txt", 2)], 2)])
    dialog.handle_events([("skipped", r"C:\a.txt", "Cancelled")])

    assert dialog.rows[r"C:\a.txt"]["status"].cget("text") == "Cancelled"
    dialog.destroy()


def test_skipped_event_falls_back_to_generic_label_when_reason_is_empty(tk_root):
    dialog = Dialog(tk_root, FakeConverter(), total_files=1)
    dialog.handle_events([("plan", [(r"C:\a.txt", 2)], 2)])
    dialog.handle_events([("skipped", r"C:\a.txt", None)])

    assert dialog.rows[r"C:\a.txt"]["status"].cget("text") == "Skipped"
    dialog.destroy()


def test_all_done_event_marks_finished_and_disables_cancel(tk_root):
    dialog = Dialog(tk_root, FakeConverter(), total_files=1)
    dialog.handle_events([("all_done", None, None)])

    assert dialog.finished is True
    assert dialog.overall_label.cget("text") == "Conversion complete"
    assert dialog.eta_label.cget("text") == ""
    assert str(dialog.cancel_btn.cget("state")) == "disabled"
    assert dialog.cancel_btn.cget("text") == "Done"
    dialog.destroy()


def test_cancel_button_invokes_converter_cancel_and_disables_itself(tk_root):
    converter = FakeConverter()
    dialog = Dialog(tk_root, converter, total_files=1)
    dialog._cancel()

    assert converter.cancel_calls == 1
    assert str(dialog.cancel_btn.cget("state")) == "disabled"
    assert dialog.cancel_btn.cget("text") == "Cancelling..."
    dialog.destroy()


def test_row_for_reuses_existing_row_instead_of_creating_a_duplicate(tk_root):
    """Regression: a file that shows up in more than one event (plan, then progress,
    then done) must update the SAME row, not silently create a second one for the
    same file, which would show duplicate/stale entries in the file list."""
    dialog = Dialog(tk_root, FakeConverter(), total_files=1)
    dialog.handle_events([("plan", [(r"C:\a.txt", 2)], 2)])
    first_row = dialog.rows[r"C:\a.txt"]
    dialog.handle_events([("done", r"C:\a.txt", r"C:\out\a.wav")])
    assert dialog.rows[r"C:\a.txt"] is first_row
    assert len(dialog.rows) == 1
    dialog.destroy()
