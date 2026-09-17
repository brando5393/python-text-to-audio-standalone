"""Windows hardware/keyboard media-key support (Play/Pause, Stop, Next, Previous),
so they control Talebrew even when it isn't the focused window.

Approach chosen -- RegisterHotKey() with the VK_MEDIA_* virtual key codes, not
WM_APPCOMMAND: WM_APPCOMMAND is only ever delivered to the currently *focused* window
(it rides along with normal input message routing), so it can't satisfy "works even
when the app isn't focused" by itself -- that's the whole point of this feature.
RegisterHotKey(), by contrast, is Windows' actual global-hotkey mechanism: once a
window registers a virtual key as a hotkey, Windows delivers WM_HOTKEY to it
regardless of which window currently has focus, which is exactly what's needed here.
The trade-off (documented in MediaKeyHook below) is that RegisterHotKey claims each
key system-wide for this process, so it can lose a specific key to another
already-running app that grabbed it first (e.g. Spotify) -- install() reports which
keys actually succeeded so the caller can log/ignore that gracefully instead of
crashing.

A first implementation subclassed Talebrew's own Tk window (SetWindowLongPtrW'ing a
Python ctypes callback in as its WNDPROC) to observe WM_HOTKEY directly. That let the
OS call back into a Python function asynchronously from inside Tcl's own message pump
-- and running it for real, against a live window, crashed the whole interpreter
within a couple of media-key presses with a fatal, uncatchable
"PyEval_RestoreThread: the function must be called with the GIL held ... but the GIL
is released" abort (verified directly, not hypothetical -- see the manual test in this
module's usage notes). That's the fundamental hazard of subclassing a live Tcl/Tk
window's WNDPROC with a foreign (Python) callback: Tcl's own internal window handling
does not expect another owner to intercept its message stream, and the two fight over
thread-state assumptions.

This module avoids that entirely by never letting the OS call into Python
asynchronously at all. It creates its own hidden, message-only window (a plain
DefWindowProcW window, entirely separate from Tk's), registers the hotkeys against
*that* window, and Talebrew polls it -- via PeekMessageW, called from ordinary Python
code on a Tk `app.after()` timer -- instead of being called back into. Slightly higher
latency (bounded by the poll interval) in exchange for never crashing the interpreter.

The low-level OS hook (the message-only window, RegisterHotKey, PeekMessageW) is
inherently not unit-testable -- it requires a real HWND and real OS message delivery.
What *is* directly unit-testable, and tested in tests/test_media_keys.py, is
resolve_command() and dispatch(): the pure mapping from "which hotkey id fired" /
"which command name" to "which existing playback action to call".
"""

import ctypes
from ctypes import wintypes

WM_HOTKEY = 0x0312
MOD_NOREPEAT = 0x4000
PM_REMOVE = 0x0001
HWND_MESSAGE = -3

VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_STOP = 0xB2
VK_MEDIA_PLAY_PAUSE = 0xB3

# Hotkey id -> (command name, virtual key code). Ids are arbitrary small integers
# scoped to this process/HWND, chosen by RegisterHotKey's caller (us), not by Windows.
_HOTKEYS = {
    1: ("play_pause", VK_MEDIA_PLAY_PAUSE),
    2: ("stop", VK_MEDIA_STOP),
    3: ("next", VK_MEDIA_NEXT_TRACK),
    4: ("previous", VK_MEDIA_PREV_TRACK),
}

_WNDPROC_T = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM)


class _WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", ctypes.c_uint),
        ("lpfnWndProc", _WNDPROC_T),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


class _MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", ctypes.c_uint),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt_x", ctypes.c_long),
        ("pt_y", ctypes.c_long),
    ]


_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32

_user32.DefWindowProcW.restype = ctypes.c_ssize_t
_user32.DefWindowProcW.argtypes = [wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM]
_user32.RegisterClassW.restype = wintypes.ATOM
_user32.RegisterClassW.argtypes = [ctypes.POINTER(_WNDCLASSW)]
_user32.UnregisterClassW.restype = wintypes.BOOL
_user32.UnregisterClassW.argtypes = [wintypes.LPCWSTR, wintypes.HINSTANCE]
_user32.CreateWindowExW.restype = wintypes.HWND
_user32.CreateWindowExW.argtypes = [
    wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HWND, wintypes.HANDLE, wintypes.HINSTANCE, wintypes.LPVOID,
]
_user32.DestroyWindow.restype = wintypes.BOOL
_user32.DestroyWindow.argtypes = [wintypes.HWND]
_user32.RegisterHotKey.restype = wintypes.BOOL
_user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_uint, ctypes.c_uint]
_user32.UnregisterHotKey.restype = wintypes.BOOL
_user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
_user32.PeekMessageW.restype = wintypes.BOOL
_user32.PeekMessageW.argtypes = [ctypes.POINTER(_MSG), wintypes.HWND, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint]

