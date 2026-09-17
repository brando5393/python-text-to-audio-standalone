"""Tests for ErrorReporter. subprocess.run is always faked here -- these tests must
never invoke the real `gh` CLI, which would file a live issue on the real repo."""

import subprocess
import time

import ErrorReporter

# conftest.py's autouse no_real_error_reports fixture replaces ErrorReporter.report with
# a no-op for every test, to keep the rest of the suite from ever calling the real `gh`
# CLI. These tests are specifically testing that function, so they restore the real one
# (captured here, before any fixture has a chance to patch it) and fake subprocess.run
# instead -- the layer that actually matters to keep isolated from the real `gh` CLI.
_REAL_REPORT = ErrorReporter.report


class _FakeCompletedProcess:
    def __init__(self, returncode=0):
        self.returncode = returncode
        self.stdout = ""
        self.stderr = ""


def _wait_for(predicate, timeout=2):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(ErrorReporter, "report", _REAL_REPORT)
    monkeypatch.setattr(ErrorReporter, "APP_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(ErrorReporter, "REPORTED_PATH", str(tmp_path / "reported_errors.json"))


def test_report_calls_gh_issue_create_with_repo_and_label(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return _FakeCompletedProcess(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    ErrorReporter.report("Failed to convert file 'book.pdf'", "ValueError: No audio could be generated")
    assert _wait_for(lambda: len(calls) == 1)

    cmd = calls[0]
    assert cmd[:3] == ["gh", "issue", "create"]
    assert "--repo" in cmd and ErrorReporter.REPO in cmd
    assert "--label" in cmd and ErrorReporter.LABEL in cmd
    title = cmd[cmd.index("--title") + 1]
    assert "Failed to convert file" in title
    body = cmd[cmd.index("--body") + 1]
    assert "Failed to convert file 'book.pdf'" in body
    assert "No audio could be generated" in body


def test_duplicate_errors_only_report_once(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return _FakeCompletedProcess(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    import hashlib

    signature = hashlib.sha256(b"same-technical-detail").hexdigest()

    ErrorReporter.report("Something broke", "same-technical-detail")
    # Waits for the dedup record itself, not just the subprocess call -- otherwise the
    # second report() below can race ahead of the first one's own dedup write finishing,
    # making this test flaky rather than the code it's testing.
    assert _wait_for(lambda: ErrorReporter._already_reported(signature))

    ErrorReporter.report("Something broke again, different message", "same-technical-detail")
    time.sleep(0.2)  # give a wrongly-firing second report a chance to show up
    assert len(calls) == 1, "the same underlying error should only ever open one issue"


def test_different_errors_each_report(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return _FakeCompletedProcess(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    ErrorReporter.report("First problem", "detail A")
    assert _wait_for(lambda: len(calls) == 1)
    ErrorReporter.report("Second problem", "detail B")
    assert _wait_for(lambda: len(calls) == 2)


def test_failed_gh_call_is_not_marked_reported(tmp_path, monkeypatch):
    """If `gh` itself fails (not installed, not authenticated, offline), the error
    shouldn't be marked as reported -- otherwise a real future fix to `gh` auth would
    never get a chance to actually report it."""
    _isolate(tmp_path, monkeypatch)

    def fake_run(cmd, **kwargs):
        return _FakeCompletedProcess(returncode=1)

    monkeypatch.setattr(subprocess, "run", fake_run)

    ErrorReporter.report("Something broke", "detail")
    time.sleep(0.2)
    assert not ErrorReporter._already_reported(
        __import__("hashlib").sha256(b"detail").hexdigest()
    )


def test_report_never_raises_when_gh_is_missing(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)

    def fake_run(cmd, **kwargs):
        raise FileNotFoundError("gh not found")

    monkeypatch.setattr(subprocess, "run", fake_run)

    ErrorReporter.report("Something broke", "detail")  # must not raise
    time.sleep(0.2)


def test_title_is_truncated():
    long_message = "x" * 300
    title = ErrorReporter._truncate(f"Error: {long_message}", ErrorReporter.TITLE_MAX_CHARS)
    assert len(title) <= ErrorReporter.TITLE_MAX_CHARS
    assert title.endswith("…")
