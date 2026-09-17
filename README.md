<p align="center"><img src="assets/logo.png" width="140" alt="Talebrew logo"></p>

# Talebrew

[![Tests](https://github.com/brando5393/talebrew/actions/workflows/tests.yml/badge.svg)](https://github.com/brando5393/talebrew/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)

*Every story, brewed aloud.*

A Windows desktop app that converts text, PDF, and ebook files into audio, using either
your system's built-in voice or a natural-sounding offline neural voice ([Piper](https://github.com/rhasspy/piper)).

## About this Project
This started as a fork of [TiffinTech](https://github.com/TiffinTech)'s [python-pdf-audo](https://github.com/TiffinTech/python-pdf-audo), a small, unlicensed example script, but has since been rewritten end to end (UI, conversion pipeline, TTS engine, packaging) and lives here as its own standalone, MIT-licensed project rather than a GitHub fork of that repository. See [LICENSE](LICENSE) for terms.

**A note on Piper's license:** the Piper binary this app downloads is pinned to a specific release (`2023.11.14-2`) of the original [rhasspy/piper](https://github.com/rhasspy/piper), which remains MIT-licensed. That repository is now archived (no further updates), and active Piper development has since moved to a separate GPL-3.0-licensed fork ([OHF-Voice/piper1-gpl](https://github.com/OHF-Voice/piper1-gpl)) that this app does not use and has no plans to. If Piper's pinned release is ever upgraded to something from that fork, this note -- and the licensing implications of shipping a GPL binary alongside an MIT app -- would need revisiting first.

## Features
- **Supported formats**: `.txt`, `.md`, `.pdf`, `.epub`, non-DRM `.mobi`/`.azw3`, `.docx`, `.rtf`, and `.html`/`.htm`. DRM-locked Kindle store books can't be decrypted by this app, or legally by anyone without the device's Kindle key, so that's a hard limit rather than a bug.
- **Text sanitization before synthesis**: extracted text is cleaned up before it reaches the TTS engine, without touching the original file. Table-of-contents entries, page numbers, and repeated running headers/footers are dropped so they aren't read aloud, whether or not the source PDF preserved real line breaks around them -- some don't, extracting a table of contents or a page-number stamp as one continuous run of text with no delimiters at all, which needed its own handling separate from the line-based checks. Inline page-number stamps and a repeating watermark phrase glued directly onto surrounding words are also removed, without eating the real word that follows. Broken Unicode and ligatures from PDF extraction are repaired, and duplicated characters or words from extraction artifacts (like "stoooormy" or "the the") are collapsed. Words split across a PDF line wrap are rejoined, bracketed/superscript/glued footnote and citation markers are stripped, bullet-point glyphs are dropped while their text is kept, leftover literal HTML entities ("&amp;amp;") from web-sourced content are decoded, invisible zero-width characters and soft hyphens are removed, ASCII scene-break/divider lines ("* * *", "-----") are dropped, and stray Unicode replacement characters from an earlier unrecoverable decoding failure are closed up rather than read aloud as a glitch.
- **Two TTS engines, 30+ voices**: your system's voice (SAPI, via `pyttsx3`) works immediately with no setup, or install [Piper](https://github.com/rhasspy/piper) from the Settings drawer for a much more natural-sounding offline neural voice. Over 30 curated Piper voices are available to download individually, spanning English (US and UK, many speakers) plus Spanish, French, German, Italian, Portuguese, Dutch, Russian, and Chinese. **Preview any voice** with a short sample clip before downloading its full model, and voices you no longer want can be deleted from Settings to free up space. Speed and expressiveness sliders show a plain-language description next to the number (e.g. "1.20x (Slightly faster)", "0.50 (Flat, monotone)") instead of just a raw value.
- **Per-file voice selection**: each file queued in "Files to Convert" can use its own engine and voice, set before conversion starts, instead of only the one global choice in Settings -- pick a file, choose Piper/System voice (and which Piper voice), then apply it to just that file or to everything queued at once with one click. Files with their own override show in a different color from ones using the Settings default.
- **Pre-conversion estimate**: selecting a queued file shows its page/chapter count and a rough estimated conversion time for whichever voice is currently set for it, based on real measured throughput for each engine/voice tier. Once conversion actually starts, the progress dialog shows a live ETA recalculated continuously from that specific run's own observed speed, which is always more accurate than the pre-conversion guess.
- **Settings drawer**: a docked side panel (not a popup) with three tabs: Voice (engine/voice/tuning), App (save location, light/dark appearance, reset-to-defaults buttons), and Accessibility (larger text, sound cues, a written accessibility statement).
- **Conversions library**: converted files are organized under a dedicated `Documents/TextToAudio/Conversions` folder, which you can freely split into your own subfolders (Books, Podcasts, etc.) from the app. A browsable panel shows that whole folder tree without leaving the app, with Pages, Chapters, and Voice columns for each file. Pages comes from PDFs; chapters comes from EPUBs (and from a Word document's "Heading 1" paragraphs, as a best guess). For formats/documents with no real structural metadata to read (plain TXT, a DOCX with no heading styles, and so on), both columns fall back to a rough estimate from the text itself -- pages from character count, chapters from scanning for lines that look like chapter headings ("Chapter 3", "CHAPTER ONE", ...). If even that finds nothing, the column shows "Unknown" rather than a blank cell, so it's clear the app looked and genuinely couldn't tell, not that something's broken (also applies to an older file converted before this existed). **Re-convert with Current Voice** regenerates any past file using whichever voice is active now, no original document needed, since the text used to make it is kept alongside the audio.
- **Split into chapter files**: check "Split into chapter files" next to Convert to Audio to get one audio file per chapter instead of one file for the whole book -- for EPUB (each spine chapter), Word documents (split on "Heading 1" paragraphs, the same heuristic used for the Chapters column), and non-DRM MOBI/AZW3 that unpack to EPUB. Each chapter gets its own file (`Book Title - Chapter 01.wav`, `Book Title - Chapter 02.wav`, ...), its own resume checkpoint if interrupted, and shows as its own row in the Conversions Library. A file with no detectable chapter structure, or a format with no chapter concept at all (PDF, TXT, ...), converts as a single whole file automatically, exactly as if the box were unchecked.
- **Keyboard shortcuts**: `Ctrl+O` adds files, `Ctrl+Enter` starts conversion, `Delete` removes the selected queued file, `Ctrl+P` toggles play/pause, `Ctrl+,` toggles the Settings drawer, `Ctrl+Q` quits (with the usual confirmation), and `Enter` on a selected Conversions Library row plays it, the keyboard equivalent of double-clicking it.
- **Built-in playback**: double-click any audio file in the Conversions Library to play it, with play/pause/stop/start-over controls right in the app, plus a mini player mode (with its own seek bar and elapsed/remaining time) for keeping Talebrew out of the way while listening -- it remembers whether it was open across restarts. Playback position is remembered per file: reopening a file you were partway through offers to resume from there, and a file finished normally starts fresh next time either way.
- **Progress dialog**: converting shows a per-file and overall progress bar with an estimated time remaining, plus a Cancel button, so there's no wondering whether a long book is still working or stuck.
- **Responsive and crash-resistant**: conversion runs on a background thread and in small chunks, each with its own timeout, so a single stuck or corrupt section is skipped and logged instead of hanging the whole conversion (or the app) indefinitely. If the app closes or crashes mid-conversion, it automatically resumes from the last completed chunk next time it opens, rather than starting the whole file over.
- **Sound cues**: short tones for app-ready, conversion-done, error, and exit moments, useful when the window isn't in view; toggle them off in Settings if you'd rather not have them.
- **Confirmations where they matter**: changing the save folder confirms the exact destination before committing to it, and quitting asks first; reset buttons for save folder, voice settings, appearance, or everything at once are in Settings.
- **Logging**: a rotating log file at `~/.texttoaudio/texttoaudio.log`, plus a live, color-coded Activity Log panel in the app.
- **Cleans up after itself**: a conversion that definitively fails (as opposed to one interrupted by closing the app, which stays resumable) removes its own partial/scratch files rather than leaving orphaned clutter behind in the Conversions folder.
- **Auto error reporting** (developer builds only): an error opens a GitHub issue on this repo automatically, via the local `gh` CLI rather than a bundled credential, so it only does anything on a machine where the developer is already authenticated. Deduplicated so a recurring error only ever opens one issue.
- **Auto-updates**: checks this repo's GitHub Releases for a newer version on startup, with an in-app banner to download and install it.

## System Requirements
- Windows 10/11 (playback and the Piper engine use Windows-specific APIs; see [Platform notes](#platform-notes))
- Python 3.10 or higher (only needed if running from source; see [Installation](#installation))

## Installation

### Option A: Windows installer (recommended for most users)
Once a version has been tagged and released, a ready-to-run `.msi` installer is attached to that release on the [Releases page](https://github.com/brando5393/talebrew/releases) -- download it, run it, and it adds both a Desktop and a Start Menu shortcut. No separate Python install needed; the installer bundles its own. Already-installed copies also check for newer releases on startup and offer to update in-app (see [Auto-updates](#auto-updates)).

To build that same installer yourself instead of waiting for a release:
```
poetry install
poetry run python setup.py bdist_msi
```
The installer lands in `dist\Talebrew-<version>-win-arm64.msi` (or `-win-amd64` on an Intel/AMD machine). See [RELEASING.md](RELEASING.md) for the full packaging/release process, including how CI builds and publishes this file automatically on a tagged release.

### Option B: Run from source
1. Install Python 3.10+ from [python.org](https://www.python.org/downloads/)
2. Clone this repository:
   ```
   git clone https://github.com/brando5393/talebrew.git
   ```
3. Install dependencies with [Poetry](https://python-poetry.org/):
   ```
   poetry install
   poetry run python main.py
   ```
   Or with plain pip: `pip install pypdf pyttsx3 ttkbootstrap ebooklib beautifulsoup4 mobi python-docx striprtf packaging` then `python main.py`.

## Usage
1. Launch the app. **Add Files** to queue `.txt`/`.pdf`/`.epub`/`.mobi`/`.azw3` files for conversion.
2. Click **Convert to Audio**. A progress dialog shows per-file and overall progress with an ETA; conversion runs in the background, so you can keep using the app while it works, and **Cancel Remaining** stops anything not yet converted.
3. Browse the **Conversions Library** panel for everything you've converted; double-click a file to play it with the **Playback** controls. Each row shows which voice made it, and **Re-convert with Current Voice** regenerates it using whatever voice is active now.
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
  - **Running Piper chunks concurrently was tried and made things worse, not better.** The obvious lever for speeding up conversion -- synthesizing several chunks at once on a multi-core machine -- was implemented and measured directly: two independent timed runs (order reversed between them to rule out thermal throttling skewing the result) both showed 4 concurrent chunks taking *longer* than sequential, not less (441.8s vs 299.5s, then 449.4s vs 314.5s -- consistently about 30% slower). A separate measurement isolated Piper's own per-invocation overhead (model load + process startup) at well under a second, so that overhead isn't what dominates -- the ~31s/chunk cost is genuinely compute-bound inference. The most likely explanation is that onnxruntime already parallelizes a single chunk's inference across available cores internally, so running several Piper processes at once oversubscribes the same cores rather than adding real parallelism, made worse by x64-under-ARM64 emulation likely adding its own contention on top. Chunk synthesis stays sequential as a result (see `Converter.py`).

Given process-level parallelism is a dead end on this hardware, native ARM64 inference (below) is the only lever that would actually help without changing anything about the audio itself.
  - **Voice quality tier matters far more than any of the above, though.** The same 3000-character chunk took 82.2s with a "high" tier voice (`en_US-ryan-high`) versus 15.4s with a "low" tier voice (`en_US-danny-low`) -- about 5x faster, because a lower-tier model is a genuinely smaller/simpler neural network, not just a different codec setting. For long documents where speed matters more than how natural the voice sounds, picking a "low" tier voice from Settings is the single most effective way to speed up a Piper conversion on this hardware. The Settings drawer surfaces this tip next to the voice download list.

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
- Packaging and publishing a release (version bump, tag, what CI builds and attaches) is documented separately in [RELEASING.md](RELEASING.md).
- Contributions are welcome! Fork this repository, make your changes, and submit a pull request. For any major changes, please open an issue first to discuss the proposed changes. Please add or update tests and this README alongside any behavior change.

## Architecture
| Module | Responsibility |
|---|---|
| `main.py` | UI layout and wiring |
| `TextExtraction.py` | Pulls plain text out of txt/md/pdf/epub/mobi/azw3/docx/rtf/html, reads page/chapter counts for display (falling back to a text-based heuristic estimate when a format has no real structural metadata), and (for EPUB/DOCX/MOBI/AZW3) splits a document into per-chapter text for the "Split into chapter files" option |
| `TextSanitization.py` | Strips tables of contents/headers/footers, footnote/citation markers, HTML entities, invisible formatting characters, and scene-break divider lines, fixes broken Unicode, collapses repeated characters/words -- all before synthesis, never touching the original file |
| `Converter.py` | Runs conversion on a background thread, chunked (see `TextChunking.py`) and dispatched to the active TTS engine, optionally as one output file per chapter instead of one file per document. Per-chunk timeouts and a top-level crash guard keep one bad section, or an unexpected error, from hanging the whole batch |
| `TextChunking.py` | Splits long text into sentence-bounded chunks so long documents synthesize incrementally instead of in one long call |
| `ProgressDialog.py` | Per-file and overall progress bars with an ETA, fed by `Converter`'s event queue |
| `PiperEngine.py` | Installs/runs the Piper neural TTS engine, manages the curated voice catalog and voice preview samples |
| `AppUpdater.py` | Checks GitHub Releases for a newer version, verifies and launches the installer |
| `UpdateBanner.py` | The in-app banner that surfaces `AppUpdater` results and drives the download/install flow |
| `version.py` | Single source of truth for the app version (read by `setup.py` and `AppUpdater.py`) |
| `Config.py` | Persists voice/engine/appearance/accessibility settings to `~/.texttoaudio/config.json` |
| `SettingsDrawer.py` | Docked side panel: Voice, App, and Accessibility tabs |
| `MiniPlayer.py` | Compact always-on-top playback window, with its own seek bar and time display |
| `SoundEffects.py` | Plays short UI sound cues via their own MCI alias, separate from `AudioPlayer` |
| `FileManager.py` | File picking, Conversions folder management, per-file engine/voice overrides |
| `ConversionEstimate.py` | Rough pre-conversion time estimate shown for the selected queued file |
| `ConversionsLibrary.py` | Treeview browser over the Conversions folder |
| `ConversionQueue.py` | Remembers an in-progress batch so it can auto-resume if the app closes before it finishes |
| `AudioPlayer.py` | Playback controls via Windows MCI |
| `PlaybackMemory.py` | Remembers each file's last playback position, per file, so it can offer to resume |
| `LogManager.py` | Rotating file log and live on-screen log feed |
| `ErrorReporter.py` | Auto-files a deduplicated GitHub issue for each distinct error, via the local `gh` CLI |

## Roadmap / Next Steps
- **Native ARM64 Piper inference**: replace the emulated `piper.exe` subprocess with a pure-Python pipeline. `onnxruntime` (which does publish a native win-arm64 wheel) would run Piper's ONNX voice model directly, paired with a phonemizer that doesn't require `piper-phonemize`'s unavailable native extension. This would remove the roughly 2-hour-per-novel ceiling described in [Platform notes](#platform-notes) entirely, since the actual bottleneck is emulated ONNX inference, not process startup.
- **Cross-platform playback/TTS**: see [Platform notes](#platform-notes); the Windows-specific pieces would need swapping out for macOS/Linux support.
- **Bundle a default Piper voice** in the installer so natural speech works out of the box, trading a larger installer for zero post-install setup.
- **Repo hygiene**: consider archiving the old `python-text-to-audio` fork on GitHub now that this standalone repo is the active one.
