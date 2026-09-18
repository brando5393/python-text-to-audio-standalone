"""Persists MCP conversion job status to disk, in the same JSON-sidecar-file style as
PlaybackMemory.py and ConversionQueue.py.

Why disk and not just an in-memory dict: an MCP client talking to mcp_server.py over
stdio spawns the server as a subprocess and keeps that one process alive for the whole
client session, so in-memory state *would* survive across calls within a session. But
it does not survive the client restarting, the server being relaunched, or a different
process being used to check status later -- none of which are unusual for an agent
that kicks off a long book conversion and comes back to check on it much later, possibly
after the coordinating chat session itself has been restarted. Persisting to a small
JSON file, updated after every event, means get_conversion_status() gives a real answer
regardless of which process asks.
"""

import json
import os
import threading
import time

JOBS_DIR = os.path.join(os.path.expanduser("~"), ".texttoaudio")
JOBS_PATH = os.path.join(JOBS_DIR, "mcp_jobs.json")

# Keeps only the most recent N raw events per job in the persisted record -- a
# book-length conversion can emit thousands of "progress" events, and nothing reading
# get_conversion_status() needs the full history, just where things stand now and
# recent context.
MAX_EVENTS_PER_JOB = 50

# How long a writer waits to acquire the cross-process lock before deciding it must be
# stale (see _CrossProcessLock) -- generous relative to how fast a load-mutate-save
# cycle actually takes, since it's only ever hit under real contention.
_LOCK_TIMEOUT_SECONDS = 5.0
_LOCK_POLL_SECONDS = 0.02


class _CrossProcessLock:
    """A simple mutex usable across separate OS processes, via the atomicity of
    os.O_CREAT | os.O_EXCL (fails if the file already exists -- the same primitive
    Converter.py's own resume-checkpoint writes rely on for atomic replace via
    os.replace, just applied here to acquisition instead of the final write).

    threading.Lock only serializes calls within one process; mcp_server.py can be
    spawned as a separate process per MCP client session (see this module's docstring),
    so two such processes each doing JobStore's load-mutate-save cycle on the same file
    need a lock neither process's in-memory state can provide -- without one, whichever
    process's save() runs last silently overwrites the other's update to a *different*
    job, or to the same job, with no error and no trace of what was lost.
    """

    def __init__(self, lock_path):
        self._lock_path = lock_path

    def __enter__(self):
        deadline = time.time() + _LOCK_TIMEOUT_SECONDS
        while True:
            try:
                fd = os.open(self._lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(fd)
                return self
            except FileExistsError:
                if time.time() >= deadline:
                    # A process that crashed while holding the lock leaves it stale
                    # forever -- break it rather than let every future call hang. A
                    # false break during genuine (if unusually slow) contention just
                    # costs the loser a retry on the next call, versus every job status
                    # check silently hanging forever without this.
                    try:
                        os.remove(self._lock_path)
                    except OSError:
                        pass
                    continue
                time.sleep(_LOCK_POLL_SECONDS)

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            os.remove(self._lock_path)
        except OSError:
            pass


class JobStore:
    """Thread- and process-safe, file-backed store for MCP conversion job status."""

    def __init__(self, path=None):
        self._path = path or JOBS_PATH
        self._lock = threading.Lock()
        self._file_lock = _CrossProcessLock(self._path + ".lock")

    def _load(self):
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}

    def _save(self, jobs):
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        tmp_path = self._path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(jobs, f, indent=2)
        os.replace(tmp_path, self._path)

    def create(self, job_id, path, engine, voice, output_dir):
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with self._lock, self._file_lock:
            jobs = self._load()
            jobs[job_id] = {
                "job_id": job_id,
                "status": "running",
                "path": path,
                "engine": engine,
                "voice": voice,
                "output_dir": output_dir,
                "output_files": [],
                "error": None,
                "events": [],
                "created_at": time.time(),
                "updated_at": time.time(),
            }
            self._save(jobs)

    def record_event(self, job_id, event):
        """Folds one raw Converter.poll_events() tuple into the job's persisted record.

        Converter._events tuples aren't all the same shape (see Converter.py):
            ("plan", [(file, chunk_count), ...], total_chunks)
            ("progress", file, done_in_file, total_in_file, global_done, total_chunks, elapsed)
            ("skipped", file, reason)
            ("done", file, output_file)
            ("error", file, error_message)
            ("all_done", None, None)
        so `event` is taken and stored whole rather than assumed to always be
        (kind, file, extra).
        """
        kind = event[0]
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with self._lock, self._file_lock:
            jobs = self._load()
            job = jobs.get(job_id)
            if job is None:
                return  # Unknown job (e.g. store file was cleared externally) -- nothing to update.

            job["events"].append({"kind": kind, "data": list(event[1:]), "time": time.time()})
            job["events"] = job["events"][-MAX_EVENTS_PER_JOB:]

            if kind == "done":
                _file, output_file = event[1], event[2]
                job["output_files"].append(output_file)
            elif kind == "error":
                _file, error_message = event[1], event[2]
                job["error"] = error_message
                job["status"] = "error"
            elif kind == "progress":
                _file, done_in_file, total_in_file, global_done, total_chunks, elapsed = event[1:]
                job["progress"] = {
                    "file": _file, "done_in_file": done_in_file, "total_in_file": total_in_file,
                    "global_done": global_done, "total_chunks": total_chunks, "elapsed_seconds": elapsed,
                }
            elif kind == "all_done":
                if job["status"] != "error":
                    job["status"] = "done" if job["output_files"] else "failed"
                if job["status"] == "failed" and not job["error"]:
                    job["error"] = "Conversion finished with no output file (see events)"

            job["updated_at"] = time.time()
            jobs[job_id] = job
            self._save(jobs)

    def get(self, job_id):
        with self._lock:
            return self._load().get(job_id)

    def all_jobs(self):
        with self._lock:
            return self._load()
