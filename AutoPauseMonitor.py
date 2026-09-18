"""Detects when audio activity starts on the system OUTSIDE Talebrew -- a Zoom/Teams
call, another app playing music, or a one-shot Windows notification sound -- and
pauses/resumes Talebrew's own playback around it.

Detection approach
-------------------
Windows offers two real mechanisms for this, and the choice between them matters:

1. ``IAudioSessionManager2::RegisterDuckNotification`` -- the OS's native "ducking"
   mechanism (what makes Spotify duck when a Teams call starts). It's event-driven, no
   polling needed. But per Microsoft's own docs ("Getting Ducking Events from a
   Communication Device"), it exists specifically so a media app can react "when a
   communication stream is opened or closed" -- i.e. it only fires for a session Windows
   has classified with the eCommunications role. A plain notification sound (played on
   Windows' "System Sounds" session) or another app's ordinary music playback is not a
   communications stream, and would never trigger it. So ducking alone would satisfy
   half of this feature (calls) and silently miss the other half (notification dings) --
   confirmed against Microsoft Learn, not assumed.

2. Polling ``IAudioSessionManager2::GetSessionEnumerator()`` and reading each OTHER
   session's ``IAudioMeterInformation`` peak value. Not event-driven, but a non-zero peak
   on any other session -- a call, a song, or a one-shot chime -- is caught the same way,
   satisfying both halves of the requirement with a single mechanism.

Decision: polling only, no ducking registration. A hybrid (register for ducking as a
low-latency signal for calls specifically, alongside polling for everything else) was
considered, but rejected: the polling loop already has to run continuously to catch
notification dings, and it also naturally catches call audio (a call's peak level stays
non-zero for as long as the call has audio), so registering for ducking notifications
would only shave the reaction time for the call case from "next poll" (<= POLL_INTERVAL_MS)
down to near-instant -- at the cost of a second, hand-rolled COM interface
(``IAudioVolumeDuckNotification`` isn't wrapped by pycaw, so it would mean raw comtypes
COM callback plumbing). That complexity wasn't judged worth it for a sub-second latency
win on only one of the two cases this feature needs to cover.

Architecture
------------
``AutoPauseController`` is the pure, directly-testable decision logic: given whether
other audio is currently active and whether Talebrew is currently playing, it decides
whether to pause or resume, tracking only "did *I* (the monitor) cause the current
pause" so a user's own manual pause is never auto-resumed out from under them. It reads
Talebrew's live ``is_playing()`` state on every tick rather than remembering "did the
user click pause" -- a pause is only ever recorded as auto-triggered at the moment this
controller itself decides to trigger it, so a manual pause (from the main window, the
Mini Player, or the keyboard shortcut -- any path) can never be mistaken for one of ours,
with no extra wiring needed at each of those call sites.

``AutoPauseMonitor`` wires that decision logic to the real ``AudioPlayer`` and to a
Tkinter ``app.after`` polling loop (matching this codebase's established
background-thread-plus-``app.after``-polling pattern, e.g. ``poll_file_info`` and
``track_playback_position`` in main.py) -- and to the raw pycaw/COM session polling.
Only ``AutoPauseController`` is unit tested directly; ``other_audio_is_active`` and
``AutoPauseMonitor`` depend on real Windows Core Audio sessions and are exercised via
manual verification instead, same as this app's other OS-integration pieces.
"""
import os
import time

try:
    from pycaw.pycaw import AudioUtilities
    from pycaw.api.endpointvolume import IAudioMeterInformation
    PYCAW_AVAILABLE = True
except ImportError:  # pragma: no cover -- exercised only on a system without pycaw installed
    PYCAW_AVAILABLE = False

# Normalized 0.0-1.0 peak level above which another session counts as "active". Kept
# low (well above float noise but far below a deliberately-quiet system sound) so a
# genuinely quiet notification chime still registers.
PEAK_THRESHOLD = 0.02

# How long other audio must have been silent before Talebrew auto-resumes. Keeps a
# rapid flutter of notification sounds (e.g. several IM pings in a row) from causing a
# stutter of pause/resume/pause/resume -- each new burst of activity resets the clock.
RESUME_DEBOUNCE_SECONDS = 1.5

# How often the Tk polling loop checks other sessions' peak levels. Cheap enough (a
# handful of COM calls) to run sub-second without noticeable CPU cost, but not so often
# that it's polling harder than it needs to for a "quiet-for-N-seconds" debounce anyway.
POLL_INTERVAL_MS = 750


