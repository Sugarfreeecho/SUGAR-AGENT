"""Full-screen black overlay built directly on Win32 (no PowerShell, no WinForms).

The PowerShell/WinForms version needed ~4.4 s before the first pixel appeared,
because ``powershell.exe`` alone costs ~3.5 s to start on this machine. This
module creates the window inside the already-running daemon instead, so the
screen goes black in well under a second.

Public surface:

    window = ShieldWindow()
    window.show()                     # covers the virtual screen
    while window.pump(0.03): ...      # False once the user dismissed it
    window.close()

Dismissal: any key press, mouse click, or a mouse move of more than 60 px.
"""

from __future__ import annotations

import ctypes
import time
from ctypes import wintypes
from typing import Optional

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WM_DESTROY = 0x0002
WM_PAINT = 0x000F
WM_SETCURSOR = 0x0020
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_RBUTTONDOWN = 0x0204
WM_MBUTTONDOWN = 0x0207
WM_DISPLAYCHANGE = 0x007E

WS_POPUP = 0x80000000
WS_VISIBLE = 0x10000000
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080

SW_SHOW = 5
SW_HIDE = 0

SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

BLACK_BRUSH = 4
TRANSPARENT = 1
DT_CENTER = 0x0001
DT_VCENTER = 0x0004
DT_WORDBREAK = 0x0010

MOVE_THRESHOLD_PX = 60
HINT_SECONDS = 6.0

WNDPROC = ctypes.WINFUNCTYPE(
    ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


class PAINTSTRUCT(ctypes.Structure):
    _fields_ = [
        ("hdc", wintypes.HDC),
        ("fErase", wintypes.BOOL),
        ("rcPaint", wintypes.RECT),
        ("fRestore", wintypes.BOOL),
        ("fIncUpdate", wintypes.BOOL),
        ("rgbReserved", ctypes.c_byte * 32),
    ]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", wintypes.POINT),
    ]


def _declare_prototypes() -> None:
    """64-bit safety: handles are pointers, not ints, and LPARAM can exceed 32 bits."""

    user32.DefWindowProcW.argtypes = [
        wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
    ]
    user32.DefWindowProcW.restype = ctypes.c_ssize_t
    user32.CreateWindowExW.restype = wintypes.HWND
    user32.CreateWindowExW.argtypes = [
        wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID,
    ]
    user32.RegisterClassW.restype = wintypes.ATOM
    user32.BeginPaint.argtypes = [wintypes.HWND, ctypes.POINTER(PAINTSTRUCT)]
    user32.BeginPaint.restype = wintypes.HDC
    user32.EndPaint.argtypes = [wintypes.HWND, ctypes.POINTER(PAINTSTRUCT)]
    user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.PeekMessageW.argtypes = [
        ctypes.POINTER(MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT,
    ]
    user32.SetWindowPos.argtypes = [
        wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
        ctypes.c_int, ctypes.c_int, wintypes.UINT,
    ]
    user32.DrawTextW.argtypes = [
        wintypes.HDC, wintypes.LPCWSTR, ctypes.c_int,
        ctypes.POINTER(wintypes.RECT), wintypes.UINT,
    ]
    user32.LoadCursorW.restype = wintypes.HANDLE
    user32.SetCursor.argtypes = [wintypes.HANDLE]
    gdi32.CreateFontW.restype = wintypes.HANDLE
    gdi32.CreateFontW.argtypes = [
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
        wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.LPCWSTR,
    ]
    gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HANDLE]
    gdi32.SelectObject.restype = wintypes.HANDLE
    gdi32.DeleteObject.argtypes = [wintypes.HANDLE]
    gdi32.GetStockObject.restype = wintypes.HANDLE
    gdi32.SetTextColor.argtypes = [wintypes.HDC, wintypes.DWORD]
    gdi32.SetBkMode.argtypes = [wintypes.HDC, ctypes.c_int]
    kernel32.GetModuleHandleW.restype = wintypes.HMODULE


_declare_prototypes()


def _make_dpi_aware() -> None:
    try:
        # PER_MONITOR_AWARE_V2 keeps GetSystemMetrics in physical pixels.
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        return
    except Exception:
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass


def _virtual_screen() -> tuple[int, int, int, int]:
    return (
        user32.GetSystemMetrics(SM_XVIRTUALSCREEN),
        user32.GetSystemMetrics(SM_YVIRTUALSCREEN),
        user32.GetSystemMetrics(SM_CXVIRTUALSCREEN),
        user32.GetSystemMetrics(SM_CYVIRTUALSCREEN),
    )


