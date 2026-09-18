from AutoPauseMonitor import AutoPauseController, AutoPauseMonitor


def test_pauses_when_other_audio_starts_while_playing():
    controller = AutoPauseController()
    action = controller.evaluate(other_audio_active=True, is_playing=True, now=0.0)
    assert action == "pause"
    assert controller.auto_paused is True


def test_does_not_auto_pause_if_already_paused():
    """If Talebrew isn't playing (already paused/stopped), other audio starting should
    not report a pause action -- there's nothing to pause, and it must not be mistaken
    for one this controller triggered."""
    controller = AutoPauseController()
    action = controller.evaluate(other_audio_active=True, is_playing=False, now=0.0)
    assert action is None
    assert controller.auto_paused is False


def test_resumes_after_debounce_once_other_audio_stops():
    controller = AutoPauseController(resume_debounce_seconds=1.5)
    assert controller.evaluate(other_audio_active=True, is_playing=True, now=0.0) == "pause"

    # Other audio just stopped -- Talebrew is (correctly) not playing since we paused it.
    assert controller.evaluate(other_audio_active=False, is_playing=False, now=0.5) is None
    assert controller.evaluate(other_audio_active=False, is_playing=False, now=1.0) is None
    # Debounce window has now elapsed since quiet began at t=0.5.
    action = controller.evaluate(other_audio_active=False, is_playing=False, now=2.1)
    assert action == "resume"
    assert controller.auto_paused is False


def test_does_not_auto_resume_a_manual_pause():
    """A pause the controller never triggered (is_playing was already False the whole
    time -- e.g. the user paused it themselves) must never be auto-resumed."""
    controller = AutoPauseController(resume_debounce_seconds=1.0)
    # Other audio starts and stops, but Talebrew was never playing (user had it paused).
    assert controller.evaluate(other_audio_active=True, is_playing=False, now=0.0) is None
    assert controller.evaluate(other_audio_active=False, is_playing=False, now=0.1) is None
    assert controller.evaluate(other_audio_active=False, is_playing=False, now=5.0) is None
    assert controller.auto_paused is False


def test_manual_pause_that_started_before_other_audio_is_never_auto_resumed():
    """The user pauses on their own (no other audio involved yet); other audio then
    starts and stops while Talebrew stays paused throughout. Since this controller never
    triggered the pause, it must not resume playback afterward."""
    controller = AutoPauseController(resume_debounce_seconds=1.0)
    # User manually pauses; controller sees a plain "nothing else going on" tick.
    assert controller.evaluate(other_audio_active=False, is_playing=False, now=0.0) is None
    # Other audio starts while Talebrew is already (manually) paused.
    assert controller.evaluate(other_audio_active=True, is_playing=False, now=1.0) is None
    # Other audio stops again.
    for t in (1.5, 2.0, 3.0):
        assert controller.evaluate(other_audio_active=False, is_playing=False, now=t) is None
    assert controller.auto_paused is False


def test_rapid_flutter_within_debounce_window_does_not_cause_spurious_resume():
    """Several quick on/off bursts of other audio (e.g. a flurry of IM notification
    dings) within the debounce window must not trigger a resume until things are
    actually quiet for the full debounce period."""
    controller = AutoPauseController(resume_debounce_seconds=1.5)
    assert controller.evaluate(other_audio_active=True, is_playing=True, now=0.0) == "pause"

    # Flutter: quiet, then active again, repeatedly -- each burst resets the debounce.
    assert controller.evaluate(other_audio_active=False, is_playing=False, now=0.5) is None
    assert controller.evaluate(other_audio_active=True, is_playing=False, now=0.8) is None
    assert controller.evaluate(other_audio_active=False, is_playing=False, now=1.0) is None
    assert controller.evaluate(other_audio_active=True, is_playing=False, now=1.3) is None
    assert controller.evaluate(other_audio_active=False, is_playing=False, now=1.6) is None
    # Only 1.4s quiet so far since the last burst at 1.3 -- still short of 1.5s.
    assert controller.evaluate(other_audio_active=False, is_playing=False, now=2.6) is None
    assert controller.auto_paused is True

    # Now genuinely quiet for the full debounce window.
    action = controller.evaluate(other_audio_active=False, is_playing=False, now=4.2)
    assert action == "resume"


def test_reset_clears_auto_pause_tracking():
    controller = AutoPauseController()
    controller.evaluate(other_audio_active=True, is_playing=True, now=0.0)
    assert controller.auto_paused is True
    controller.reset()
    assert controller.auto_paused is False


class _FakeApp:
    def after(self, *_args, **_kwargs):
        pass


class _FakePlayer:
    def is_playing(self):
        return True


def test_notify_playback_changed_resets_a_stale_auto_pause():
    """Without this, switching files (or stopping) while an auto-pause from the
    *previous* file is still unresolved would leave the controller thinking it owns a
    pause it no longer does -- so once the call/notification that triggered it ends, it
    would force-resume whatever's playing now, even if the user paused that manually."""
    monitor = AutoPauseMonitor(_FakeApp(), _FakePlayer())
    monitor.controller.evaluate(other_audio_active=True, is_playing=True, now=0.0)
    assert monitor.controller.auto_paused is True

    monitor.notify_playback_changed()

    assert monitor.controller.auto_paused is False
