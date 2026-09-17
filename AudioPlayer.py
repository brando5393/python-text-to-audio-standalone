import collections
import threading
import wave

import numpy as np
import sounddevice as sd

import AudioStretch

DEFAULT_ALIAS = "texttoaudio_player"

CHUNK_SECONDS = 1.0  # how much source audio the producer thread processes per iteration
BUFFER_AHEAD_SECONDS = 3.0  # producer stops getting ahead of playback by more than this
MIN_SPEED, MAX_SPEED = 0.5, 2.5
MIN_TONE, MAX_TONE = -6.0, 6.0


def wav_duration_ms(path):
    """Reads a WAV file's duration without opening it for playback -- used to decide
    whether a saved playback position is worth offering to resume from, before playback
    is ever involved. Returns 0 if the file can't be read as a WAV (wrong format, missing)."""
    try:
        with wave.open(path, "rb") as wav_file:
            return int(1000 * wav_file.getnframes() / wav_file.getframerate())
    except (wave.Error, OSError, ZeroDivisionError):
        return 0


def _pcm_bytes_to_float32(raw, width, channels):
    if width == 1:
        data = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    elif width == 2:
        data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    elif width == 4:
        data = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
    else:
        # Odd widths (e.g. 24-bit) aren't a numpy dtype -- unpack by hand. Rare in
        # practice (Piper and pyttsx3/SAPI both emit 16-bit PCM), kept only so an
        # unusual WAV doesn't crash playback outright.
        count = len(raw) // width
        data = np.zeros(count, dtype=np.float32)
        scale = float(2 ** (8 * width - 1))
        for i in range(count):
            value = int.from_bytes(raw[i * width:(i + 1) * width], byteorder="little", signed=True)
            data[i] = value / scale
    channels = max(1, channels)
    frame_count = data.shape[0] // channels
    return data[:frame_count * channels].reshape(frame_count, channels)


def _read_wav(path):
    with wave.open(path, "rb") as w:
        channels = w.getnchannels()
        width = w.getsampwidth()
        rate = w.getframerate()
        raw = w.readframes(w.getnframes())
    return _pcm_bytes_to_float32(raw, width, channels), rate, channels


def _load_samples(path):
    """Loads an audio file into a (frames, channels) float32 array, for the in-memory
    playback buffer AudioPlayer streams from. WAVs -- the only format Talebrew itself
    ever produces -- are read with the stdlib `wave` module, matching the pattern
    Converter.py already uses elsewhere in this codebase. The one other file type this
    app ever plays is the .mp3 voice-preview samples PiperEngine downloads for Settings'
    "Preview This Voice" button; those go through `soundfile` instead, which bundles its
    own decoder (libsndfile) as part of its wheel, so it needs nothing separately
    installed on the end user's machine.
    """
    if path.lower().endswith(".wav"):
        return _read_wav(path)
    import soundfile as sf

    data, rate = sf.read(path, dtype="float32", always_2d=True)
    return data, rate, data.shape[1]


