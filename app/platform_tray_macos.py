"""Native macOS NSStatusItem menu-bar adapter through PyObjC."""

from __future__ import annotations

import os
import threading
from pathlib import Path

try:
    from .platform_lifecycle import LaunchdUserBackend, open_webui
    from .platform_tray import lifecycle_menu_enabled, launch_updater, open_logs_in_terminal
except ImportError:
    from platform_lifecycle import LaunchdUserBackend, open_webui
    from platform_tray import lifecycle_menu_enabled, launch_updater, open_logs_in_terminal


def run(root: Path) -> int:
    try:
        import objc
        from AppKit import (
            NSAlert,
            NSAlertFirstButtonReturn,
            NSApplication,
            NSApplicationActivationPolicyAccessory,
            NSImage,
            NSMenu,
            NSMenuItem,
            NSStatusBar,
            NSVariableStatusItemLength,
        )
        from Foundation import NSObject
        from PyObjCTools import AppHelper
    except ImportError as exc:
        raise RuntimeError(
            "macOS menu-bar dependencies are missing. "
            "Install pyobjc-framework-Cocoa in the SugarAgent virtual environment."
        ) from exc

    backend = LaunchdUserBackend(root)
    backend.start()

    class TrayDelegate(NSObject):
        def init(self):
            self = objc.super(TrayDelegate, self).init()
            if self is None:
                return None
            self.status_item = None
            return self

        @objc.python_method
        def _confirm(self, message: str) -> bool:
            alert = NSAlert.alloc().init()
            alert.setMessageText_("SugarAgent")
            alert.setInformativeText_(message)
            alert.addButtonWithTitle_("继续")
            alert.addButtonWithTitle_("取消")
            return alert.runModal() == NSAlertFirstButtonReturn

        @objc.python_method
        def _error(self, message: str) -> None:
            alert = NSAlert.alloc().init()
            alert.setMessageText_("SugarAgent")
            alert.setInformativeText_(str(message))
            alert.runModal()

        def openAgent_(self, _sender):
            open_webui("/")

        def openSettings_(self, _sender):
            open_webui("/setup/env")

        def openMcp_(self, _sender):
            open_webui("/setup/mcp")

        def openLogs_(self, _sender):
            try:
                open_logs_in_terminal(backend)
            except Exception as exc:
                self._error(str(exc))

        def restartAgent_(self, _sender):
            if not self._confirm("重启会中断当前正在运行的任务，是否继续？"):
                return
            threading.Thread(target=backend.restart, daemon=True).start()

        def updateAgent_(self, _sender):
            if not self._confirm("更新会中断当前任务并执行安全的 Git 快进更新，是否继续？"):
                return
            launch_updater(backend)
            NSApplication.sharedApplication().terminate_(None)

        def exitAgent_(self, _sender):
            if not self._confirm("退出将停止 SugarAgent 服务，是否继续？"):
                return
            backend.stop()
            NSApplication.sharedApplication().terminate_(None)

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    delegate = TrayDelegate.alloc().init()
    status_item = NSStatusBar.systemStatusBar().statusItemWithLength_(
        NSVariableStatusItemLength
    )
    delegate.status_item = status_item
    icon = NSImage.alloc().initWithContentsOfFile_(
        str(root / "app" / "assets" / "sugar-logo.png")
    )
    if icon is not None:
        icon.setTemplate_(True)
        status_item.button().setImage_(icon)
    else:
        status_item.button().setTitle_("S")
    status_item.button().setToolTip_("SugarAgent")

    menu = NSMenu.alloc().init()

    def add(title: str, selector: str) -> None:
        item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, selector, "")
        item.setTarget_(delegate)
        menu.addItem_(item)

    add("打开 Agent", "openAgent:")
    add("高级设置", "openSettings:")
    add("MCP 配置", "openMcp:")
    add("运行日志", "openLogs:")
    if lifecycle_menu_enabled(root):
        menu.addItem_(NSMenuItem.separatorItem())
        add("重启", "restartAgent:")
        add("更新", "updateAgent:")
    menu.addItem_(NSMenuItem.separatorItem())
    add("退出 Agent", "exitAgent:")
    status_item.setMenu_(menu)
    app.setDelegate_(delegate)
    AppHelper.runEventLoop()
    return 0
