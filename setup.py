"""Builds a Windows .msi installer for Talebrew.

Usage:
    poetry run python setup.py bdist_msi

The Piper TTS engine and voice models are NOT bundled here -- they're
downloaded on demand from Settings (see PiperEngine.py) to keep the
installer small. pyttsx3/SAPI works immediately after install with no
extra download.

Building the optional TalebrewMCP.exe (see msi_mcp_feature.py) needs the `mcp` Poetry
dependency group installed -- `poetry install --with mcp` -- the same one MCP_SETUP.md
already documents for running mcp_server.py from source. Without it, `import mcp` below
fails immediately with a clear error rather than a confusing cx_Freeze build failure.
"""

import json
import os

from cx_Freeze import Executable, setup

from msi_mcp_feature import (
    MCP_CONFIG_BASENAME,
    MCP_EXE_BASENAME,
    BdistMsiWithOptionalMcpFeature,
)
from version import __version__

try:
    import mcp  # noqa: F401  -- see the module docstring above.
except ImportError:
    raise SystemExit(
        "Building TalebrewMCP.exe needs the optional 'mcp' Poetry dependency group.\n"
        "Run: poetry install --with mcp"
    ) from None

# Matches bdist_msi_options["initial_target_dir"] below, which is also where the MSI
# actually lands on a default "click Next through the wizard" install. A user who picks a
# different install directory needs to hand-edit this path in the generated config file
# afterward -- cx_Freeze's bdist_msi has no custom-action hook here to fill in the
# *actual* chosen TARGETDIR at install time without a lot more machinery (a real custom
# action DLL/script), so this bakes in the common case instead of leaving a placeholder
# for every installer to hand-edit either way. See MCP_SETUP.md.
MCP_INSTALL_DIR = r"C:\Program Files\Talebrew"


def _write_generated_mcp_config() -> str:
    """Writes the exact `mcpServers` JSON snippet MCP_SETUP.md documents for Claude
    Desktop/Claude Code, pre-filled with TalebrewMCP.exe's real installed path, so
    checking the installer's "Install MCP Server support" box gets a user a ready-to-paste
    config file instead of a placeholder path to hunt down themselves. Written into the
    build tree (not source control) each time setup.py runs, same spirit as assets/*.bmp
    being generated rather than hand-maintained -- see scripts/generate_installer_art.py.
    """
    config = {
        "mcpServers": {
            "talebrew": {
                "command": os.path.join(MCP_INSTALL_DIR, MCP_EXE_BASENAME),
            }
        }
    }
    out_dir = os.path.join("build", "installer_generated")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, MCP_CONFIG_BASENAME)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(config, indent=2))
        f.write("\n")
    return out_path


build_exe_options = {
    # A single shared list -- cx_Freeze's `packages` is a build-wide (Freezer-level)
    # option, not a per-Executable one (checked directly against cx_Freeze's own source:
    # Executable() takes no packages/includes/excludes of its own; Freezer.packages is
    # one set shared by every Executable in the build). So Talebrew.exe and
    # TalebrewMCP.exe necessarily share one forced-include list and one output "lib"
    # folder in a single `bdist_msi` invocation -- there's no cx_Freeze option to force
    # sounddevice/numpy/soundfile into just Talebrew.exe's dependency closure and leave
    # them out of TalebrewMCP.exe's. What IS still true and independently verified below:
    # TalebrewMCP.exe's own script (mcp_server.py) and everything it imports
    # (Config/ConversionsLibrary/Converter/FileManager/TextExtraction/JobStore) never
    # references sounddevice/numpy/soundfile/AudioPlayer, so nothing in TalebrewMCP.exe's
    # own code ever loads them at runtime even though they're physically present in the
    # shared install directory. A genuinely separate, slimmer TalebrewMCP-only tree would
    # need two separate `build_exe`/`bdist_msi` invocations merged together after the
    # fact -- a bigger restructuring not undertaken here (see RELEASING.md).
    "packages": [
        "tkinter", "ttkbootstrap", "pypdf", "pyttsx3", "ebooklib", "bs4", "mobi", "loguru", "ftfy",
        "sounddevice", "numpy", "soundfile",
        # mcp_server.py's own dependencies -- mcp.server.fastmcp pulls all of these in
        # unconditionally at import time (verified by reading its own imports), even
        # though mcp_server.py only ever uses the default stdio transport.
        "mcp", "anyio", "httpx", "httpx_sse", "pydantic", "pydantic_core", "pydantic_settings",
        "starlette", "uvicorn", "sse_starlette", "jsonschema", "multipart",
    ],
    "excludes": ["test", "unittest"],
    "include_files": [
        ("assets", "assets"),
        (_write_generated_mcp_config(), MCP_CONFIG_BASENAME),
    ],
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
    # MSI in "Apps & features" / "Programs and Features" automatically. TalebrewMCP.exe
    # deliberately gets no shortcut of its own -- it's launched by an MCP client
    # (Claude Desktop/Code), never double-clicked by a person.
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
    # BdistMsiWithOptionalMcpFeature (msi_mcp_feature.py) is cx_Freeze's own bdist_msi
    # plus one optional MSI Feature ("MCP Server Support") wrapped around TalebrewMCP.exe
    # -- see that module's docstring for exactly what it adds and why a plain
    # bdist_msi_options dict can't express "optional" for just one Executable.
    cmdclass={"bdist_msi": BdistMsiWithOptionalMcpFeature},
    executables=[
        Executable(
            "main.py",
            base="Win32GUI",
            target_name="Talebrew.exe",
            shortcut_name="Talebrew",
            shortcut_dir="DesktopFolder",
            icon="assets/icon.ico",
        ),
        Executable(
            "mcp_server.py",
            # Console app, not Win32GUI -- it's an MCP stdio server, not a windowed app.
            target_name=MCP_EXE_BASENAME,
            icon="assets/icon.ico",
        ),
    ],
)
