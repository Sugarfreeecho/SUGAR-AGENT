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