class AudioPlayer:
    """Streams WAV/MP3 playback via `sounddevice` (PortAudio) with live, pitch-preserving
    speed and tone (pitch) control -- see AudioStretch.py for the DSP.

    This replaces an earlier implementation built on the Windows MCI API
    (`mciSendStringW` against winmm.dll). MCI needed no dependency at all and worked
    fine for plain transport control (play/pause/seek), but its `waveaudio` device type
    has no live rate or pitch control whatsoever -- not a missing feature, a real
    limitation of the API -- so it couldn't support "Speed" and "Tone" becoming live
    playback controls instead of synthesis-time settings. Reading the WAV into memory
    and streaming it through PortAudio, with a background thread applying WSOLA
    time-stretch/pitch-shift as it's read, is what makes an in-progress speed or tone
    change take effect immediately on already-synthesized audio.
    """

    def __init__(self, alias=DEFAULT_ALIAS):
        # `alias` is kept only for API compatibility with the MCI-era constructor and to
        # identify an instance in logs/tests -- isolation between two AudioPlayer
        # instances (e.g. the main player and Settings' voice-preview player) is now
        # inherent, since each instance owns its own buffer, thread, and PortAudio
        # stream rather than sharing OS-level state the way MCI aliases did.
        self._alias = alias
        self._current_path = None
        self._samples = None
        self._samplerate = 44100
        self._channels = 1
        self._total_frames = 0

        self._speed = 1.0
        self._tone = 0.0

        self._lock = threading.RLock()
        self._chunks = collections.deque()  # (audio[frames,channels], src_start, src_end)
        self._chunk_offset = 0
        self._heard_source_frame = 0
        self._produce_from = 0
        self._produced_output_frames = 0
        self._consumed_output_frames = 0
        self._finished = False

        self._playing = False
        self._stop_event = threading.Event()
        self._restart_event = threading.Event()
        self._producer_thread = None
        self._stream = None

    # -- public transport controls (unchanged interface from the MCI-era player) -----

    def play(self, path):
        """Stops any current playback and starts playing `path` from the beginning."""
        self.stop()
        samples, rate, channels = _load_samples(path)
        self._samples = samples
        self._samplerate = rate
        self._channels = channels
        self._total_frames = samples.shape[0]
        self._current_path = path

        self._chunks.clear()
        self._chunk_offset = 0
        self._heard_source_frame = 0
        self._produce_from = 0
        self._produced_output_frames = 0
        self._consumed_output_frames = 0
        self._finished = False

        self._stop_event.clear()
        self._restart_event.clear()
        self._producer_thread = threading.Thread(target=self._produce_loop, daemon=True)
        self._producer_thread.start()

        self._stream = sd.OutputStream(
            samplerate=self._samplerate, channels=self._channels, dtype="float32",
            callback=self._audio_callback,
        )
        self._stream.start()
        self._playing = True

    def pause(self):
        if self._current_path is not None and self._stream is not None:
            self._stream.stop()
            self._playing = False

    def resume(self):
        if self._current_path is not None and self._stream is not None:
            self._stream.start()
            self._playing = True

    def stop(self):
        self._stop_event.set()
        self._restart_event.set()
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        if self._producer_thread is not None:
            self._producer_thread.join(timeout=1.0)
            self._producer_thread = None
        self._current_path = None
        self._samples = None
        self._playing = False

    def current_path(self):
        return self._current_path

    def seek_ms(self, position_ms):
        if self._current_path is None:
            return
        target_frame = int(max(0, position_ms) / 1000 * self._samplerate)
        target_frame = min(target_frame, self._total_frames)
        with self._lock:
            self._heard_source_frame = target_frame
            self._chunks.clear()
            self._chunk_offset = 0
            self._produce_from = target_frame
            self._finished = False
            self._restart_event.set()
        if self._stream is not None and not self._playing:
            self._stream.start()
            self._playing = True

    def is_playing(self):
        return self._current_path is not None and self._playing

    def position_ms(self):
        if self._current_path is None:
            return 0
        return int(1000 * self._heard_source_frame / self._samplerate)

    def length_ms(self):
        if self._current_path is None:
            return 0
        return int(1000 * self._total_frames / self._samplerate)

    # -- new live playback controls ---------------------------------------------------

    def set_speed(self, multiplier):
        """Sets live playback speed (tempo), pitch-preserving. 1.0 = normal."""
        multiplier = max(MIN_SPEED, min(MAX_SPEED, float(multiplier)))
        with self._lock:
            if multiplier != self._speed:
                self._speed = multiplier
                self._reset_from_current_position()

    def set_tone(self, semitones):
        """Sets live pitch shift, in semitones, independent of speed. 0 = normal."""
        semitones = max(MIN_TONE, min(MAX_TONE, float(semitones)))
        with self._lock:
            if semitones != self._tone:
                self._tone = semitones
                self._reset_from_current_position()

    def get_speed(self):
        return self._speed

    def get_tone(self):
        return self._tone

    def _reset_from_current_position(self):
        # Called with self._lock held. Drops any already-produced-but-not-yet-heard
        # audio and tells the producer thread to resume generating from exactly what's
        # currently audible, using the new speed/tone -- so a mid-playback adjustment
        # takes effect immediately rather than only once whatever was already buffered
        # ahead finishes playing.
        if self._current_path is None:
            return
        self._chunks.clear()
        self._chunk_offset = 0
        self._produce_from = self._heard_source_frame
        self._finished = False
        self._restart_event.set()

    # -- internals ----------------------------------------------------------------------

    def _audio_callback(self, outdata, frames, time_info, status):
        filled = 0
        with self._lock:
            while filled < frames and self._chunks:
                chunk, src_start, src_end = self._chunks[0]
                available = chunk.shape[0] - self._chunk_offset
                take = min(available, frames - filled)
                outdata[filled:filled + take] = chunk[self._chunk_offset:self._chunk_offset + take]
                self._chunk_offset += take
                filled += take
                span = max(1, chunk.shape[0])
                frac = self._chunk_offset / span
                self._heard_source_frame = int(src_start + (src_end - src_start) * frac)
                if self._chunk_offset >= chunk.shape[0]:
                    self._chunks.popleft()
                    self._chunk_offset = 0
            self._consumed_output_frames += filled
            finished_and_empty = self._finished and not self._chunks
        if filled < frames:
            outdata[filled:] = 0
        if finished_and_empty and filled == 0:
            self._playing = False

    def _produce_loop(self):
        while not self._stop_event.is_set():
            with self._lock:
                start = self._produce_from
                speed = self._speed
                tone = self._tone
                ahead_frames = self._produced_output_frames - self._consumed_output_frames

            if start >= self._total_frames:
                with self._lock:
                    self._finished = True
                self._restart_event.wait(timeout=0.2)
                self._restart_event.clear()
                continue

            if ahead_frames > BUFFER_AHEAD_SECONDS * self._samplerate:
                if self._restart_event.wait(timeout=0.05):
                    self._restart_event.clear()
                continue

            chunk_len = int(CHUNK_SECONDS * self._samplerate)
            end = min(self._total_frames, start + chunk_len)
            source_chunk = self._samples[start:end]
            processed, consumed = AudioStretch.process(source_chunk, speed, tone)

            with self._lock:
                if self._produce_from != start:
                    continue  # a seek/speed/tone change happened mid-process -- discard, it's stale
                self._chunks.append((processed, start, start + consumed))
                self._produced_output_frames += processed.shape[0]
                self._produce_from = start + consumed
                if start + consumed >= self._total_frames:
                    self._finished = True
