"""Builds a Windows .msi installer for Talebrew.

Usage:
    poetry run python setup.py bdist_msi

The Piper TTS engine and voice models are NOT bundled here -- they're
downloaded on demand from Settings (see PiperEngine.py) to keep the
installer small. pyttsx3/SAPI works immediately after install with no
extra download.
"""

from cx_Freeze import Executable, setup

from version import __version__

build_exe_options = {
    "packages": [
        "tkinter", "ttkbootstrap", "pypdf", "pyttsx3", "ebooklib", "bs4", "mobi", "loguru", "ftfy",
        "sounddevice", "numpy", "soundfile",
    ],
    "excludes": ["test", "unittest"],
    "include_files": [("assets", "assets")],
}

bdist_msi_options = {
    "upgrade_code": "{9C7C6C1E-6B0D-4C7B-9E6F-2B1A9F0D5A11}",
    "add_to_path": False,
    "initial_target_dir": r"[ProgramFiles64Folder]\Talebrew",
    # Talebrew's icon in Windows' "Apps & features" / "Programs and Features" list,
    # instead of the generic default MSI package icon.
    "install_icon": "assets/icon.ico",
    # The Executable below already gets a Desktop shortcut (shortcut_dir="DesktopFolder");
    # this adds a second one under the Start Menu, which is where most people actually look
    # for a newly-installed app. "ProgramMenuFolder" is a predefined Windows Installer
    # directory id, so it doesn't need a matching row in the Directory table. The
    # uninstaller itself needs no shortcut of its own -- Windows Installer registers every
    # MSI in "Apps & features" / "Programs and Features" automatically.
    "data": {
        "Shortcut": [
            (
                "S_STARTMENU", "ProgramMenuFolder", "Talebrew", "TARGETDIR",
                "[TARGETDIR]Talebrew.exe", None, None, None, None, None, None, "TARGETDIR",
            ),
        ],
    },
}

setup(
    name="Talebrew",
    version=__version__,
    description="A proper Windows app that turns your heaviest reading into a flawless listening experience.",
    options={"build_exe": build_exe_options, "bdist_msi": bdist_msi_options},
    executables=[
        Executable(
            "main.py",
            base="Win32GUI",
            target_name="Talebrew.exe",
            shortcut_name="Talebrew",
            shortcut_dir="DesktopFolder",
            icon="assets/icon.ico",
        )
    ],
)