class ShieldWindow:
    """One borderless black window spanning every monitor."""

    _class_registered = False

    def __init__(self, *, hint_text: str = "护屏模式\n按任意键或移动鼠标退出") -> None:
        _make_dpi_aware()
        self.hwnd: Optional[int] = None
        self._dismissed = False
        self._hint = hint_text
        self._hint_until = 0.0
        self._origin = (0, 0)
        self._proc = WNDPROC(self._wndproc)
        self._class_name = "SugarAgentShieldWindow"
        self._register_class()

    # -- window plumbing -------------------------------------------------
    def _register_class(self) -> None:
        if ShieldWindow._class_registered:
            return
        wc = WNDCLASSW()
        wc.style = 0
        wc.lpfnWndProc = self._proc
        wc.cbClsExtra = 0
        wc.cbWndExtra = 0
        wc.hInstance = kernel32.GetModuleHandleW(None)
        wc.hIcon = None
        wc.hCursor = None
        wc.hbrBackground = gdi32.GetStockObject(BLACK_BRUSH)
        wc.lpszMenuName = None
        wc.lpszClassName = self._class_name
        if not user32.RegisterClassW(ctypes.byref(wc)):
            err = ctypes.get_last_error()
            if err not in (0, 1410):  # 1410 = class already exists
                raise OSError(err, "RegisterClassW failed")
        ShieldWindow._class_registered = True

    def _wndproc(self, hwnd, msg, wparam, lparam):
        if msg == WM_PAINT:
            self._paint(hwnd)
            return 0
        if msg == WM_SETCURSOR:
            user32.SetCursor(None)
            return 1
        if msg in (WM_KEYDOWN, WM_SYSKEYDOWN):
            self._dismissed = True
            return 0
        if msg in (WM_LBUTTONDOWN, WM_RBUTTONDOWN, WM_MBUTTONDOWN):
            self._dismissed = True
            return 0
        if msg == WM_MOUSEMOVE:
            x = ctypes.c_short(lparam & 0xFFFF).value
            y = ctypes.c_short((lparam >> 16) & 0xFFFF).value
            if abs(x - self._origin[0]) > MOVE_THRESHOLD_PX or abs(y - self._origin[1]) > MOVE_THRESHOLD_PX:
                self._dismissed = True
            return 0
        if msg == WM_DISPLAYCHANGE:
            self._layout()
            return 0
        if msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _paint(self, hwnd) -> None:
        ps = PAINTSTRUCT()
        hdc = user32.BeginPaint(hwnd, ctypes.byref(ps))
        try:
            if time.monotonic() < self._hint_until and self._hint:
                rect = wintypes.RECT()
                user32.GetClientRect(hwnd, ctypes.byref(rect))
                font = gdi32.CreateFontW(
                    34, 0, 0, 0, 400, 0, 0, 0, 134, 0, 0, 0, 0, "Microsoft YaHei UI"
                )
                old = gdi32.SelectObject(hdc, font)
                gdi32.SetTextColor(hdc, 0x00555555)  # COLORREF is BGR
                gdi32.SetBkMode(hdc, TRANSPARENT)
                text = ctypes.c_wchar_p(self._hint)
                user32.DrawTextW(hdc, text, -1, ctypes.byref(rect), DT_CENTER | DT_VCENTER | DT_WORDBREAK)
                gdi32.SelectObject(hdc, old)
                gdi32.DeleteObject(font)
        finally:
            user32.EndPaint(hwnd, ctypes.byref(ps))

    def _layout(self) -> None:
        if not self.hwnd:
            return
        x, y, width, height = _virtual_screen()
        user32.SetWindowPos(self.hwnd, -1, x, y, width, height, 0x0040)  # SWP_SHOWWINDOW

    # -- public API ------------------------------------------------------
    def show(self) -> None:
        if self.hwnd:
            return
        x, y, width, height = _virtual_screen()
        self.hwnd = user32.CreateWindowExW(
            WS_EX_TOPMOST | WS_EX_TOOLWINDOW,
            self._class_name,
            "",
            WS_POPUP | WS_VISIBLE,
            x,
            y,
            width,
            height,
            None,
            None,
            kernel32.GetModuleHandleW(None),
            None,
        )
        if not self.hwnd:
            raise OSError(ctypes.get_last_error(), "CreateWindowExW failed")
        point = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(point))
        self._origin = (point.x, point.y)
        self._hint_until = time.monotonic() + HINT_SECONDS
        user32.ShowWindow(self.hwnd, SW_SHOW)
        user32.UpdateWindow(self.hwnd)
        user32.SetWindowPos(self.hwnd, -1, x, y, width, height, 0x0040)
        user32.SetCursor(None)

    def pump(self, seconds: float = 0.03) -> bool:
        """Dispatch pending messages; False once the user dismissed the shield."""

        deadline = time.monotonic() + seconds
        msg = MSG()
        while True:
            while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):  # PM_REMOVE
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            if self._dismissed:
                return False
            if time.monotonic() >= deadline:
                return True
            time.sleep(0.01)

    def close(self) -> None:
        hwnd, self.hwnd = self.hwnd, None
        if hwnd:
            user32.DestroyWindow(hwnd)
        user32.SetCursor(user32.LoadCursorW(None, ctypes.c_void_p(32512)))  # IDC_ARROW


__all__ = ["ShieldWindow"]
