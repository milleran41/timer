"""Keeps the timer in the Windows "topmost" band while it is on screen.

Qt puts WS_EX_TOPMOST on the window exactly once, when it is created, and
never looks at it again.  Every window in the topmost band is above every
non-topmost window, but inside the band the winner is whoever asked last -
and games, launchers and anti-cheat helpers routinely call
SetWindowPos(HWND_TOPMOST) on their own window while they start.  They are
then above the clock for the rest of the session, which is exactly the
reported symptom: the timer runs, the sound plays, but the window is hidden
behind the game.

This module re-asserts the topmost band instead of relying on the one-time
flag:
  * right after the window is shown,
  * as soon as another window becomes the foreground window
    (SetWinEventHook / EVENT_SYSTEM_FOREGROUND),
  * and once a second while the clock is visible, which also recovers from
    games that re-topmost themselves on focus loss or on a resolution change.

Every call uses SWP_NOMOVE|SWP_NOSIZE|SWP_NOACTIVATE|SWP_NOOWNERZORDER, so the
clock is never moved, resized or activated - a game keeps keyboard focus.

Limitation: none of this can paint over a game that renders in *exclusive*
fullscreen.  That mode bypasses the desktop compositor, so no separate
process can be composed above it without injecting code into the game
(which is what Steam/Discord/NVIDIA overlays do, and what anti-cheat
software is designed to stop).  Borderless / "fullscreen optimised" mode -
the default of most modern games - composites normally and works.
"""

import ctypes
import sys

from PyQt6.QtCore import QObject, QTimer

IS_WINDOWS = sys.platform == 'win32'

# ── Win32 constants ──────────────────────────────────────────────────────
GWL_EXSTYLE = -20
WS_EX_TOPMOST = 0x00000008
HWND_TOPMOST = -1

SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_NOOWNERZORDER = 0x0200
SWP_NOSENDCHANGING = 0x0400

EVENT_SYSTEM_FOREGROUND = 0x0003
WINEVENT_OUTOFCONTEXT = 0x0000
WINEVENT_SKIPOWNPROCESS = 0x0002

if IS_WINDOWS:
    from ctypes import wintypes

    _user32 = ctypes.WinDLL('user32', use_last_error=True)

    # GetWindowLongPtrW / SetWindowLongPtrW exist only in 64-bit user32;
    # the 32-bit builds have the plain Long variants.
    _get_long = getattr(_user32, 'GetWindowLongPtrW', _user32.GetWindowLongW)
    _set_long = getattr(_user32, 'SetWindowLongPtrW', _user32.SetWindowLongW)
    _get_long.argtypes = [wintypes.HWND, ctypes.c_int]
    _get_long.restype = ctypes.c_ssize_t
    _set_long.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
    _set_long.restype = ctypes.c_ssize_t

    _user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND,
                                     ctypes.c_int, ctypes.c_int,
                                     ctypes.c_int, ctypes.c_int,
                                     ctypes.c_uint]
    _user32.SetWindowPos.restype = wintypes.BOOL

    _user32.GetForegroundWindow.argtypes = []
    _user32.GetForegroundWindow.restype = wintypes.HWND

    _user32.IsWindow.argtypes = [wintypes.HWND]
    _user32.IsWindow.restype = wintypes.BOOL

    WINEVENTPROC = ctypes.WINFUNCTYPE(None, wintypes.HANDLE, wintypes.DWORD,
                                      wintypes.HWND, wintypes.LONG,
                                      wintypes.LONG, wintypes.DWORD,
                                      wintypes.DWORD)
    _user32.SetWinEventHook.argtypes = [wintypes.DWORD, wintypes.DWORD,
                                        wintypes.HMODULE, WINEVENTPROC,
                                        wintypes.DWORD, wintypes.DWORD,
                                        wintypes.DWORD]
    _user32.SetWinEventHook.restype = wintypes.HANDLE
    _user32.UnhookWinEvent.argtypes = [wintypes.HANDLE]
    _user32.UnhookWinEvent.restype = wintypes.BOOL


def _hwnd_value(hwnd):
    return int(hwnd or 0)


def _is_window(hwnd):
    """False once Windows has destroyed the handle (Qt recreates windows)."""
    if not IS_WINDOWS or not hwnd:
        return False
    return bool(_user32.IsWindow(hwnd))


