import os
import queue
import shutil
import tempfile
import threading
import wave

import pyttsx3

import Config
import LogManager as logger
import PiperEngine
import TextChunking
import TextExtraction


class Converter:
    """Converts documents to audio.

    Conversion runs on a background worker thread so the UI stays responsive. A file's
    text is split into chunks (see TextChunking) rather than synthesized in one call:
    a book-length text run through Piper or SAPI in a single call can take a very long
    time with zero feedback and no way to tell "still working" from "stuck" -- chunking
    keeps each engine call short, lets progress be reported, and means one bad chunk
    doesn't lose the whole book. Results are delivered back to the caller via a
    thread-safe queue that the UI polls with Tk's `after()`.
    """

    def __init__(self, app_log_display):
        self.logger = logger.LogManager(app_log_display)
        self._events = queue.Queue()

    def convert_to_audio(self, files, output_dir):
        """Queues `files` for background conversion into `output_dir`. Non-blocking."""
        worker = threading.Thread(target=self._convert_worker, args=(list(files), output_dir), daemon=True)
        worker.start()

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
        settings = Config.load()
        use_piper = (
            settings["engine"] == "piper"
            and PiperEngine.is_engine_installed()
            and PiperEngine.is_voice_installed(settings["voice"])
        )
        pyttsx3_speaker = None if use_piper else pyttsx3.init()
        engine_label = f"Piper ({settings['voice']})" if use_piper else "system voice (pyttsx3)"
        os.makedirs(output_dir, exist_ok=True)

        for file in files:
            try:
                if not file.lower().endswith(TextExtraction.SUPPORTED_EXTENSIONS):
                    self.logger.add_event("alert", "The specified file is not supported and could not be converted.", file)
                    self._events.put(("skipped", file, None))
                    continue

                text = TextExtraction.extract_text(file)
                clean_text = text.strip().replace("\n", " ")
                if not clean_text:
                    raise ValueError("No extractable text was found in this file")

                base_name = os.path.splitext(os.path.basename(file))[0]
                output_file = os.path.join(output_dir, base_name + ".wav")

                self._convert_one(file, clean_text, output_file, use_piper, pyttsx3_speaker, settings, engine_label)
            except Exception as e:
                error_message = f"Failed to convert file '{file}' to audio: {str(e)}"
                self.logger.add_event("error", error_message)
                self._events.put(("error", file, str(e)))

    def _convert_one(self, file, clean_text, output_file, use_piper, pyttsx3_speaker, settings, engine_label):
        chunks = TextChunking.split_into_chunks(clean_text)
        total = len(chunks)
        tmp_dir = tempfile.mkdtemp(prefix="tta_")
        chunk_paths = []

        try:
            log_every = max(1, total // 10)
            for i, chunk in enumerate(chunks):
                chunk_path = os.path.join(tmp_dir, f"chunk_{i:05d}.wav")
                try:
                    self._synthesize_chunk(chunk, chunk_path, use_piper, pyttsx3_speaker, settings)
                    chunk_paths.append(chunk_path)
                except Exception as chunk_error:
                    # Skip a bad chunk rather than losing every chunk already synthesized.
                    self.logger.add_event(
                        "warn", f"Skipped one unreadable section of '{os.path.basename(file)}'", str(chunk_error)
                    )

                self._events.put(("progress", file, (i + 1) / total))
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

    def _synthesize_chunk(self, chunk_text, chunk_path, use_piper, pyttsx3_speaker, settings):
        if use_piper:
            # length_scale is inverse of speed: 2x speed -> half the length_scale.
            PiperEngine.synthesize(
                chunk_text,
                settings["voice"],
                chunk_path,
                length_scale=1.0 / max(settings["speed"], 0.1),
                noise_scale=settings["expressiveness"],
            )
        else:
            pyttsx3_speaker.save_to_file(chunk_text, chunk_path)
            pyttsx3_speaker.runAndWait()


def _concatenate_wavs(chunk_paths, output_path):
    with wave.open(chunk_paths[0], "rb") as first:
        params = first.getparams()

    with wave.open(output_path, "wb") as out:
        out.setparams(params)
        for path in chunk_paths:
            with wave.open(path, "rb") as chunk:
                out.writeframes(chunk.readframes(chunk.getnframes()))
