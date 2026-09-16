<p align="center"><img src="assets/logo.png" width="140" alt="Talebrew logo"></p>

# Talebrew

[![Tests](https://github.com/brando5393/python-text-to-audio-standalone/actions/workflows/tests.yml/badge.svg)](https://github.com/brando5393/python-text-to-audio-standalone/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)

*Every story, brewed aloud.*

A Windows desktop app that converts text, PDF, and ebook files into audio, using either
your system's built-in voice or a natural-sounding offline neural voice ([Piper](https://github.com/rhasspy/piper)).

## About this Project
This started as a fork of [TiffinTech](https://github.com/TiffinTech)'s [python-pdf-audo](https://github.com/TiffinTech/python-pdf-audo), a small, unlicensed example script, but has since been rewritten end to end (UI, conversion pipeline, TTS engine, packaging) and lives here as its own standalone, MIT-licensed project rather than a GitHub fork of that repository. See [LICENSE](LICENSE) for terms.

## Features
- **Supported formats**: `.txt`, `.md`, `.pdf`, `.epub`, non-DRM `.mobi`/`.azw3`, `.docx`, `.rtf`, and `.html`/`.htm`. DRM-locked Kindle store books can't be decrypted by this app, or legally by anyone without the device's Kindle key, so that's a hard limit rather than a bug.
- **Two TTS engines, 30+ voices**: your system's voice (SAPI, via `pyttsx3`) works immediately with no setup, or install [Piper](https://github.com/rhasspy/piper) from the Settings drawer for a much more natural-sounding offline neural voice. Over 30 curated Piper voices are available to download individually, spanning English (US and UK, many speakers) plus Spanish, French, German, Italian, Portuguese, Dutch, Russian, and Chinese. Speed and expressiveness are tunable too, and voices you no longer want can be deleted from Settings to free up space.
- **Settings drawer**: a docked side panel (not a popup) with three tabs: Voice (engine/voice/tuning), App (save location, light/dark appearance, reset-to-defaults buttons), and Accessibility (larger text, sound cues, a written accessibility statement).
- **Conversions library**: converted files are organized under a dedicated `Documents/TextToAudio/Conversions` folder, which you can freely split into your own subfolders (Books, Podcasts, etc.) from the app. A browsable panel shows that whole folder tree without leaving the app.
- **Built-in playback**: double-click any audio file in the Conversions Library to play it, with play/pause/stop controls right in the app, plus a mini player mode for keeping Talebrew out of the way while listening (remembers whether it was open across restarts).
- **Progress dialog**: converting shows a per-file and overall progress bar with an estimated time remaining, plus a Cancel button, so there's no wondering whether a long book is still working or stuck.
- **Responsive and crash-resistant**: conversion runs on a background thread and in small chunks, each with its own timeout, so a single stuck or corrupt section is skipped and logged instead of hanging the whole conversion (or the app) indefinitely.
- **Sound cues**: short tones for app-ready, conversion-done, error, and exit moments, useful when the window isn't in view; toggle them off in Settings if you'd rather not have them.
- **Confirmations where they matter**: changing the save folder confirms the exact destination before committing to it, and quitting asks first; reset buttons for save folder, voice settings, appearance, or everything at once are in Settings.
- **Logging**: a rotating log file at `~/.texttoaudio/texttoaudio.log`, plus a live, color-coded Activity Log panel in the app.
- **Auto-updates**: checks this repo's GitHub Releases for a newer version on startup, with an in-app banner to download and install it.

## System Requirements
- Windows 10/11 (playback and the Piper engine use Windows-specific APIs; see [Platform notes](#platform-notes))
- Python 3.10 or higher (only needed if running from source; see [Installation](#installation))

## Installation

### Option A: Windows installer (recommended for most users)
Build a standalone `.msi` that bundles its own Python, so no separate install is needed:
```
poetry install
poetry run python setup.py bdist_msi
```
The installer lands in `dist\Talebrew-<version>-win-arm64.msi` (or `-win-amd64` on an Intel/AMD machine). Run it to install; it adds a desktop shortcut.

### Option B: Run from source
1. Install Python 3.10+ from [python.org](https://www.python.org/downloads/)
2. Clone this repository:
   ```
   git clone https://github.com/brando5393/python-text-to-audio-standalone.git
   ```
3. Install dependencies with [Poetry](https://python-poetry.org/):
   ```
   poetry install
   poetry run python main.py
   ```
   Or with plain pip: `pip install PyPDF2 pyttsx3 ttkbootstrap ebooklib beautifulsoup4 mobi python-docx striprtf packaging` then `python main.py`.

## Usage
1. Launch the app. **Add Files** to queue `.txt`/`.pdf`/`.epub`/`.mobi`/`.azw3` files for conversion.
2. Click **Convert to Audio**. A progress dialog shows per-file and overall progress with an ETA; conversion runs in the background, so you can keep using the app while it works, and **Cancel Remaining** stops anything not yet converted.
3. Browse the **Conversions Library** panel for everything you've converted; double-click a file to play it with the **Playback** controls.
4. Open **Settings** (top right) for three tabs:
   - **Voice**: install the Piper engine, download a voice, pick the active one, and tune speed/expressiveness. Without Piper installed, conversion automatically falls back to your system voice.
   - **App**: change the save folder or create a new subfolder under Conversions, open it in File Explorer, switch between light and dark appearance, or reset any of these back to defaults.
   - **Accessibility**: a larger-text toggle, a sound cues toggle, and a written statement of what's actually been verified.

The UI uses a custom "coffee house" theme (espresso, caramel, honey-gold, with both a latte-cream light mode and a dark-roast dark mode), a subtle paper-grain background with a faint watermark of the app icon, and Palatino Linotype for headers. All defined in `main.py` and generated by the scripts under `scripts/`.

## Platform notes
This app targets **Windows**, and specifically was built and tested on **Windows on ARM64**, which has much thinner PyPI wheel coverage than x64 Windows. Two design decisions follow directly from that:
- **Playback** (`AudioPlayer.py`) uses Windows' built-in MCI API via `ctypes` rather than a package like `pygame`, which publishes no Windows-ARM64 wheel at all.
- **Piper** (`PiperEngine.py`) is driven as a subprocess against its self-contained Windows x64 binary (running under Windows 11's built-in x64 emulation on ARM64) rather than via the `piper-tts` pip package, whose native `piper-phonemize` dependency also has no win-arm64 wheel.
- **Audio output is WAV**, not MP3. MP3 playback via MCI depends on Windows Media Player being installed, which it isn't by default on Windows 11.
- **Piper is slow on ARM64 for book-length text**, since emulation costs the most on the heavy neural-net inference step, not just process startup. Measured on this machine: about 31 seconds per 3000-character chunk, so a full novel (roughly 700,000 characters) via Piper takes on the order of 2 hours. The system voice (`pyttsx3`/SAPI) runs natively and converts the same novel in under 3 minutes, just with a more robotic voice. Until there's a native, non-emulated ARM64 path for Piper's ONNX inference, use the system voice for full books and Piper for shorter documents (articles, chapters, short stories), where the wait is seconds, not hours.

Porting to macOS/Linux would mean swapping `AudioPlayer.py` for a cross-platform library (e.g. `sounddevice`) and using Piper's Linux/macOS binaries directly (no emulation needed there, and full novels would convert in reasonable time even with Piper).

## Auto-updates
`AppUpdater.py` checks this repo's GitHub Releases for a newer `.msi` on startup; if one exists, an in-app banner offers to download and launch it. It is not a fully silent updater: installing still touches Program Files, so Windows still shows one UAC prompt, the same as the original install. Avoiding that would need a background service running as a privileged user, a much bigger tradeoff than an occasional prompt. A downloaded installer is verified against the SHA-256 checksum GitHub computes for the release asset itself before it's ever run, so a corrupted or tampered-with download is rejected rather than launched. This isn't a substitute for code signing (the binaries aren't signed), only a guarantee that the bytes on disk match what GitHub actually served. Network failures (offline, GitHub down, no releases published yet) fail silently, since a background version check should never interrupt using the app.

## For Developers
- Set up a development environment:
  ```
  poetry install
  poetry run python main.py
  ```
- Regenerate the app icon after changing `scripts/generate_icon.py`:
  ```
  poetry run python scripts/generate_icon.py
  ```
- Run the test suite:
  ```
  poetry run pytest tests/ -v
  ```
  CI (`.github/workflows/tests.yml`) runs the same suite on Windows against Python 3.10 and 3.12 on every push/PR to `main`.
- Contributions are welcome! Fork this repository, make your changes, and submit a pull request. For any major changes, please open an issue first to discuss the proposed changes. Please add or update tests and this README alongside any behavior change.

## Architecture
| Module | Responsibility |
|---|---|
| `main.py` | UI layout and wiring |
| `TextExtraction.py` | Pulls plain text out of txt/md/pdf/epub/mobi/azw3/docx/rtf/html |
| `Converter.py` | Runs conversion on a background thread, chunked (see `TextChunking.py`) and dispatched to the active TTS engine. Per-chunk timeouts and a top-level crash guard keep one bad section, or an unexpected error, from hanging the whole batch |
| `TextChunking.py` | Splits long text into sentence-bounded chunks so long documents synthesize incrementally instead of in one long call |
| `ProgressDialog.py` | Per-file and overall progress bars with an ETA, fed by `Converter`'s event queue |
| `PiperEngine.py` | Installs/runs the Piper neural TTS engine, manages the curated voice catalog |
| `AppUpdater.py` | Checks GitHub Releases for a newer version, verifies and launches the installer |
| `UpdateBanner.py` | The in-app banner that surfaces `AppUpdater` results and drives the download/install flow |
| `version.py` | Single source of truth for the app version (read by `setup.py` and `AppUpdater.py`) |
| `Config.py` | Persists voice/engine/appearance/accessibility settings to `~/.texttoaudio/config.json` |
| `SettingsDrawer.py` | Docked side panel: Voice, App, and Accessibility tabs |
| `MiniPlayer.py` | Compact always-on-top playback window |
| `SoundEffects.py` | Plays short UI sound cues via their own MCI alias, separate from `AudioPlayer` |
| `FileManager.py` | File picking, Conversions folder management |
| `ConversionsLibrary.py` | Treeview browser over the Conversions folder |
| `AudioPlayer.py` | Playback controls via Windows MCI |
| `LogManager.py` | Rotating file log and live on-screen log feed |

## Roadmap / Next Steps
- **Native ARM64 Piper inference**: replace the emulated `piper.exe` subprocess with a pure-Python pipeline. `onnxruntime` (which does publish a native win-arm64 wheel) would run Piper's ONNX voice model directly, paired with a phonemizer that doesn't require `piper-phonemize`'s unavailable native extension. This would remove the roughly 2-hour-per-novel ceiling described in [Platform notes](#platform-notes) entirely, since the actual bottleneck is emulated ONNX inference, not process startup.
- **Cross-platform playback/TTS**: see [Platform notes](#platform-notes); the Windows-specific pieces would need swapping out for macOS/Linux support.
- **Migrate PyPDF2 to pypdf**: PyPDF2 is archived upstream in favor of `pypdf`.
- **Bundle a default Piper voice** in the installer so natural speech works out of the box, trading a larger installer for zero post-install setup.
- **Repo hygiene**: consider archiving the old `python-text-to-audio` fork on GitHub now that this standalone repo is the active one.
