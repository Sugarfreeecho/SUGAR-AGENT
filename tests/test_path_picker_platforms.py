import ctypes
import sys
from types import SimpleNamespace

import pytest

from app import path_picker_util


def test_linux_desktop_prefers_zenity(monkeypatch):
    monkeypatch.setattr(path_picker_util.platform, "system", lambda: "Linux")
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)

    assert [name for name, _fn in path_picker_util._backends()] == [
        "zenity",
        "tkinter",
    ]


def test_linux_headless_has_no_gui_backend(monkeypatch):
    monkeypatch.setattr(path_picker_util.platform, "system", lambda: "Linux")
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)

    assert path_picker_util._backends() == []
    with pytest.raises(RuntimeError, match="headless Linux"):
        path_picker_util.pick_native_path("file")


def test_macos_prefers_native_osascript(monkeypatch):
    monkeypatch.setattr(path_picker_util.platform, "system", lambda: "Darwin")

    assert [name for name, _fn in path_picker_util._backends()] == [
        "macos-osascript",
        "tkinter",
    ]


@pytest.mark.skipif(sys.platform != "win32", reason="Windows COM ABI")
@pytest.mark.parametrize(
    "kind,show_hr,result_hr,expected,cancelled",
    [
        ("directory", 0, 0, r"D:\projects\selected-child", False),
        ("file", 0, 0, r"D:\projects\selected-child", False),
        ("directory", ctypes.c_int32(0x800704C7).value, 0, None, True),
        ("directory", 0, -1, None, False),
    ],
)
def test_windows_dialog_returns_confirmed_selection(
    monkeypatch, kind, show_hr, result_hr, expected, cancelled
):
    """Run the real COM binding with different browsing/confirmed folders.

    No OS dialog opens: the vtables supply the same outputs as IFileDialog.
    The browsing folder must never substitute for the confirmed result,
    including when GetResult fails or the user cancels.
    """
    from ctypes import wintypes as wt

    retained = []
    calls = []

    def interface(methods, size):
        table = (ctypes.c_void_p * size)()
        for index, (argument_types, handler) in methods.items():
            callback = ctypes.WINFUNCTYPE(
                ctypes.HRESULT, ctypes.c_void_p, *argument_types
            )(handler)
            retained.append(callback)
            table[index] = ctypes.cast(callback, ctypes.c_void_p).value
        instance = (ctypes.c_void_p * 1)(ctypes.addressof(table))
        retained.extend([table, instance])
        return ctypes.addressof(instance)

    def shell_item(path):
        buffer = ctypes.create_unicode_buffer(path)
        retained.append(buffer)

        def display_name(_this, _kind, output):
            output[0] = ctypes.cast(buffer, wt.LPWSTR)
            return 0

        return interface({5: ([wt.DWORD, ctypes.POINTER(wt.LPWSTR)], display_name)}, 6)

    browsing_item = shell_item(r"D:\projects\default-workspace")
    selected_item = shell_item(r"D:\projects\selected-child")

    def get_folder(_this, output):
        calls.append("GetFolder")
        output[0] = browsing_item
        return 0

    def get_result(_this, output):
        calls.append("GetResult")
        if result_hr == 0:
            output[0] = selected_item
        return result_hr

    dialog = interface({
        3: ([wt.HWND], lambda *_args: show_hr),
        9: ([wt.DWORD], lambda *_args: 0),
        12: ([ctypes.c_void_p], lambda *_args: 0),
        13: ([ctypes.POINTER(ctypes.c_void_p)], get_folder),
        17: ([wt.LPCWSTR], lambda *_args: 0),
        20: ([ctypes.POINTER(ctypes.c_void_p)], get_result),
    }, 21)

    def create_instance(_class, _outer, _context, _iid, output):
        ctypes.cast(output, ctypes.POINTER(ctypes.c_void_p))[0] = dialog
        return 0

    def create_shell_item(_path, _context, _iid, output):
        ctypes.cast(output, ctypes.POINTER(ctypes.c_void_p))[0] = browsing_item
        return 0

    ole = SimpleNamespace(
        CoInitializeEx=lambda *_args: 0,
        CoCreateInstance=create_instance,
        CoTaskMemFree=lambda *_args: None,
        CoUninitialize=lambda: None,
    )
    shell = SimpleNamespace(SHCreateItemFromParsingName=create_shell_item)
    monkeypatch.setattr(ctypes, "OleDLL", lambda name: ole if name == "ole32" else shell)
    monkeypatch.setattr(path_picker_util, "_safe_initial_dir", lambda _initial: r"D:\projects\default-workspace")
    monkeypatch.setattr(path_picker_util, "_dialog_owner_hwnd", lambda: 0)

    assert path_picker_util._pick_windows_ifiledialog_impl(kind, "") == (expected, cancelled)
    assert "GetFolder" not in calls
    assert calls == ([] if cancelled else ["GetResult"])
