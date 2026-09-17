import json
import os
import subprocess
import urllib.request
import zipfile

APP_DATA_DIR = os.path.join(os.path.expanduser("~"), ".texttoaudio")
ENGINE_DIR = os.path.join(APP_DATA_DIR, "engine", "piper")
VOICES_DIR = os.path.join(APP_DATA_DIR, "voices")
SAMPLES_DIR = os.path.join(APP_DATA_DIR, "voice_samples")
PIPER_EXE = os.path.join(ENGINE_DIR, "piper", "piper.exe")

# Piper's own project publishes a short pre-made sample clip per voice/quality tier, at a
# path mirroring CURATED_VOICES' own key structure minus the final "<voice_id>" segment
# (e.g. "en/en_US/ryan/high/en_US-ryan-high" -> ".../en/en_US/ryan/high/speaker_0.mp3").
# Each clip is small (well under 200KB), so a voice can be previewed without downloading
# its full 60-120MB model first -- useful for deciding which voice to even bother with.
SAMPLES_BASE = "https://raw.githubusercontent.com/rhasspy/piper-samples/master/samples"

PIPER_RELEASE_URL = "https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_windows_amd64.zip"

# A broad set of free voices from Piper's voice pack (https://github.com/rhasspy/piper,
# MIT-licensed), picking each speaker's best available quality tier. Runs under Windows'
# built-in x64 emulation on ARM64 -- Piper ships no native win-arm64 build, but the amd64
# build works fine through emulation.
CURATED_VOICES = {
    # English (US)
    "Amy (US, medium)": "en/en_US/amy/medium/en_US-amy-medium",
    "Lessac (US, high)": "en/en_US/lessac/high/en_US-lessac-high",
    "Ryan (US, high)": "en/en_US/ryan/high/en_US-ryan-high",
    "Joe (US, medium)": "en/en_US/joe/medium/en_US-joe-medium",
    "Kristin (US, medium)": "en/en_US/kristin/medium/en_US-kristin-medium",
    "Bryce (US, medium)": "en/en_US/bryce/medium/en_US-bryce-medium",
    "John (US, medium)": "en/en_US/john/medium/en_US-john-medium",
    "Norman (US, medium)": "en/en_US/norman/medium/en_US-norman-medium",
    "HFC Female (US, medium)": "en/en_US/hfc_female/medium/en_US-hfc_female-medium",
    "HFC Male (US, medium)": "en/en_US/hfc_male/medium/en_US-hfc_male-medium",
    "Sam (US, medium)": "en/en_US/sam/medium/en_US-sam-medium",
    "Danny (US, low)": "en/en_US/danny/low/en_US-danny-low",
    # English (UK)
    "Alan (UK, medium)": "en/en_GB/alan/medium/en_GB-alan-medium",
    "Alba (UK, medium)": "en/en_GB/alba/medium/en_GB-alba-medium",
    "Cori (UK, high)": "en/en_GB/cori/high/en_GB-cori-high",
    "Jenny (UK, medium)": "en/en_GB/jenny_dioco/medium/en_GB-jenny_dioco-medium",
    "Northern English Male (UK, medium)": "en/en_GB/northern_english_male/medium/en_GB-northern_english_male-medium",
    "Southern English Female (UK, low)": "en/en_GB/southern_english_female/low/en_GB-southern_english_female-low",
    # Other languages
    "Davefx (Spanish, medium)": "es/es_ES/davefx/medium/es_ES-davefx-medium",
    "Sharvard (Spanish, medium)": "es/es_ES/sharvard/medium/es_ES-sharvard-medium",
    "Siwis (French, medium)": "fr/fr_FR/siwis/medium/fr_FR-siwis-medium",
    "Tom (French, medium)": "fr/fr_FR/tom/medium/fr_FR-tom-medium",
    "Thorsten (German, high)": "de/de_DE/thorsten/high/de_DE-thorsten-high",
    "Kerstin (German, low)": "de/de_DE/kerstin/low/de_DE-kerstin-low",
    "Paola (Italian, medium)": "it/it_IT/paola/medium/it_IT-paola-medium",
    "Faber (Portuguese, medium)": "pt/pt_BR/faber/medium/pt_BR-faber-medium",
    "Ronnie (Dutch, medium)": "nl/nl_NL/ronnie/medium/nl_NL-ronnie-medium",
    "Irina (Russian, medium)": "ru/ru_RU/irina/medium/ru_RU-irina-medium",
    "Ruslan (Russian, medium)": "ru/ru_RU/ruslan/medium/ru_RU-ruslan-medium",
    "Huayan (Chinese, medium)": "zh/zh_CN/huayan/medium/zh_CN-huayan-medium",
}
HF_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main"

# Reverse lookup from a voice id (e.g. "en_US-ryan-high") back to its friendly display
# name (e.g. "Ryan (US, high)"), used by the Conversions Library to label files without
# showing users the raw model id.
FRIENDLY_NAMES = {os.path.basename(path): name for name, path in CURATED_VOICES.items()}


def is_engine_installed():
    return os.path.isfile(PIPER_EXE)


