"""Builds a Windows .msi installer for the Text to Audio Converter.

Usage:
    poetry run python setup.py bdist_msi

The Piper TTS engine and voice models are NOT bundled here -- they're
downloaded on demand from Settings (see PiperEngine.py) to keep the
installer small. pyttsx3/SAPI works immediately after install with no
extra download.
"""

from cx_Freeze import Executable, setup

build_exe_options = {
    "packages": ["tkinter", "ttkbootstrap", "PyPDF2", "pyttsx3", "ebooklib", "bs4", "mobi", "loguru"],
    "excludes": ["test", "unittest"],
    "include_files": [],
}

bdist_msi_options = {
    "upgrade_code": "{9C7C6C1E-6B0D-4C7B-9E6F-2B1A9F0D5A11}",
    "add_to_path": False,
    "initial_target_dir": r"[ProgramFiles64Folder]\TextToAudioConverter",
}

setup(
    name="TextToAudioConverter",
    version="0.1.0",
    description="Converts text, PDF, and ebook files to audio using offline text-to-speech.",
    options={"build_exe": build_exe_options, "bdist_msi": bdist_msi_options},
    executables=[
        Executable(
            "main.py",
            base="Win32GUI",
            target_name="TextToAudioConverter.exe",
            shortcut_name="Text to Audio Converter",
            shortcut_dir="DesktopFolder",
        )
    ],
)
