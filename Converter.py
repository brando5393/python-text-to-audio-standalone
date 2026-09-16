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
        engine_label = f"Piper ({settings['voice']})" if use_piper else "system voice (pyttsx3)"
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
                clean_text = text.strip().replace("\n", " ")
                if not clean_text:
                    raise ValueError("No extractable text was found in this file")
                chunks = TextChunking.split_into_chunks(clean_text)
                base_name = os.path.splitext(os.path.basename(file))[0]
                output_file = os.path.join(output_dir, base_name + ".wav")
                plan.append({"file": file, "chunks": chunks, "output_file": output_file})
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
                    item["file"], item["chunks"], item["output_file"],
                    use_piper, settings, engine_label, global_done, total_chunks, start_time,
                )
            except Exception as e:
                error_message = f"Failed to convert file '{item['file']}' to audio: {str(e)}"
                self.logger.add_event("error", error_message)
                self._events.put(("error", item["file"], str(e)))

    def _convert_one(self, file, chunks, output_file, use_piper, settings, engine_label, global_done, total_chunks, start_time):
        total = len(chunks)
        tmp_dir = tempfile.mkdtemp(prefix="tta_")
        chunk_paths = []

        try:
            log_every = max(1, total // 10)
            for i, chunk in enumerate(chunks):
                if self._cancel_event.is_set():
                    self.logger.add_event("warn", f"Conversion cancelled: '{os.path.basename(file)}'")
                    self._events.put(("skipped", file, "Cancelled"))
                    return global_done

                try:
                    chunk_path = os.path.join(tmp_dir, f"chunk_{i:05d}.wav")
                    self._synthesize_chunk(chunk, chunk_path, use_piper, settings)
                    chunk_paths.append(chunk_path)
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

            if not chunk_paths:
                raise ValueError("No audio could be generated for this file")

            partial_path = output_file + ".partial"
            _concatenate_wavs(chunk_paths, partial_path)
            os.replace(partial_path, output_file)  # atomic: the library never sees a half-written file
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        self.logger.add_event("info", "File converted successfully", f"{engine_label} -> {output_file}")
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


def _concatenate_wavs(chunk_paths, output_path):
    with wave.open(chunk_paths[0], "rb") as first:
        params = first.getparams()

    with wave.open(output_path, "wb") as out:
        out.setparams(params)
        for path in chunk_paths:
            with wave.open(path, "rb") as chunk:
                out.writeframes(chunk.readframes(chunk.getnframes()))
