import json
import os

CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".texttoaudio", "config.json")

DEFAULTS = {
    "engine": "piper",  # "piper" (natural, offline) or "pyttsx3" (system voice, always available)
    "voice": "en_US-amy-medium",
    # Speed and Tone used to be synthesis-time settings baked into the WAV (requiring a
    # re-conversion to change). They're now live playback controls applied by
    # AudioPlayer -- see set_speed()/set_tone() -- and these two values just remember
    # the last-used slider positions across restarts, the same as any other preference.
    "playback_speed": 1.0,  # 0.5 (slower) .. 2.5 (faster), pitch-preserving
    "playback_tone": 0.0,  # -6 .. +6 semitones pitch shift, independent of speed
    "large_text": False,  # scales up UI text app-wide for readability
    "sound_effects_enabled": True,  # short audio cues for app ready/conversion done/error/exit
    "start_in_mini_mode": False,  # remembers whether the mini player was open at last exit
    "auto_pause_for_other_audio": False,  # pause playback automatically during calls/notifications
    # -- opt-in default, matching large_text: a behavior change some users won't want should
    # never turn itself on for someone who never asked for it.
}


def load():
    if not os.path.isfile(CONFIG_PATH):
        return dict(DEFAULTS)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        merged = dict(DEFAULTS)
        merged.update({k: v for k, v in data.items() if k in DEFAULTS})
        return merged
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULTS)


def save(settings):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump({k: settings[k] for k in DEFAULTS}, f, indent=2)
