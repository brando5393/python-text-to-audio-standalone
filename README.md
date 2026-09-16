<p align="center"><img src="assets/logo.png" width="140" alt="Talebrew logo"></p>

# Talebrew

*Every story, brewed aloud.*

A Windows desktop app that converts text, PDF, and ebook files into audio, using either
your system's built-in voice or a natural-sounding offline neural voice ([Piper](https://github.com/rhasspy/piper)).

## About this Project
This started as a fork of [TiffinTech](https://github.com/TiffinTech)'s [python-pdf-audo](https://github.com/TiffinTech/python-pdf-audo) — a small, unlicensed example script — but has since been rewritten end to end (UI, conversion pipeline, TTS engine, packaging) and lives here as its own standalone, MIT-licensed project rather than a GitHub fork of that repository. See [LICENSE](LICENSE) for terms.

## Features
- **Supported formats**: `.txt`, `.pdf`, `.epub`, and non-DRM `.mobi`/`.azw3`. DRM-locked Kindle store books can't be decrypted by this app (or legally by anyone without the device's Kindle key) — that's a hard limit, not a bug.
- **Two TTS engines**: your system's voice (SAPI, via `pyttsx3`) works immediately with no setup, or install [Piper](https://github.com/rhasspy/piper) from the Settings drawer for a much more natural-sounding offline neural voice, with several voices to choose from (Amy, Ryan, Lessac, Alan) — speed and expressiveness are tunable there too.
- **Settings drawer**: a docked side panel (not a popup) for voice/engine settings and app preferences (save location, light/dark appearance) — open it, change things, keep working.
- **Conversions library**: converted files are organized under a dedicated `Documents/TextToAudio/Conversions` folder, which you can freely split into your own subfolders (Books, Podcasts, etc.) from the app. A browsable panel shows that whole folder tree without leaving the app.
- **Built-in playback**: double-click any audio file in the Conversions Library to play it, with play/pause/stop controls, right in the app.
- **Progress dialog**: converting shows a per-file and overall progress bar with an estimated time remaining, plus a Cancel button — no more wondering whether a long book is still working or stuck.
- **Responsive and crash-resistant**: conversion runs on a background thread and in small chunks, each with its own timeout — a single stuck or corrupt section is skipped and logged instead of hanging the whole conversion (or the app) indefinitely.
- **Logging**: a rotating log file at `~/.texttoaudio/texttoaudio.log`, plus a live, color-coded Activity Log panel in the app.

