import os
import queue
import threading

import pyttsx3

import Config
import LogManager as logger
import PiperEngine
import TextExtraction


class Converter:
    """Converts documents to audio.

    Conversion runs on a background worker thread so the UI stays responsive; results
    (including per-file success/failure) are delivered back to the caller via a
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

                if use_piper:
                    # length_scale is inverse of speed: 2x speed -> half the length_scale.
                    PiperEngine.synthesize(
                        clean_text,
                        settings["voice"],
                        output_file,
                        length_scale=1.0 / max(settings["speed"], 0.1),
                        noise_scale=settings["expressiveness"],
                    )
                    engine_used = f"Piper ({settings['voice']})"
                else:
                    pyttsx3_speaker.save_to_file(clean_text, output_file)
                    pyttsx3_speaker.runAndWait()
                    engine_used = "system voice (pyttsx3)"

                self.logger.add_event("info", "File converted successfully", f"{engine_used} -> {output_file}")
                self._events.put(("done", file, output_file))
            except Exception as e:
                error_message = f"Failed to convert file '{file}' to audio: {str(e)}"
                self.logger.add_event("error", error_message)
                self._events.put(("error", file, str(e)))
