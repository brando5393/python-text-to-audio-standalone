"""Unit tests for JobStore, the JSON-backed persistence layer behind mcp_server.py's
get_conversion_status -- see JobStore.py's module docstring for why this is file-backed
rather than an in-memory dict."""

import json
import threading

from JobStore import JobStore, MAX_EVENTS_PER_JOB


def _store(tmp_path):
    return JobStore(str(tmp_path / "jobs.json"))


def test_create_then_get_returns_running_status(tmp_path):
    store = _store(tmp_path)
    store.create("job1", path="/x/book.txt", engine="piper", voice="en_US-amy-medium", output_dir="/x/out")

    job = store.get("job1")
    assert job["status"] == "running"
    assert job["path"] == "/x/book.txt"
    assert job["engine"] == "piper"
    assert job["output_files"] == []
    assert job["error"] is None


def test_get_unknown_job_returns_none(tmp_path):
    store = _store(tmp_path)
    assert store.get("does-not-exist") is None


def test_done_event_appends_output_file(tmp_path):
    store = _store(tmp_path)
    store.create("job1", path="/x/book.txt", engine="pyttsx3", voice=None, output_dir="/x/out")
    store.record_event("job1", ("done", "/x/book.txt", "/x/out/book.wav"))

    job = store.get("job1")
    assert job["output_files"] == ["/x/out/book.wav"]


def test_all_done_after_a_successful_file_marks_status_done(tmp_path):
    store = _store(tmp_path)
    store.create("job1", path="/x/book.txt", engine="pyttsx3", voice=None, output_dir="/x/out")
    store.record_event("job1", ("done", "/x/book.txt", "/x/out/book.wav"))
    store.record_event("job1", ("all_done", None, None))

    assert store.get("job1")["status"] == "done"


def test_error_event_marks_status_error_and_records_message(tmp_path):
    store = _store(tmp_path)
    store.create("job1", path="/x/book.txt", engine="pyttsx3", voice=None, output_dir="/x/out")
    store.record_event("job1", ("error", "/x/book.txt", "Something went wrong"))
    store.record_event("job1", ("all_done", None, None))

    job = store.get("job1")
    assert job["status"] == "error"
    assert job["error"] == "Something went wrong"


def test_all_done_with_no_output_and_no_error_marks_failed(tmp_path):
    """E.g. the one file in the batch was skipped as unsupported/cancelled -- no error
    event fired, but nothing was produced either."""
    store = _store(tmp_path)
    store.create("job1", path="/x/book.txt", engine="pyttsx3", voice=None, output_dir="/x/out")
    store.record_event("job1", ("skipped", "/x/book.txt", "Unsupported file type"))
    store.record_event("job1", ("all_done", None, None))

    job = store.get("job1")
    assert job["status"] == "failed"
    assert job["error"]


def test_progress_event_updates_progress_snapshot(tmp_path):
    store = _store(tmp_path)
    store.create("job1", path="/x/book.txt", engine="pyttsx3", voice=None, output_dir="/x/out")
    store.record_event("job1", ("progress", "/x/book.txt", 3, 10, 3, 10, 1.5))

    progress = store.get("job1")["progress"]
    assert progress == {
        "file": "/x/book.txt", "done_in_file": 3, "total_in_file": 10,
        "global_done": 3, "total_chunks": 10, "elapsed_seconds": 1.5,
    }


def test_events_are_capped_at_max_events_per_job(tmp_path):
    store = _store(tmp_path)
    store.create("job1", path="/x/book.txt", engine="pyttsx3", voice=None, output_dir="/x/out")
    for i in range(MAX_EVENTS_PER_JOB + 20):
        store.record_event("job1", ("progress", "/x/book.txt", i, 100, i, 100, float(i)))

    job = store.get("job1")
    assert len(job["events"]) == MAX_EVENTS_PER_JOB
    assert job["events"][-1]["data"][0] == "/x/book.txt"
    assert job["progress"]["done_in_file"] == MAX_EVENTS_PER_JOB + 19


def test_record_event_for_unknown_job_is_a_harmless_no_op(tmp_path):
    store = _store(tmp_path)
    store.record_event("ghost-job", ("done", "/x/book.txt", "/x/out/book.wav"))
    assert store.get("ghost-job") is None


def test_state_persists_across_separate_store_instances(tmp_path):
    """Simulates a fresh process: a brand new JobStore pointed at the same file must see
    a job created by a previous instance."""
    path = str(tmp_path / "jobs.json")
    JobStore(path).create("job1", path="/x/book.txt", engine="piper", voice="en_US-amy-medium", output_dir="/x/out")

    reopened = JobStore(path)
    job = reopened.get("job1")
    assert job is not None
    assert job["engine"] == "piper"

    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    assert "job1" in raw


def test_all_jobs_returns_every_created_job(tmp_path):
    store = _store(tmp_path)
    store.create("job1", path="/a.txt", engine="pyttsx3", voice=None, output_dir="/out")
    store.create("job2", path="/b.txt", engine="pyttsx3", voice=None, output_dir="/out")

    jobs = store.all_jobs()
    assert set(jobs.keys()) == {"job1", "job2"}


def test_concurrent_writers_do_not_lose_each_others_events(tmp_path):
    """Regression: JobStore's own threading.Lock only serializes calls made through one
    JobStore instance/process -- but mcp_server.py can be spawned as a separate OS
    process per MCP client session (see the module docstring), so two such processes,
    each with their own independent JobStore/Lock, can genuinely race on the same file.
    record_event's load-mutate-save is not atomic across them without a real
    cross-process lock: whichever save() lands last silently overwrites the other's
    update with no error. A fresh JobStore instance per thread here (rather than one
    shared instance) mirrors that -- no in-memory state or lock is shared between them,
    only the file on disk."""
    path = str(tmp_path / "jobs.json")
    JobStore(path).create("job1", path="/x/book.txt", engine="piper", voice=None, output_dir="/out")

    writer_count = 20

    def write_one(n):
        JobStore(path).record_event(
            "job1", ("progress", "/x/book.txt", n, writer_count, n, writer_count, float(n))
        )

    threads = [threading.Thread(target=write_one, args=(n,)) for n in range(writer_count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10.0)
        assert not t.is_alive()

    job = JobStore(path).get("job1")
    recorded = {e["data"][1] for e in job["events"] if e["kind"] == "progress"}
    assert recorded == set(range(writer_count))
