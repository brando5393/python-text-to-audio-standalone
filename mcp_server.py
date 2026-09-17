"""MCP (Model Context Protocol) server for Talebrew.

Exposes Talebrew's document-to-audio conversion pipeline as tools an AI agent (Claude
Desktop, Claude Code, or any other MCP client) can call directly, without a human
clicking through the GUI. Runs headless -- no Tk root, no display required -- by passing
`app_log_display=None` into Converter/LogManager (see LogManager.py).

Run with: poetry run python mcp_server.py
(requires the optional `mcp` dependency group: poetry install --with mcp)

See MCP_SETUP.md at the repo root for client configuration (Claude Desktop,
Claude Code) and example prompts.

Deliberately v1-scoped to four tools -- listing formats, starting a conversion,
checking on one, and listing the existing library. Playback control and other
GUI-only concerns are out of scope: this is about handing Talebrew a file to convert
and checking on it, not remote-controlling a running GUI.
"""

import os
import threading
import time
import uuid

from mcp.server.fastmcp import FastMCP

import Config
import ConversionsLibrary
import Converter
import FileManager
import TextExtraction
from JobStore import JobStore

mcp = FastMCP(
    "talebrew",
    instructions=(
        "Talebrew converts text/PDF/ebook files to audio using offline text-to-speech "
        "(Piper or the system voice). Use convert_file to start a conversion (it "
        "returns immediately with a job id -- conversion of a full book can take "
        "minutes), get_conversion_status to check on it, list_supported_formats to see "
        "which file types are accepted, and list_conversions to see what's already in "
        "the Conversions library."
    ),
)

_jobs = JobStore()

# Converter instances for jobs still running in *this* process, so their progress
# queues can keep being drained. A fresh process (a new client session, or the same
# session's server having been restarted) has none of these -- get_conversion_status
# always answers from the JobStore's on-disk record instead, which every _watch_job
# thread keeps current as events arrive. See JobStore's own docstring for why disk,
# not memory, is the source of truth here.
_active_converters = {}
_active_lock = threading.Lock()


@mcp.tool()
def list_supported_formats() -> dict:
    """List the file extensions Talebrew can convert to audio."""
    return {"supported_extensions": list(TextExtraction.SUPPORTED_EXTENSIONS)}


@mcp.tool()
def convert_file(path: str, engine: str | None = None, voice: str | None = None, output_dir: str | None = None) -> dict:
    """Start converting a document to audio in the background.

    Returns immediately with a job id -- a book-length file can take minutes to
    convert, so this does not block until it's done. Poll get_conversion_status(job_id)
    for progress and completion.

    Args:
        path: Path to the source file (must exist and be one of list_supported_formats()).
        engine: "piper" or "pyttsx3". Defaults to whatever Talebrew's Settings currently
            says (Config.load()) when omitted, matching how the GUI resolves a file with
            no per-file override.
        voice: A Piper voice id (e.g. "en_US-amy-medium"). Only meaningful when engine
            is "piper"; defaults to Settings' voice when omitted.
        output_dir: Directory to write the converted audio into. Defaults to Talebrew's
            Conversions library (FileManager.CONVERSIONS_ROOT) when omitted.
    """
    if not path or not os.path.isfile(path):
        return {"error": f"File not found: {path}"}
    if not path.lower().endswith(TextExtraction.SUPPORTED_EXTENSIONS):
        return {
            "error": (
                f"Unsupported file type: {path}. Supported extensions: "
                f"{', '.join(TextExtraction.SUPPORTED_EXTENSIONS)}"
            )
        }

    settings = Config.load()
    effective_engine = engine or settings["engine"]
    effective_voice = voice or settings["voice"]
    target_dir = output_dir or FileManager.CONVERSIONS_ROOT
    try:
        os.makedirs(target_dir, exist_ok=True)
    except OSError as e:
        return {"error": f"Could not create output directory '{target_dir}': {e}"}

    job_id = uuid.uuid4().hex
    _jobs.create(
        job_id,
        path=path,
        engine=effective_engine,
        voice=effective_voice,
        output_dir=target_dir,
    )

    # A per-file override dict, exactly like FileManager's file_list entries and what
    # Converter._convert_worker_inner already knows how to resolve against Settings
    # (None means "use whatever Settings says") -- reused rather than duplicating that
    # engine/voice fallback logic here.
    item = {"path": path, "engine": engine, "voice": voice}

    converter = Converter.Converter(app_log_display=None)
    with _active_lock:
        _active_converters[job_id] = converter

    converter.convert_to_audio([item], target_dir)
    watcher = threading.Thread(target=_watch_job, args=(job_id, converter), daemon=True)
    watcher.start()

    return {
        "job_id": job_id,
        "status": "running",
        "path": path,
        "engine": effective_engine,
        "voice": effective_voice,
        "output_dir": target_dir,
    }


def _watch_job(job_id, converter):
    """Drains `converter`'s event queue and persists progress to the JobStore as it
    happens. Runs on its own daemon thread per job so multiple convert_file calls in
    the same server process can proceed independently."""
    try:
        while True:
            events = converter.poll_events()
            for event in events:
                # Converter._events tuples aren't all the same shape -- "progress" alone
                # carries 7 fields (see Converter._convert_worker_inner/_convert_one) --
                # so the whole tuple is handed to JobStore rather than unpacked
                # positionally here (which would break the moment a differently-shaped
                # event, like "progress", showed up).
                _jobs.record_event(job_id, event)
            if any(event[0] == "all_done" for event in events):
                break
            time.sleep(0.2)
    finally:
        with _active_lock:
            _active_converters.pop(job_id, None)


@mcp.tool()
def get_conversion_status(job_id: str) -> dict:
    """Check on a conversion started with convert_file.

    Works even if this is a fresh server process from the one that started the job
    (status is persisted to disk, not just held in memory) -- an MCP client may not
    keep the same server process alive between calls.
    """
    job = _jobs.get(job_id)
    if job is None:
        return {"error": f"Unknown job id: {job_id}"}
    return job


@mcp.tool()
def list_conversions() -> dict:
    """List every converted audio file in Talebrew's Conversions library, with each
    file's page/chapter/voice metadata read from its sidecar JSON."""
    return {"conversions_root": FileManager.CONVERSIONS_ROOT, "files": ConversionsLibrary.list_conversions(FileManager.CONVERSIONS_ROOT)}


if __name__ == "__main__":
    mcp.run()
