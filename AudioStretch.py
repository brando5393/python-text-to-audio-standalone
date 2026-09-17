"""Pitch-preserving time-stretch DSP for live playback speed/tone control.

AudioPlayer.py needs to change playback speed without the "chipmunk effect" (pitch
rising/falling with speed) and needs to shift pitch independently of speed ("Tone").
MCI (the old playback backend) can't do either live -- see AudioPlayer.py's module
docstring for why the backend changed at all.

Approach chosen: a hand-rolled WSOLA (Waveform Similarity Overlap-Add) time-stretcher
using only numpy, rather than `librosa.effects.time_stretch`. librosa would do this in
one call, but its dependency chain pulls in numba (JIT compilation via LLVM) and scipy
on top of numpy/soundfile, which is exactly the kind of native-dependency stack that
has a documented history of breaking under PyInstaller/cx_Freeze (numba bundles its own
LLVM toolchain and dynamically locates typed-signature caches at runtime in ways a
frozen build's import hooks don't always see) -- a real risk for this app's frozen-.exe
distribution model, not a hypothetical one. A pure-numpy WSOLA has no such risk: it's
plain Python + array math, so anything that already freezes numpy freezes this too. It
costs more code and needs its own tests (see tests/test_audio_stretch.py), but multiple
open source pitch/time-stretch tools (e.g. `paulstretch`, several DAW time-stretch
plugins) use the same core WSOLA algorithm, so it's a proven technique, not a novel one.

Pitch shift is implemented as "resample, then time-stretch back to the original tempo"
(a standard technique): resampling by `pitch_ratio` changes both pitch and tempo by
that ratio; re-stretching by 1/pitch_ratio restores the original tempo while keeping
the shifted pitch. Speed is folded into the same stretch step so only one WSOLA pass is
needed per chunk.
"""

import numpy as np

FRAME_SIZE = 1024
ANALYSIS_HOP = FRAME_SIZE // 2  # 50% overlap
SEARCH_RADIUS = 256  # +/- frames WSOLA searches for the best-matching next segment
SEARCH_STRIDE = 4  # candidates are sampled every N frames within the search radius, to bound cost

_WINDOW = np.hanning(FRAME_SIZE).astype(np.float32)


def _resample_linear(samples, ratio):
    """Resamples `samples` (frames, channels) by `ratio` via linear interpolation.
    ratio > 1 shortens (speeds up + raises pitch); ratio < 1 lengthens (slows + lowers
    pitch). This is the *naive* chipmunk-effect resample -- used here only as the first
    half of the pitch-shift technique above, always paired with a compensating
    WSOLA stretch so the net effect on tempo is neutral."""
    n = samples.shape[0]
    if n == 0 or ratio == 1.0:
        return samples
    new_n = max(1, int(round(n / ratio)))
    src_idx = np.arange(new_n, dtype=np.float64) * ratio
    idx0 = np.clip(src_idx.astype(np.int64), 0, n - 1)
    idx1 = np.clip(idx0 + 1, 0, n - 1)
    frac = (src_idx - idx0).astype(np.float32)[:, None]
    return samples[idx0] * (1.0 - frac) + samples[idx1] * frac


