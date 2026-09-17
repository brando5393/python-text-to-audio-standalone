from SleepTimer import SleepTimer


def test_inactive_by_default():
    timer = SleepTimer()
    assert timer.is_active() is False
    assert timer.is_expired() is False
    assert timer.remaining_seconds() == 0


def test_start_arms_the_timer():
    timer = SleepTimer()
    timer.start(15, now=1000.0)
    assert timer.is_active() is True
    assert timer.is_expired(now=1000.0) is False
    assert timer.remaining_seconds(now=1000.0) == 15 * 60


def test_expires_once_the_duration_elapses():
    timer = SleepTimer()
    timer.start(15, now=1000.0)
    assert timer.is_expired(now=1000.0 + 15 * 60 - 1) is False
    assert timer.is_expired(now=1000.0 + 15 * 60) is True
    assert timer.is_expired(now=1000.0 + 15 * 60 + 30) is True


def test_remaining_seconds_never_goes_negative_past_expiry():
    timer = SleepTimer()
    timer.start(15, now=1000.0)
    assert timer.remaining_seconds(now=1000.0 + 999999) == 0


def test_starting_with_zero_minutes_behaves_like_off():
    timer = SleepTimer()
    timer.start(0, now=1000.0)
    assert timer.is_active() is False


def test_starting_with_negative_minutes_behaves_like_off():
    timer = SleepTimer()
    timer.start(-5, now=1000.0)
    assert timer.is_active() is False


def test_cancel_turns_an_active_timer_off():
    timer = SleepTimer()
    timer.start(30, now=1000.0)
    timer.cancel()
    assert timer.is_active() is False
    assert timer.is_expired(now=999999.0) is False


def test_cancel_is_safe_when_never_started():
    timer = SleepTimer()
    timer.cancel()  # must not raise
    assert timer.is_active() is False


def test_starting_again_replaces_the_previous_deadline():
    timer = SleepTimer()
    timer.start(15, now=1000.0)
    timer.start(60, now=1000.0)
    assert timer.remaining_seconds(now=1000.0) == 60 * 60


def test_already_expired_deadline_reports_expired_immediately():
    """A timer started with `now` already past what would be its own deadline (e.g. a
    resumed/late tick) must report expired right away, not wait another full duration."""
    timer = SleepTimer()
    timer.start(15, now=1000.0)
    assert timer.is_expired(now=1000.0 + 15 * 60 + 3600) is True


def test_remaining_minutes_label_rounds_up():
    timer = SleepTimer()
    timer.start(15, now=1000.0)
    # 14 minutes 1 second left should still read "15 min left", not "14".
    assert timer.remaining_minutes_label(now=1000.0 + 59) == 15
    assert timer.remaining_minutes_label(now=1000.0 + 60) == 14


def test_remaining_minutes_label_is_zero_when_inactive():
    timer = SleepTimer()
    assert timer.remaining_minutes_label() == 0
