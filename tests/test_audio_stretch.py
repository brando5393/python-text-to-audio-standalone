import numpy as np

import AudioStretch


def _sine(seconds, rate=8000, freq=440.0, channels=1):
    n = int(seconds * rate)
    t = np.arange(n) / rate
    tone = (0.5 * np.sin(2 * np.pi * freq * t)).astype(np.float32)
    return np.tile(tone[:, None], (1, channels))


def test_process_empty_chunk_returns_empty_and_consumes_nothing():
    empty = np.zeros((0, 1), dtype=np.float32)
    out, consumed = AudioStretch.process(empty, 1.0, 0.0)
    assert consumed == 0
    assert out.shape[0] == 0


def test_process_always_makes_forward_progress_on_a_short_tail_chunk():
    """Regression guard: the last fractional chunk of a file is shorter than WSOLA's
    frame size, so `process` must fall back to a direct resample there -- otherwise a
    producer loop driven by `consumed` frames could stall forever at end of file."""
    short = _sine(0.05)  # well under FRAME_SIZE * 2 at 8kHz
    out, consumed = AudioStretch.process(short, 1.7, 3.0)
    assert consumed == short.shape[0]
    assert out.shape[0] > 0


def test_process_speed_up_produces_roughly_half_length_output():
    samples = _sine(2.0)
    normal_out, _ = AudioStretch.process(samples, 1.0, 0.0)
    fast_out, _ = AudioStretch.process(samples, 2.0, 0.0)
    ratio = fast_out.shape[0] / normal_out.shape[0]
    assert 0.35 < ratio < 0.65


def test_process_slow_down_produces_roughly_double_length_output():
    samples = _sine(2.0)
    normal_out, _ = AudioStretch.process(samples, 1.0, 0.0)
    slow_out, _ = AudioStretch.process(samples, 0.5, 0.0)
    ratio = slow_out.shape[0] / normal_out.shape[0]
    assert 1.6 < ratio < 2.4


def test_process_tone_shift_preserves_tempo():
    """The whole point of pitch-preserving speed control: shifting Tone (pitch) at
    speed 1.0 should leave output duration close to unchanged, unlike a naive resample
    (which would roughly halve/double duration for a +/-12 semitone shift)."""
    samples = _sine(2.0)
    normal_out, _ = AudioStretch.process(samples, 1.0, 0.0)
    shifted_out, _ = AudioStretch.process(samples, 1.0, 6.0)
    ratio = shifted_out.shape[0] / normal_out.shape[0]
    assert 0.8 < ratio < 1.2


def test_process_preserves_channel_count():
    stereo = _sine(1.0, channels=2)
    out, _ = AudioStretch.process(stereo, 1.3, -2.0)
    assert out.shape[1] == 2


def test_wsola_stretch_identity_factor_keeps_similar_length():
    samples = _sine(1.0)
    out, consumed = AudioStretch.wsola_stretch(samples, 1.0)
    assert consumed > 0
    assert 0.85 < out.shape[0] / samples.shape[0] < 1.15


def test_wsola_stretch_short_input_passes_through_unchanged():
    tiny = _sine(0.01)  # shorter than FRAME_SIZE
    out, consumed = AudioStretch.wsola_stretch(tiny, 1.5)
    assert consumed == tiny.shape[0]
    assert np.array_equal(out, tiny)
