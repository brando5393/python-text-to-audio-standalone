import json
import os

CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".texttoaudio", "config.json")

DEFAULTS = {
    "engine": "piper",  # "piper" (natural, offline) or "pyttsx3" (system voice, always available)
    "voice": "en_US-amy-medium",
    "speed": 1.0,  # 0.5 (slower) .. 2.0 (faster) -> mapped to Piper's length_scale
    "expressiveness": 0.667,  # Piper's noise_scale: lower = flatter/more consistent, higher = more varied
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
