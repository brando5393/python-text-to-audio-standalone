import PlaybackQueue as pq


def test_next_file_returns_the_following_entry():
    order = [r"C:\a.wav", r"C:\b.wav", r"C:\c.wav"]
    assert pq.next_file(r"C:\a.wav", order) == r"C:\b.wav"
    assert pq.next_file(r"C:\b.wav", order) == r"C:\c.wav"


def test_next_file_returns_none_at_the_end_of_the_queue():
    """No wraparound -- reaching the last file stops the queue rather than looping
    back to the first."""
    order = [r"C:\a.wav", r"C:\b.wav"]
    assert pq.next_file(r"C:\b.wav", order) is None


def test_next_file_returns_none_for_empty_queue():
    assert pq.next_file(r"C:\a.wav", []) is None
    assert pq.next_file(None, []) is None


def test_next_file_starts_from_the_beginning_when_nothing_is_currently_playing():
    order = [r"C:\a.wav", r"C:\b.wav"]
    assert pq.next_file(None, order) == r"C:\a.wav"


def test_next_file_starts_from_the_beginning_when_current_path_is_not_in_the_queue():
    """E.g. the currently playing file was removed/moved since playback started."""
    order = [r"C:\a.wav", r"C:\b.wav"]
    assert pq.next_file(r"C:\gone.wav", order) == r"C:\a.wav"


def test_previous_file_returns_the_preceding_entry():
    order = [r"C:\a.wav", r"C:\b.wav", r"C:\c.wav"]
    assert pq.previous_file(r"C:\c.wav", order) == r"C:\b.wav"
    assert pq.previous_file(r"C:\b.wav", order) == r"C:\a.wav"


def test_previous_file_returns_none_at_the_start_of_the_queue():
    order = [r"C:\a.wav", r"C:\b.wav"]
    assert pq.previous_file(r"C:\a.wav", order) is None


def test_previous_file_returns_none_for_empty_queue():
    assert pq.previous_file(r"C:\a.wav", []) is None


def test_previous_file_starts_from_the_end_when_nothing_is_currently_playing():
    order = [r"C:\a.wav", r"C:\b.wav"]
    assert pq.previous_file(None, order) == r"C:\b.wav"


def test_previous_file_starts_from_the_end_when_current_path_is_not_in_the_queue():
    order = [r"C:\a.wav", r"C:\b.wav"]
    assert pq.previous_file(r"C:\gone.wav", order) == r"C:\b.wav"


def test_next_and_previous_agree_with_each_other_across_the_middle_of_a_queue():
    order = [r"C:\a.wav", r"C:\b.wav", r"C:\c.wav"]
    forward = pq.next_file(r"C:\a.wav", order)
    assert pq.previous_file(forward, order) == r"C:\a.wav"
