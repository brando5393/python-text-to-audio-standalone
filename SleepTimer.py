import time

# Preset choices shown in the Playback panel's sleep-timer control. 0 means "Off".
PRESET_MINUTES = [0, 15, 30, 45, 60]

# Shared between main.py and MiniPlayer.py so both windows' sleep-timer dropdowns show
# identical choices/labels, and so the label text used while counting down ("Sleep: N
# min left") lives in exactly one place.
LABELS_BY_MINUTES = {0: "Sleep: Off", 15: "Sleep: 15 min", 30: "Sleep: 30 min", 45: "Sleep: 45 min", 60: "Sleep: 60 min"}
CHOICES = list(LABELS_BY_MINUTES.values())
MINUTES_BY_LABEL = {v: k for k, v in LABELS_BY_MINUTES.items()}


class SleepTimer:
    """Tracks a single "pause playback after N minutes" countdown.

    Deliberately has no idea about Tkinter, `AudioPlayer`, or `app.after()` -- it is
    just "given a start time and a duration, has it expired yet", so it can be unit
    tested directly without a real Tk event loop. The `now` parameter on every method
    defaults to `time.monotonic()` but can be passed explicitly by tests to simulate
    time passing without any real waiting, and monotonic time is used (not
    `time.time()`) so the countdown can't be thrown off by a system clock change.
    """

    def __init__(self):
        self._deadline = None  # monotonic seconds at which this timer fires, or None if off

    def start(self, minutes, now=None):
        """Arms the timer for `minutes` from `now`. `minutes <= 0` is treated the same
        as cancel() -- the "Off" preset -- so callers don't need a separate branch."""
        if minutes <= 0:
            self.cancel()
            return
        if now is None:
            now = time.monotonic()
        self._deadline = now + minutes * 60

    def cancel(self):
        self._deadline = None

    def is_active(self):
        return self._deadline is not None

    def is_expired(self, now=None):
        if self._deadline is None:
            return False
        if now is None:
            now = time.monotonic()
        return now >= self._deadline

    def remaining_seconds(self, now=None):
        """Seconds left, floored at 0. 0 both while inactive and the instant it expires --
        callers distinguish those with is_active()/is_expired() if they need to."""
        if self._deadline is None:
            return 0
        if now is None:
            now = time.monotonic()
        return max(0.0, self._deadline - now)

    def remaining_minutes_label(self, now=None):
        """A human "N min left" style number, rounded up so it never reads "0 min left"
        while there's still time on the clock (e.g. 1 second left displays as "1 min
        left", not "0 min left")."""
        seconds = self.remaining_seconds(now)
        return int(seconds // 60) + (1 if seconds % 60 else 0)
