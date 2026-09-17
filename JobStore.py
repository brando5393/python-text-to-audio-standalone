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


class JobStore:
    """Thread-safe, file-backed store for MCP conversion job status."""

    def __init__(self, path=None):
        self._path = path or JOBS_PATH
        self._lock = threading.Lock()

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
        with self._lock:
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
        with self._lock:
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
