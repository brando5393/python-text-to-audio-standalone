import os
import sys

# Frozen (cx_Freeze) builds ship assets/ next to the exe; source runs ship it next to
# this file, so this is computed once here rather than duplicated in every window module.
APP_DIR = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
ICON_PATH = os.path.join(APP_DIR, "assets", "icon.ico")

APP_USER_MODEL_ID = "Talebrew.DesktopApp"


def claim_taskbar_identity():
    """Tells Windows this process is its own app, not just "python.exe".

    Without this, Windows groups the window under the Python interpreter's own taskbar
    entry and shows its generic icon there instead of ours, since window icons set via
    Tkinter only affect the title bar and Alt+Tab, not taskbar grouping. Must be called
    before the first window is created. Harmless no-op on non-Windows or if it fails --
    the app should never fail to start over a taskbar icon.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception:
        pass


def apply(window):
    """Sets the app icon on a Tk root or Toplevel window. Safe to call even if the
    icon file is missing or unreadable -- a missing icon should never block a window
    from opening."""
    try:
        window.iconbitmap(ICON_PATH)
    except Exception:
        pass