## System Requirements
- Windows 10/11 (playback and the Piper engine use Windows-specific APIs; see [Platform notes](#platform-notes))
- Python 3.10 or higher (only needed if running from source — see [Installation](#installation))

## Installation

### Option A: Windows installer (recommended for most users)
Build a standalone `.msi` that bundles its own Python — no separate install needed:
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
   Or with plain pip: `pip install PyPDF2 pyttsx3 ttkbootstrap ebooklib beautifulsoup4 mobi` then `python main.py`.

## Usage
1. Launch the app. **Add Files** to queue `.txt`/`.pdf`/`.epub`/`.mobi`/`.azw3` files for conversion.
2. Click **Convert to Audio**. A progress dialog shows per-file and overall progress with an ETA; conversion runs in the background, so you can keep using the app while it works, and **Cancel Remaining** stops anything not yet converted.
3. Browse the **Conversions Library** panel for everything you've converted; double-click a file to play it with the **Playback** controls.
4. Open **Settings** (top right) for two tabs:
   - **Voice**: install the Piper engine, download a voice, pick the active one, and tune speed/expressiveness. Without Piper installed, conversion automatically falls back to your system voice.
   - **App**: change the save folder or create a new subfolder under Conversions, open it in File Explorer, and switch between light and dark appearance.

The UI uses a custom "coffee house" theme (espresso, caramel, honey-gold, with both a latte-cream light mode and a dark-roast dark mode) defined in `main.py`.

## Platform notes
This app targets **Windows**, and specifically was built and tested on **Windows on ARM64**, which has much thinner PyPI wheel coverage than x64 Windows. Two design decisions follow directly from that:
- **Playback** (`AudioPlayer.py`) uses Windows' built-in MCI API via `ctypes` rather than a package like `pygame`, which publishes no Windows-ARM64 wheel at all.
- **Piper** (`PiperEngine.py`) is driven as a subprocess against its self-contained Windows x64 binary (running under Windows 11's built-in x64 emulation on ARM64) rather than via the `piper-tts` pip package, whose native `piper-phonemize` dependency also has no win-arm64 wheel.
- **Audio output is WAV**, not MP3 — MP3 playback via MCI depends on Windows Media Player being installed, which it isn't by default on Windows 11.
- **Piper is slow on ARM64 for book-length text**: emulation costs the most on the heavy neural-net inference step, not just process startup. Measured on this machine: ~31 seconds per 3000-character chunk, so a full novel (roughly 700,000 characters) via Piper takes **on the order of 2 hours**. The system voice (`pyttsx3`/SAPI) runs natively and converts the same novel in **under 3 minutes**, just with a more robotic voice. Until there's a native (non-emulated) ARM64 path for Piper's ONNX inference, **use the system voice for full books and Piper for shorter documents** (articles, chapters, short stories) where the wait is seconds, not hours.

Porting to macOS/Linux would mean swapping `AudioPlayer.py` for a cross-platform library (e.g. `sounddevice`) and using Piper's Linux/macOS binaries directly (no emulation needed there, and full novels would convert in reasonable time even with Piper).

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
- Contributions are welcome! Fork this repository, make your changes, and submit a pull request. For any major changes, please open an issue first to discuss the proposed changes.

## Architecture
| Module | Responsibility |
|---|---|
| `main.py` | UI layout and wiring |
| `TextExtraction.py` | Pulls plain text out of txt/pdf/epub/mobi/azw3 |
| `Converter.py` | Runs conversion on a background thread, chunked (see `TextChunking.py`) and dispatched to the active TTS engine; per-chunk timeouts and a top-level crash guard keep one bad section (or an unexpected error) from hanging the whole batch |
| `TextChunking.py` | Splits long text into sentence-bounded chunks so long documents synthesize incrementally instead of in one long call |
| `ProgressDialog.py` | Per-file and overall progress bars with an ETA, fed by `Converter`'s event queue |
| `PiperEngine.py` | Installs/runs the Piper neural TTS engine |
| `Config.py` | Persists voice/engine settings to `~/.texttoaudio/config.json` |
| `SettingsDrawer.py` | Docked side panel for voice/engine tuning and app preferences (save folder, appearance) |
| `FileManager.py` | File picking, Conversions folder management |
| `ConversionsLibrary.py` | Treeview browser over the Conversions folder |
| `AudioPlayer.py` | Playback controls via Windows MCI |
| `LogManager.py` | Rotating file log + live on-screen log feed |

## Roadmap / Next Steps
- **Native ARM64 Piper inference**: replace the emulated `piper.exe` subprocess with a pure-Python pipeline — `onnxruntime` (which does publish a native win-arm64 wheel) running Piper's ONNX voice model directly, paired with a phonemizer that doesn't require `piper-phonemize`'s unavailable native extension. Would remove the ~2-hour-per-novel ceiling described in [Platform notes](#platform-notes) entirely, since the actual bottleneck is emulated ONNX inference, not process startup.
- **Cross-platform playback/TTS**: see [Platform notes](#platform-notes) — the Windows-specific pieces would need swapping out for macOS/Linux support.
- **Progress feedback**: `Converter` already emits a per-chunk progress event as a file converts; the UI doesn't surface it yet beyond periodic log lines — a progress bar next to the file in the list would be the natural next step.
- **Tests**: there's no automated test coverage yet.
- **Migrate PyPDF2 → pypdf**: PyPDF2 is archived upstream in favor of `pypdf`.
- **Bundle a default Piper voice** in the installer so natural speech works out of the box, trading a larger installer for zero post-install setup.
- **Repo hygiene**: consider archiving the old `python-text-to-audio` fork on GitHub now that this standalone repo is the active one.