def wsola_stretch(samples, factor):
    """Time-stretches `samples` (frames, channels float32) by `factor` (output is
    roughly `factor` times as long) while preserving pitch, using WSOLA.

    Returns (output_samples, source_frames_consumed). `source_frames_consumed` is how
    much of `samples` was actually read (WSOLA's search can nudge the read position
    around, so it isn't exactly len(samples) even at factor == 1) -- callers use it to
    track true playback position.
    """
    factor = max(0.1, min(10.0, float(factor)))
    n, channels = samples.shape
    if n <= FRAME_SIZE:
        return samples.copy(), n

    synthesis_hop = ANALYSIS_HOP
    analysis_hop = max(1, int(round(synthesis_hop / factor)))
    # The correlation search below is allowed to pick a best-matching frame anywhere
    # within `tolerance` of the nominal next position. Two failure modes bound this
    # value from opposite directions, both found via real hung/wrong-length test runs
    # (see tests/test_audio_stretch.py), not hypothetically:
    #   - Too *wide* (close to or exceeding analysis_hop): a near-periodic signal (a
    #     pure test tone, but also any sustained voiced vowel in real speech) has
    #     many near-equally-good phase matches within the window, and the search
    #     would often settle on one barely past the previous position -- net progress
    #     through the source shrinks toward ~0 every iteration, which technically
    #     isn't an infinite loop (progress is still strictly positive) but bloats the
    #     output to many times the intended length.
    #   - Too wide in the other, more dangerous direction (>= analysis_hop) directly
    #     risks the original CPU-pegging infinite loop this guard exists to prevent:
    #     search_lo could fall behind (or equal) the previous read position.
    # A quarter of the nominal hop is enough room to correct phase discontinuities at
    # a splice point without letting the search wander far enough to strand progress.
    tolerance = min(SEARCH_RADIUS, max(0, analysis_hop // 8))

    out_capacity = int(n * factor) + FRAME_SIZE * 2
    output = np.zeros((out_capacity, channels), dtype=np.float32)
    norm = np.zeros(out_capacity, dtype=np.float32)

    frame = samples[0:FRAME_SIZE] * _WINDOW[:, None]
    output[0:FRAME_SIZE] += frame
    norm[0:FRAME_SIZE] += _WINDOW
    last_frame_mono = frame.mean(axis=1)
    write_pos = synthesis_hop
    read_pos = 0

    max_pos = n - FRAME_SIZE
    while read_pos + 1 + FRAME_SIZE <= n:
        ideal_pos = read_pos + analysis_hop
        # Both bounds are clamped to max_pos (so a slice never runs past the end of
        # `samples`) and floored at read_pos + 1 (so it never stalls or goes
        # backwards) -- read_pos + 1 <= max_pos is guaranteed by the loop condition
        # above, so search_lo always ends up in [read_pos + 1, max_pos].
        search_lo = min(max(read_pos + 1, ideal_pos - tolerance), max_pos)
        search_hi = min(max(search_lo, ideal_pos + tolerance), max_pos)

        best_pos = search_lo
        best_score = -np.inf
        for cand in range(search_lo, search_hi + 1, SEARCH_STRIDE):
            cand_mono = samples[cand:cand + FRAME_SIZE].mean(axis=1)
            score = float(np.dot(last_frame_mono, cand_mono))
            if score > best_score:
                best_score = score
                best_pos = cand

        frame = samples[best_pos:best_pos + FRAME_SIZE] * _WINDOW[:, None]
        end = write_pos + FRAME_SIZE
        if end > output.shape[0]:
            pad = end - output.shape[0] + FRAME_SIZE
            output = np.vstack([output, np.zeros((pad, channels), dtype=np.float32)])
            norm = np.concatenate([norm, np.zeros(pad, dtype=np.float32)])
        output[write_pos:end] += frame
        norm[write_pos:end] += _WINDOW
        last_frame_mono = frame.mean(axis=1)

        write_pos += synthesis_hop
        read_pos = best_pos  # always > the previous read_pos -- see `tolerance` above

    norm[norm < 1e-6] = 1.0
    result = (output[:write_pos] / norm[:write_pos, None]).astype(np.float32)
    return result, min(max(read_pos, 1), n)


def process(source_chunk, speed, tone_semitones):
    """Applies live speed (tempo, pitch-preserving) and tone (pitch shift, in
    semitones) to a chunk of source audio. Returns (output_samples, source_frames_
    consumed) -- consumed is always > 0 for a non-empty input, so a caller looping
    over a file always makes forward progress.
    """
    n = source_chunk.shape[0]
    if n == 0:
        return source_chunk, 0

    pitch_ratio = 2.0 ** (tone_semitones / 12.0)
    combined = pitch_ratio * max(0.1, speed)

    if n < FRAME_SIZE * 2:
        # Too short to run windowed WSOLA on (e.g. the last fractional chunk of a
        # file) -- resample directly by the combined factor instead. This is the
        # "naive" pitch-shifting resample everywhere else, but for a sub-second tail
        # it's inaudible, and it guarantees the whole remaining chunk is consumed so
        # playback can actually finish the file.
        out = _resample_linear(source_chunk, combined)
        return out, n

    resampled = _resample_linear(source_chunk, pitch_ratio) if pitch_ratio != 1.0 else source_chunk
    stretch_factor = pitch_ratio / max(0.1, speed)
    stretched, consumed_resampled = wsola_stretch(resampled, stretch_factor)

    consumed_source = int(round(consumed_resampled * pitch_ratio)) if pitch_ratio != 1.0 else consumed_resampled
    consumed_source = min(max(consumed_source, 1), n)
    return stretched, consumed_source