def set_topmost(hwnd):
    """Puts the window into the topmost band without moving, resizing or
    activating it.  Safe to call repeatedly."""
    if not IS_WINDOWS or not hwnd:
        return False
    _set_long(hwnd, GWL_EXSTYLE, _get_long(hwnd, GWL_EXSTYLE) | WS_EX_TOPMOST)
    return bool(_user32.SetWindowPos(
        hwnd, HWND_TOPMOST, 0, 0, 0, 0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE |
        SWP_NOOWNERZORDER | SWP_NOSENDCHANGING))


def is_topmost(hwnd):
    """True if the window currently carries WS_EX_TOPMOST (used by tests)."""
    if not IS_WINDOWS or not hwnd:
        return False
    return bool(_get_long(hwnd, GWL_EXSTYLE) & WS_EX_TOPMOST)


def foreground_is_other(hwnd):
    """True if some other window is in the foreground right now."""
    if not IS_WINDOWS:
        return False
    fg = _hwnd_value(_user32.GetForegroundWindow())
    return fg != 0 and fg != _hwnd_value(hwnd)


class TopmostKeeper(QObject):
    """Keeps `window` in the topmost band for as long as it is visible.

    Call start() after the native window exists (from showEvent), and stop()
    when the app shuts down so the WinEvent hook is released.
    """

    def __init__(self, window, interval_ms=1000, parent=None):
        super().__init__(parent if parent is not None else window)
        self._window = window
        self._hwnd = 0
        self._hook = None
        self._proc = None
        self._pending = False
        self._stopped = False
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self.reassert)

    # ── lifecycle ──
    def start(self):
        if not IS_WINDOWS:
            return
        self._stopped = False
        self._refresh_hwnd()
        self.reassert()
        self._install_hook()
        if not self._timer.isActive():
            self._timer.start()

    def stop(self):
        """Releases the hook and the periodic check; nothing runs afterwards."""
        self._stopped = True
        self._pending = False
        self._timer.stop()
        self._remove_hook()
        self._hwnd = 0

    # ── internals ──
    def _install_hook(self):
        if self._hook or not self._hwnd:
            return

        def _on_foreground(_hook, _event, _hwnd, _obj, _child, _thread, _time):
            self._queue()

        # the callback must stay referenced, otherwise ctypes frees it
        self._proc = WINEVENTPROC(_on_foreground)
        self._hook = _user32.SetWinEventHook(
            EVENT_SYSTEM_FOREGROUND, EVENT_SYSTEM_FOREGROUND, None,
            self._proc, 0, 0,
            WINEVENT_OUTOFCONTEXT | WINEVENT_SKIPOWNPROCESS)
        if not self._hook:
            self._proc = None

    def _remove_hook(self):
        if self._hook:
            _user32.UnhookWinEvent(self._hook)
            self._hook = None
        self._proc = None

    def _queue(self):
        """One re-assert per event-loop turn: starting a game fires several
        foreground events in a row and only the last one matters."""
        if self._pending:
            return
        self._pending = True
        QTimer.singleShot(0, self._run_queued)

    def _run_queued(self):
        self._pending = False
        if self._stopped:
            return
        self.reassert()

    def _refresh_hwnd(self):
        """Qt may recreate the native window (style, DPI or screen change);
        the keeper would then hold a dead handle and raise nothing."""
        if _is_window(self._hwnd):
            return True
        if self._stopped or not self._window.isVisible():
            return False
        hwnd = _hwnd_value(self._window.winId())
        if not _is_window(hwnd):
            return False
        self._hwnd = hwnd
        return True

    def reassert(self):
        # Only the clock's own HWND is ever touched - no other window is
        # moved, raised or sent messages, so shell windows, UAC prompts and
        # the secure desktop are left alone.  When the secure desktop (UAC,
        # lock screen) is in front, GetForegroundWindow reports no foreign
        # window, so the foreground check below simply does nothing.
        if self._stopped or not IS_WINDOWS:
            return
        if not self._window.isVisible() or self._window.isMinimized():
            return
        if not self._refresh_hwnd():
            return
        if not foreground_is_other(self._hwnd):
            return
        set_topmost(self._hwnd)