# A plain, real C function (DefWindowProcW itself) used as the message-only window's
# WNDPROC -- deliberately *not* a Python callback, so the OS never calls back into the
# interpreter asynchronously. See the module docstring for why that matters.
_DEF_WNDPROC = ctypes.cast(_user32.DefWindowProcW, _WNDPROC_T)


def resolve_command(hotkey_id):
    """Pure mapping: a WM_HOTKEY wParam (the hotkey id we registered it under) -> the
    media command name it represents, or None for an id this module never registered.
    Directly unit-testable without any OS hook."""
    entry = _HOTKEYS.get(hotkey_id)
    return entry[0] if entry else None


def dispatch(command, actions):
    """Pure mapping: a media command name -> the matching callable in `actions`
    (e.g. {"play_pause": toggle_pause, "stop": stop_playback, "next": play_next,
    "previous": play_previous}), invoked if present. Returns True if a matching action
    was found and called, False otherwise (unknown command, or this app doesn't wire
    one up for it)."""
    action = actions.get(command)
    if action is None:
        return False
    action()
    return True


class MediaKeyHook:
    """Owns a hidden, message-only window used only to receive WM_HOTKEY for the
    global multimedia keys. Nothing here is ever called by the OS -- `poll()` must be
    invoked periodically (main.py drives it via `app.after()`) and calls
    `on_command(command_name)` for whichever hotkeys fired since the last poll."""

    _class_name = "TalebrewMediaKeyHook"
    _class_registered = False

    def __init__(self, on_command):
        self._on_command = on_command
        self._hwnd = None
        self._registered_ids = set()
        self._hinstance = _kernel32.GetModuleHandleW(None)

    def install(self):
        """Creates the hidden window and registers whichever media keys aren't
        already claimed by another app. Returns the set of command names that were
        actually registered, so the caller can log which (if any) were unavailable
        rather than assuming all four always succeed."""
        if not MediaKeyHook._class_registered:
            wndclass = _WNDCLASSW()
            wndclass.style = 0
            wndclass.lpfnWndProc = _DEF_WNDPROC
            wndclass.cbClsExtra = 0
            wndclass.cbWndExtra = 0
            wndclass.hInstance = self._hinstance
            wndclass.hIcon = None
            wndclass.hCursor = None
            wndclass.hbrBackground = None
            wndclass.lpszMenuName = None
            wndclass.lpszClassName = self._class_name
            if not _user32.RegisterClassW(ctypes.byref(wndclass)):
                raise OSError("RegisterClassW failed for the media-key hook window")
            MediaKeyHook._class_registered = True

        self._hwnd = _user32.CreateWindowExW(
            0, self._class_name, "Talebrew Media Keys", 0, 0, 0, 0, 0,
            wintypes.HWND(HWND_MESSAGE), None, self._hinstance, None,
        )
        if not self._hwnd:
            raise OSError("CreateWindowExW failed for the media-key hook window")

        registered_commands = set()
        for hotkey_id, (command, vk) in _HOTKEYS.items():
            if _user32.RegisterHotKey(self._hwnd, hotkey_id, MOD_NOREPEAT, vk):
                self._registered_ids.add(hotkey_id)
                registered_commands.add(command)
        return registered_commands

    def poll(self):
        """Drains any WM_HOTKEY messages queued since the last poll and dispatches
        each to `on_command`. Safe to call repeatedly (e.g. every 150ms from
        `app.after()`) -- a no-op when nothing fired."""
        if self._hwnd is None:
            return
        msg = _MSG()
        while _user32.PeekMessageW(ctypes.byref(msg), self._hwnd, WM_HOTKEY, WM_HOTKEY, PM_REMOVE):
            command = resolve_command(msg.wParam)
            if command is not None:
                try:
                    self._on_command(command)
                except Exception:
                    pass  # a broken handler must never take down the polling loop

    def uninstall(self):
        for hotkey_id in self._registered_ids:
            _user32.UnregisterHotKey(self._hwnd, hotkey_id)
        self._registered_ids.clear()
        if self._hwnd is not None:
            _user32.DestroyWindow(self._hwnd)
            self._hwnd = None
