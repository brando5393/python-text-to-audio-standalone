import hashlib
import json
import os
import queue
import shutil
import tempfile
import threading
import time
import wave

import pyttsx3

import Config
import LogManager as logger
import PiperEngine
import TextChunking
import TextExtraction
import TextSanitization

# In-process pyttsx3 calls can't be killed like a subprocess if they hang; instead a
# chunk is run on a helper thread and abandoned (left to finish or hang on its own,
# harmless since it's a daemon thread) if it doesn't return within this long, and the
# engine is re-initialized for the next chunk in case the old one is left wedged.
PYTTSX3_CHUNK_TIMEOUT_SECONDS = 60


class Converter:
    """Converts documents to audio.

    Conversion runs on a background worker thread so the UI stays responsive. Text is
    split into chunks (see TextChunking) rather than synthesized in one call: a
    book-length text run through Piper or SAPI in a single call can take a very long
    time with zero feedback and no way to tell "still working" from "stuck" -- chunking
    keeps each engine call short, lets progress (and an ETA) be reported, and means one
    slow or stuck chunk doesn't lose the whole book or hang the app indefinitely.
    Results are delivered back to the caller via a thread-safe queue that the UI polls
    with Tk's `after()`.
    """

    def __init__(self, app_log_display):
        self.logger = logger.LogManager(app_log_display)
        self._events = queue.Queue()
        self._cancel_event = threading.Event()
        self._pyttsx3_speaker = None

    def convert_to_audio(self, files, output_dir):
        """Queues `files` for background conversion into `output_dir`. Non-blocking."""
        self._cancel_event.clear()
        worker = threading.Thread(target=self._convert_worker, args=(list(files), output_dir), daemon=True)
        worker.start()

    def cancel(self):
        """Requests cancellation. Takes effect after the chunk currently in progress."""
        self._cancel_event.set()

    def poll_events(self):
        """Drains and returns any conversion results produced since the last poll."""
        events = []
        while True:
            try:
                events.append(self._events.get_nowait())
            except queue.Empty:
                break
        return events

    def _convert_worker(self, files, output_dir):
        try:
            self._convert_worker_inner(files, output_dir)
        except Exception as e:
            # A safety net: without this, an unexpected exception here (e.g. the TTS
            # engine failing to initialize) would kill the daemon thread silently and
            # leave the progress dialog waiting forever with no explanation.
            self.logger.add_event("error", "Conversion stopped unexpectedly", str(e))
            self._events.put(("error", "(batch)", str(e)))
        finally:
            self._events.put(("all_done", None, None))

    def _convert_worker_inner(self, files, output_dir):
        settings = Config.load()
        engine_installed = PiperEngine.is_engine_installed()
        voice_installed = PiperEngine.is_voice_installed(settings["voice"])
        use_piper = settings["engine"] == "piper" and engine_installed and voice_installed

        if settings["engine"] == "piper" and not use_piper:
            # Piper was the user's actual choice; falling back to the system voice
            # without saying why would look like the voice selection is being ignored.
            if not engine_installed:
                reason = "the Piper engine isn't installed yet"
            elif not voice_installed:
                reason = f"the voice '{settings['voice']}' isn't downloaded yet"
            else:
                reason = "Piper isn't fully set up yet"
            self.logger.add_event(
                "warn", f"Piper is selected but {reason}, using the system voice instead",
                "Install the engine and download the voice from Settings > Voice",
            )

        if not use_piper:
            self._pyttsx3_speaker = pyttsx3.init()
        os.makedirs(output_dir, exist_ok=True)

        # Build the full plan up front (extract + chunk every file) so the progress UI
        # knows the total amount of work, and can therefore show a real ETA, before any
        # synthesis starts.
        plan = []
        for file in files:
            if not file.lower().endswith(TextExtraction.SUPPORTED_EXTENSIONS):
                self.logger.add_event("alert", "The specified file is not supported and could not be converted.", file)
                self._events.put(("skipped", file, "Unsupported file type"))
                continue
            try:
                text = TextExtraction.extract_text(file)
                text = TextSanitization.sanitize(text)
                clean_text = text.strip().replace("\n", " ")
                if not clean_text:
                    raise ValueError("No extractable text was found in this file")
                chunks = TextChunking.split_into_chunks(clean_text)
                base_name = os.path.splitext(os.path.basename(file))[0]
                output_file = os.path.join(output_dir, base_name + ".wav")
                plan.append({"file": file, "chunks": chunks, "output_file": output_file, "text": clean_text})
            except Exception as e:
                error_message = f"Failed to read '{file}': {str(e)}"
                self.logger.add_event("error", error_message)
                self._events.put(("error", file, str(e)))

        total_chunks = sum(len(item["chunks"]) for item in plan)
        self._events.put(("plan", [(item["file"], len(item["chunks"])) for item in plan], total_chunks))

        start_time = time.time()
        global_done = 0

        for item in plan:
            if self._cancel_event.is_set():
                self._events.put(("skipped", item["file"], "Cancelled"))
                continue
            try:
                global_done = self._convert_one(
                    item["file"], item["chunks"], item["output_file"], item["text"],
                    use_piper, settings, global_done, total_chunks, start_time,
                )
            except Exception as e:
                error_message = f"Failed to convert file '{item['file']}' to audio: {str(e)}"
                self.logger.add_event("error", error_message)
                self._events.put(("error", item["file"], str(e)))

    def _convert_one(self, file, chunks, output_file, text, use_piper, settings, global_done, total_chunks, start_time):
        # Each chunk's audio is appended to a scratch PCM file as soon as it's synthesized,
        # with a small sidecar tracking how many chunks are already in it. If the app closes
        # (or crashes) mid-file, that scratch file and sidecar survive -- reconverting the
        # same source text later picks up from the first unfinished chunk instead of
        # resynthesizing everything, which otherwise wasted real synthesis time (Piper on
        # this machine runs under x64 emulation and isn't fast) every time a long book got
        # interrupted partway through.
        total = len(chunks)
        progress_path = output_file + ".progress.json"
        pcm_path = output_file + ".partial.pcm"
        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

        resume = _load_resume_state(progress_path, pcm_path, text_hash, total)
        if resume:
            start_index = resume["completed_chunks"]
            resume_use_piper = resume["engine"] == "piper"
            resume_settings = {
                "voice": resume["voice_id"], "speed": settings["speed"], "expressiveness": settings["expressiveness"],
            }
            wav_info = {"nchannels": resume["nchannels"], "sampwidth": resume["sampwidth"], "framerate": resume["framerate"]}
            self.logger.add_event(
                "info", f"Resuming '{os.path.basename(file)}' from section {start_index + 1}/{total}",
                "Picking up an interrupted conversion instead of starting over",
            )
        else:
            start_index = 0
            resume_use_piper = use_piper
            resume_settings = settings
            wav_info = {}
            for stale_path in (progress_path, pcm_path):
                try:
                    os.remove(stale_path)
                except OSError:
                    pass

        if start_index:
            global_done += start_index
            self._events.put(("progress", file, start_index, total, global_done, total_chunks, time.time() - start_time))

        engine_label = f"Piper ({resume_settings['voice']})" if resume_use_piper else "system voice (pyttsx3)"
        tmp_dir = tempfile.mkdtemp(prefix="tta_")
        chunk_scratch = os.path.join(tmp_dir, "chunk.wav")

        try:
            log_every = max(1, total // 10)
            for i in range(start_index, total):
                if self._cancel_event.is_set():
                    self.logger.add_event("warn", f"Conversion cancelled: '{os.path.basename(file)}'")
                    self._events.put(("skipped", file, "Cancelled"))
                    return global_done  # progress/pcm scratch files are left in place on purpose, for next time

                try:
                    self._synthesize_chunk(chunks[i], chunk_scratch, resume_use_piper, resume_settings)
                    with wave.open(chunk_scratch, "rb") as chunk_wav:
                        if not wav_info:
                            wav_info = {
                                "nchannels": chunk_wav.getnchannels(), "sampwidth": chunk_wav.getsampwidth(),
                                "framerate": chunk_wav.getframerate(),
                            }
                        frames = chunk_wav.readframes(chunk_wav.getnframes())
                    with open(pcm_path, "ab") as pcm_file:
                        pcm_file.write(frames)
                except Exception as chunk_error:
                    # Skip a bad or timed-out chunk rather than losing every chunk already
                    # synthesized, or hanging the whole app on one stuck section.
                    self.logger.add_event(
                        "warn", f"Skipped one section of '{os.path.basename(file)}'", str(chunk_error)
                    )

                global_done += 1
                elapsed = time.time() - start_time
                self._events.put(("progress", file, i + 1, total, global_done, total_chunks, elapsed))
                if total > 1 and ((i + 1) % log_every == 0 or i + 1 == total):
                    self.logger.add_event("info", f"Converting '{os.path.basename(file)}': {i + 1}/{total} sections")
                _save_resume_state(progress_path, i + 1, total, text_hash, resume_use_piper, resume_settings.get("voice"), wav_info)

            if not os.path.isfile(pcm_path) or os.path.getsize(pcm_path) == 0:
                raise ValueError("No audio could be generated for this file")

            partial_path = output_file + ".partial"
            with open(pcm_path, "rb") as pcm_file, wave.open(partial_path, "wb") as out:
                out.setnchannels(wav_info["nchannels"])
                out.setsampwidth(wav_info["sampwidth"])
                out.setframerate(wav_info["framerate"])
                out.writeframes(pcm_file.read())
            os.replace(partial_path, output_file)  # atomic: the library never sees a half-written file
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        for scratch_path in (progress_path, pcm_path):
            try:
                os.remove(scratch_path)
            except OSError:
                pass

        self.logger.add_event("info", "File converted successfully", f"{engine_label} -> {output_file}")
        _write_sidecar(output_file, text, resume_use_piper, resume_settings)
        self._events.put(("done", file, output_file))
        return global_done

    def _synthesize_chunk(self, chunk_text, chunk_path, use_piper, settings):
        if use_piper:
            # length_scale is inverse of speed: 2x speed -> half the length_scale.
            # PiperEngine.synthesize enforces its own subprocess timeout internally.
            PiperEngine.synthesize(
                chunk_text,
                settings["voice"],
                chunk_path,
                length_scale=1.0 / max(settings["speed"], 0.1),
                noise_scale=settings["expressiveness"],
            )
            return

        if self._pyttsx3_speaker is None:
            # Normally initialized once per batch in _convert_worker_inner, but a resumed
            # file can call for the system voice even when the rest of the batch is using
            # Piper (it resumes with whatever voice it was originally started with).
            self._pyttsx3_speaker = pyttsx3.init()

        done = threading.Event()
        error_box = []

        def run():
            try:
                self._pyttsx3_speaker.save_to_file(chunk_text, chunk_path)
                self._pyttsx3_speaker.runAndWait()
            except Exception as e:
                error_box.append(e)
            finally:
                done.set()

        threading.Thread(target=run, daemon=True).start()
        if not done.wait(timeout=PYTTSX3_CHUNK_TIMEOUT_SECONDS):
            # The engine may be wedged; replace it so later chunks aren't stuck behind it too.
            self._pyttsx3_speaker = pyttsx3.init()
            raise TimeoutError(f"System voice did not finish this section within {PYTTSX3_CHUNK_TIMEOUT_SECONDS}s")
        if error_box:
            raise error_box[0]


def _write_sidecar(output_file, text, use_piper, settings):
    """Stores the voice used and the exact text synthesized alongside the audio file.

    This is what lets the Conversions Library show which voice made a file, and lets a
    file be re-synthesized in a different voice later without needing the original
    document again -- otherwise a converted file is permanently locked to whatever voice
    was selected the moment it was made, defeating the point of being able to change voices.
    """
    voice_label = PiperEngine.FRIENDLY_NAMES.get(settings["voice"], settings["voice"]) if use_piper else "System voice"
    sidecar = {
        "engine": "piper" if use_piper else "pyttsx3",
        "voice_id": settings["voice"] if use_piper else None,
        "voice_label": voice_label,
        "text": text,
    }
    try:
        with open(output_file + ".json", "w", encoding="utf-8") as f:
            json.dump(sidecar, f)
    except OSError:
        pass  # Metadata is a display/re-convert convenience, not required for the audio itself.


def _load_resume_state(progress_path, pcm_path, text_hash, total_chunks):
    """Returns the saved resume state for this exact output file, or None if there isn't
    a usable one -- either no interrupted attempt exists, or its text no longer matches
    (the source document changed since the crash, so continuing would risk stitching
    audio from two different texts together)."""
    if not os.path.isfile(pcm_path):
        return None
    try:
        with open(progress_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    if data.get("text_hash") != text_hash or data.get("total_chunks") != total_chunks:
        return None
    return data


def _save_resume_state(progress_path, completed_chunks, total_chunks, text_hash, use_piper, voice_id, wav_info):
    state = {
        "completed_chunks": completed_chunks,
        "total_chunks": total_chunks,
        "text_hash": text_hash,
        "engine": "piper" if use_piper else "pyttsx3",
        "voice_id": voice_id,
        **wav_info,
    }
    tmp_path = progress_path + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(state, f)
        os.replace(tmp_path, progress_path)
    except OSError:
        pass  # Losing a checkpoint just means a resume restarts this file from scratch -- not fatal.
