# Python Text to Audio Converter

## About this Project
This is a desktop app that converts text, PDF, and ebook files to audio using offline text-to-speech. It started as a fork of [TiffinTech](https://github.com/TiffinTech)'s [python-pdf-audo](https://github.com/TiffinTech/python-pdf-audo) — a small, unlicensed example script — but has since been rewritten end to end (UI, conversion pipeline, TTS engine, packaging) and lives here as its own standalone, MIT-licensed project rather than a GitHub fork of that repository. See [LICENSE](LICENSE) for terms.

The main goals of this project are to:
- Create a Python program to convert text files to audio for use on any common platform.
- Design a simple, clean, and intuitive user interface.
- Demonstrate elements of clean and properly formatted code.
- Utilize Object-Oriented Programming (OOP) principles.

## System Requirements and Installation
### System Requirements
- Python 3.10 or higher
- Compatible with Windows, macOS, and Linux
- Dependencies:
  - `pyttsx3` for text-to-speech conversion
  - `PyPDF2` for PDF processing
  - `ttkbootstrap` for the UI theme

### Installation
1. Install Python 3.10 or higher from [https://www.python.org/downloads/](https://www.python.org/downloads/)
2. Install dependencies using pip:
```
pip install pyttsx3 PyPDF2 ttkbootstrap
```
3. Clone or download this repository:
```
git clone https://github.com/brando5393/python-text-to-audio-standalone.git
```
4. Navigate to the project directory
5. Run the program:
```
python main.py
```

## Usage
1. Launch the app with `python main.py`. The UI uses the `ttkbootstrap` "flatly" theme by default — change the `THEME` constant at the top of `main.py` (e.g. to `"darkly"`) for a dark UI.
2. Click **Add Files** and choose one or more `.txt` or `.pdf` files.
3. Optionally click **Change Download Folder** to pick where audio output goes.
4. Click **Convert to Audio** to generate an `.mp3` for each selected file, saved next to the source file.
5. Check the **Activity Log** panel (and `~/texttoaudiopy.log`) for conversion status and errors.

## For Developers
- To set up a development environment with Poetry:
  ```
  poetry install
  poetry run python main.py
  ```
- Contributions are welcome! Please fork this repository, make your changes, and submit a pull request.
- For any major changes, please open an issue first to discuss the proposed changes.

## Roadmap / Next Steps
- **Threaded conversion**: `convert_to_audio` currently blocks the UI thread while pyttsx3 renders audio; move it to a background thread (or `after()` polling) so the window stays responsive on large files.
- **Progress feedback**: add a progress bar or per-file status in the file list while a batch conversion runs.
- **Configurable voice/rate**: expose pyttsx3's voice and speech-rate options in the UI instead of hardcoding defaults.
- **Tests**: there's no automated test coverage yet; a few unit tests around `Converter` and `FileManager` (mocking `pyttsx3`/file dialogs) would catch regressions like the PyPDF2 API break that was fixed here.
- **Migrate PyPDF2 → pypdf**: PyPDF2 is now archived upstream in favor of `pypdf`; consider switching before PyPDF2 stops receiving updates.
- **Dark mode toggle**: expose the `darkly`/`flatly` theme switch as an in-app button instead of a code constant.
- **Repo hygiene**: enable Issues on the GitHub repo and turn on "delete branch on merge".

