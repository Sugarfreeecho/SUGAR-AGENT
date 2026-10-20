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


def _fake_ifiledialog(monkeypatch, show_hr, result_hr, cancelled_path=None):
    """Install a fake IFileDialog vtable; return the list of HRESULT-level calls.

    No OS dialog opens: the vtables supply the same outputs as IFileDialog.
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
    # `retained` 持有回调与 vtable 内存，必须活到断言结束（否则函数指针悬空）。
    return calls, retained


@pytest.mark.skipif(sys.platform != "win32", reason="Windows COM ABI")
@pytest.mark.parametrize(
    "kind,show_hr,result_hr,expected,cancelled",
    [
        ("directory", 0, 0, r"D:\projects\selected-child", False),
        ("file", 0, 0, r"D:\projects\selected-child", False),
        ("directory", ctypes.c_int32(0x800704C7).value, 0, None, True),
    ],
)
def test_windows_dialog_returns_confirmed_selection(
    monkeypatch, kind, show_hr, result_hr, expected, cancelled
):
    """The browsing folder must never substitute for the confirmed result."""
    calls, _retained = _fake_ifiledialog(monkeypatch, show_hr, result_hr)

    assert path_picker_util._pick_windows_ifiledialog_impl(kind, "") == (expected, cancelled)
    assert "GetFolder" not in calls
    assert calls == ([] if cancelled else ["GetResult"])


@pytest.mark.skipif(sys.platform != "win32", reason="Windows COM ABI")
def test_windows_dialog_result_failure_is_terminal(monkeypatch):
    """A confirmed pick we cannot read must not re-open another picker form."""
    _calls, _retained = _fake_ifiledialog(monkeypatch, 0, -1)

    with pytest.raises(path_picker_util.PathPickerDialogError):
        path_picker_util._pick_windows_ifiledialog_impl("directory", "")


def _install_backends(monkeypatch, backends):
    monkeypatch.setattr(path_picker_util, "_backends", lambda: list(backends))
    monkeypatch.setattr(path_picker_util, "_preferred_backend", None)


def test_dialog_error_does_not_fall_back_to_another_picker(monkeypatch):
    """Once a dialog has been shown, the next backend must stay closed."""
    monkeypatch.setattr(path_picker_util.platform, "system", lambda: "Windows")
    calls = []

    def first(_kind, _initial):
        calls.append("first")
        raise path_picker_util.PathPickerDialogError("没有返回可用的目录路径")

    def second(_kind, _initial):
        calls.append("second")
        return r"D:\other"

    _install_backends(monkeypatch, [("first", first), ("second", second)])

    with pytest.raises(path_picker_util.PathPickerDialogError):
        path_picker_util.pick_native_path("directory")
    assert calls == ["first"]


@pytest.mark.parametrize(
    "failure",
    [
        path_picker_util.PathPickerUnavailable("未安装"),
        ImportError("No module named 'tkinter'"),
        FileNotFoundError("zenity"),
    ],
)
def test_unavailable_backend_falls_through(monkeypatch, failure):
    monkeypatch.setattr(path_picker_util.platform, "system", lambda: "Windows")

    def first(_kind, _initial):
        raise failure

    def second(_kind, _initial):
        return r"D:\picked"

    _install_backends(monkeypatch, [("first", first), ("second", second)])

    assert path_picker_util.pick_native_path("directory") == r"D:\picked"
    assert path_picker_util._preferred_backend == "second"
    assert [name for name, _fn in path_picker_util._ordered_backends()][0] == "second"


def test_all_backends_unavailable_reports_install_hint(monkeypatch):
    monkeypatch.setattr(path_picker_util.platform, "system", lambda: "Windows")

    def unavailable(_kind, _initial):
        raise path_picker_util.PathPickerUnavailable("未安装")

    _install_backends(monkeypatch, [("only", unavailable)])

    with pytest.raises(RuntimeError, match="无法打开本机文件选择对话框"):
        path_picker_util.pick_native_path("directory")


def test_concurrent_pick_is_rejected(monkeypatch):
    monkeypatch.setattr(path_picker_util.platform, "system", lambda: "Windows")
    _install_backends(monkeypatch, [("only", lambda _kind, _initial: r"D:\picked")])

    assert path_picker_util._pick_lock.acquire(blocking=False)
    try:
        with pytest.raises(path_picker_util.PathPickerDialogError, match="正在等待操作"):
            path_picker_util.pick_native_path("directory")
    finally:
        path_picker_util._pick_lock.release()
    # The rejected attempt must not leave the lock held.
    assert path_picker_util.pick_native_path("directory") == r"D:\picked"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows COM ABI")
def test_sta_thread_returns_value_and_propagates_errors():
    assert path_picker_util._run_in_sta_thread(lambda: 42) == 42

    def boom():
        raise path_picker_util.PathPickerDialogError("对话框失败")

    with pytest.raises(path_picker_util.PathPickerDialogError, match="对话框失败"):
        path_picker_util._run_in_sta_thread(boom)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows COM ABI")
def test_sta_thread_reports_mta_thread_as_unavailable(monkeypatch):
    def refuse(*_args):
        raise OSError(path_picker_util.RPC_E_CHANGED_MODE, "线程模式已设置")

    monkeypatch.setattr(
        ctypes,
        "OleDLL",
        lambda _name: SimpleNamespace(CoInitializeEx=refuse, CoUninitialize=lambda: None),
    )

    with pytest.raises(path_picker_util.PathPickerUnavailable, match="MTA"):
        path_picker_util._run_in_sta_thread(lambda: r"D:\never")