class AutoPauseController:
    """Pure decision logic: given the current audio-activity signal and Talebrew's own
    live playback state, decides whether to pause or resume -- with no Windows/COM/Tk
    dependency, so it can be unit tested directly."""

    def __init__(self, resume_debounce_seconds=RESUME_DEBOUNCE_SECONDS):
        self.resume_debounce_seconds = resume_debounce_seconds
        self._auto_paused = False
        self._quiet_since = None

    @property
    def auto_paused(self):
        """True only while the CURRENT pause is one this controller itself triggered."""
        return self._auto_paused

    def reset(self):
        """Clears auto-pause tracking -- call when monitoring is turned off or playback
        is stopped/switched to a different file, so stale state can't cause a later
        spurious resume."""
        self._auto_paused = False
        self._quiet_since = None

    def evaluate(self, other_audio_active, is_playing, now=None):
        """Call once per poll tick. Returns "pause", "resume", or None.

        `is_playing` must reflect Talebrew's REAL, live player state (not anything this
        controller remembers) -- that's what lets a manual pause/resume from any UI path
        (main window, Mini Player, keyboard shortcut) be correctly distinguished from one
        this controller triggered itself, without those call sites needing to know this
        monitor exists.
        """
        now = time.monotonic() if now is None else now

        if other_audio_active:
            self._quiet_since = None
            if is_playing:
                self._auto_paused = True
                return "pause"
            return None

        if self._auto_paused:
            if self._quiet_since is None:
                self._quiet_since = now
                return None
            if now - self._quiet_since >= self.resume_debounce_seconds:
                self._auto_paused = False
                self._quiet_since = None
                return "resume"
        return None


def other_audio_is_active(own_pid, threshold=PEAK_THRESHOLD):
    """Polls every OTHER process's audio session for a non-trivial peak meter level.

    Returns False (never raises) on any failure -- pycaw missing, COM not available, a
    session that's gone away mid-enumeration -- since a monitoring glitch should never
    itself interrupt or block playback.
    """
    if not PYCAW_AVAILABLE:
        return False
    try:
        sessions = AudioUtilities.GetAllSessions()
    except Exception:
        return False

    for session in sessions:
        try:
            if session.ProcessId == own_pid:
                continue
            ctl = session._ctl
            if ctl is None:
                continue
            meter = ctl.QueryInterface(IAudioMeterInformation)
            if meter.GetPeakValue() >= threshold:
                return True
        except Exception:
            continue
    return False


class AutoPauseMonitor:
    """Wires AutoPauseController's decisions to the real AudioPlayer and a Tk polling
    loop. Owns no UI -- SettingsDrawer's toggle just calls set_enabled()."""

    def __init__(self, app, player, logger=None, poll_interval_ms=POLL_INTERVAL_MS):
        self.app = app
        self.player = player
        self.logger = logger
        self.poll_interval_ms = poll_interval_ms
        self.controller = AutoPauseController()
        self._own_pid = os.getpid()
        self._enabled = False
        self._polling = False

    def set_enabled(self, enabled):
        """Turns monitoring on/off -- called at startup from the saved setting, and live
        whenever the Settings drawer toggle changes."""
        self._enabled = bool(enabled)
        if not self._enabled:
            self.controller.reset()
        elif not self._polling:
            self._polling = True
            self.app.after(self.poll_interval_ms, self._tick)

    def notify_playback_changed(self):
        """Call whenever playback is explicitly stopped or switched to a different file
        (not paused by the auto-pause logic itself) -- without this, resetting the
        controller's own _auto_paused flag, a call/notification that started while file A
        was playing and ends only after the user has moved on to file B (stopped A,
        started B, maybe paused B manually) would force-resume B against the user's own
        explicit pause, since the controller still thinks it owns an unresolved
        auto-pause from A."""
        self.controller.reset()

    def _tick(self):
        if self._enabled:
            try:
                self._check_once()
            except Exception as e:
                if self.logger:
                    self.logger.add_event("warn", "Auto-pause check failed", str(e))
            self.app.after(self.poll_interval_ms, self._tick)
        else:
            self._polling = False

    def _check_once(self):
        other_active = other_audio_is_active(self._own_pid)
        is_playing = self.player.is_playing()
        action = self.controller.evaluate(other_active, is_playing)
        if action == "pause":
            self.player.pause()
            if self.logger:
                self.logger.add_event("info", "Playback auto-paused: other audio activity detected")
        elif action == "resume":
            self.player.resume()
            if self.logger:
                self.logger.add_event("info", "Playback auto-resumed: other audio activity stopped")
