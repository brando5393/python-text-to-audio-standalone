import ConversionEstimate as ce


def test_estimate_seconds_pyttsx3_matches_measured_rate():
    # ~700,000 chars in ~180s per the README's own measured conversion.
    seconds = ce.estimate_seconds(700_000, "pyttsx3", None)
    assert 170 < seconds < 190


def test_estimate_seconds_piper_high_tier_matches_measured_rate():
    seconds = ce.estimate_seconds(3000, "piper", "en_US-ryan-high")
    assert 29 < seconds < 33


def test_estimate_seconds_piper_low_tier_is_roughly_five_times_faster():
    high = ce.estimate_seconds(3000, "piper", "en_US-ryan-high")
    low = ce.estimate_seconds(3000, "piper", "en_US-danny-low")
    assert 4.5 < high / low < 5.5


def test_estimate_seconds_piper_medium_tier_uses_standard_rate():
    medium = ce.estimate_seconds(3000, "piper", "en_US-amy-medium")
    high = ce.estimate_seconds(3000, "piper", "en_US-ryan-high")
    assert medium == high  # medium and high share the same measured baseline rate


def test_estimate_seconds_scales_linearly_with_length():
    small = ce.estimate_seconds(1000, "pyttsx3", None)
    large = ce.estimate_seconds(2000, "pyttsx3", None)
    assert large == small * 2


def test_format_duration_seconds_only():
    assert ce.format_duration(45) == "45s"
    assert ce.format_duration(0) == "0s"


def test_format_duration_minutes_and_seconds():
    assert ce.format_duration(200) == "3m 20s"


def test_format_duration_exact_minutes_omits_seconds():
    assert ce.format_duration(180) == "3m"


def test_format_duration_hours_and_minutes():
    assert ce.format_duration(8100) == "2h 15m"


def test_format_duration_exact_hours_omits_minutes():
    assert ce.format_duration(7200) == "2h"