def install_engine(progress_cb=None):
    """Downloads and extracts the Piper CLI engine. `progress_cb(fraction)` is optional."""
    os.makedirs(ENGINE_DIR, exist_ok=True)
    zip_path = os.path.join(ENGINE_DIR, "piper.zip")
    _download(PIPER_RELEASE_URL, zip_path, progress_cb)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(ENGINE_DIR)
    os.remove(zip_path)
    if not is_engine_installed():
        raise RuntimeError("Piper engine extracted but piper.exe was not found where expected")


def list_installed_voices():
    if not os.path.isdir(VOICES_DIR):
        return []
    return sorted(f[:-5] for f in os.listdir(VOICES_DIR) if f.endswith(".onnx"))


def is_voice_installed(voice_id):
    return os.path.isfile(os.path.join(VOICES_DIR, voice_id + ".onnx"))


def voice_size_bytes(voice_id):
    total = 0
    for ext in (".onnx", ".onnx.json"):
        path = os.path.join(VOICES_DIR, voice_id + ext)
        if os.path.isfile(path):
            total += os.path.getsize(path)
    return total


def delete_voice(voice_id):
    """Removes a downloaded voice's model and config files, freeing the space they used."""
    for ext in (".onnx", ".onnx.json"):
        path = os.path.join(VOICES_DIR, voice_id + ext)
        if os.path.isfile(path):
            os.remove(path)


def download_voice(voice_key, progress_cb=None):
    """`voice_key` is one of CURATED_VOICES' values, e.g. 'en/en_US/amy/medium/en_US-amy-medium'."""
    os.makedirs(VOICES_DIR, exist_ok=True)
    voice_id = os.path.basename(voice_key)
    onnx_path = os.path.join(VOICES_DIR, voice_id + ".onnx")
    json_path = os.path.join(VOICES_DIR, voice_id + ".onnx.json")
    _download(f"{HF_BASE}/{voice_key}.onnx", onnx_path, progress_cb)
    _download(f"{HF_BASE}/{voice_key}.onnx.json", json_path, None)
    return voice_id


def sample_path_for(voice_key):
    """Returns the local cache path a voice's preview clip would live at, whether or
    not it's actually been downloaded yet."""
    voice_id = os.path.basename(voice_key)
    return os.path.join(SAMPLES_DIR, voice_id + ".mp3")


def is_sample_cached(voice_key):
    return os.path.isfile(sample_path_for(voice_key))


def download_sample(voice_key):
    """Downloads (and caches) a voice's small pre-made preview clip -- lets someone
    hear a voice before committing to downloading its full model. Returns the local
    path, downloading it first only if it isn't already cached."""
    dest_path = sample_path_for(voice_key)
    if os.path.isfile(dest_path):
        return dest_path
    os.makedirs(SAMPLES_DIR, exist_ok=True)
    sample_key = voice_key.rsplit("/", 1)[0] + "/speaker_0.mp3"
    _download(f"{SAMPLES_BASE}/{sample_key}", dest_path, None)
    return dest_path


def _download(url, dest_path, progress_cb):
    def _reporthook(block_num, block_size, total_size):
        if progress_cb and total_size > 0:
            progress_cb(min(1.0, (block_num * block_size) / total_size))

    tmp_path = dest_path + ".part"
    urllib.request.urlretrieve(url, tmp_path, _reporthook)
    os.replace(tmp_path, dest_path)


# Measured ~31s for a 3000-char chunk under x64 emulation on ARM64 -- generous multiplier
# so normal runs never hit this, while a genuinely stuck process still gets killed instead
# of blocking the worker thread (and everything queued behind it) forever.
MIN_TIMEOUT_SECONDS = 90
SECONDS_PER_CHAR = 0.25


def synthesize(text, voice_id, output_wav_path, length_scale=1.0, noise_scale=0.667, noise_w=0.8):
    """Synthesizes `text` to `output_wav_path` using an installed Piper voice.

    length_scale: speaking rate (1.0 normal, >1 slower, <1 faster).
    noise_scale / noise_w: Piper's naturalness/variation controls ("expressiveness").
    Raises TimeoutError if the process doesn't finish in a generous multiple of the
    time a chunk this size should reasonably take, instead of blocking forever.
    """
    model_path = os.path.join(VOICES_DIR, voice_id + ".onnx")
    if not is_engine_installed():
        raise RuntimeError("Piper engine is not installed yet (see Settings > Voice)")
    if not os.path.isfile(model_path):
        raise RuntimeError(f"Voice '{voice_id}' is not downloaded yet (see Settings > Voice)")

    command = [
        PIPER_EXE,
        "--model", model_path,
        "--output_file", output_wav_path,
        "--length_scale", str(length_scale),
        "--noise_scale", str(noise_scale),
        "--noise_w", str(noise_w),
    ]
    timeout = max(MIN_TIMEOUT_SECONDS, len(text) * SECONDS_PER_CHAR)
    try:
        result = subprocess.run(
            command, input=text, capture_output=True, text=True, encoding="utf-8",
            creationflags=subprocess.CREATE_NO_WINDOW, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"Piper did not finish this section within {int(timeout)}s -- treating it as stuck")
    if result.returncode != 0:
        raise RuntimeError(f"Piper failed (exit {result.returncode}): {result.stderr.strip()[:500]}")
