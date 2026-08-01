"""Ubuntu GTK/Ayatana AppIndicator tray adapter."""

from __future__ import annotations

import threading
from pathlib import Path

try:
    from .platform_lifecycle import SystemdUserBackend, open_webui
    from .platform_tray import lifecycle_menu_enabled, launch_updater, open_logs_in_terminal
except ImportError:
    from platform_lifecycle import SystemdUserBackend, open_webui
    from platform_tray import lifecycle_menu_enabled, launch_updater, open_logs_in_terminal


def run(root: Path) -> int:
    try:
        import gi

        gi.require_version("Gtk", "3.0")
        gi.require_version("AyatanaAppIndicator3", "0.1")
        from gi.repository import AyatanaAppIndicator3 as AppIndicator3
        from gi.repository import GLib, Gtk
    except (ImportError, ValueError) as exc:
        raise RuntimeError(
            "Linux tray dependencies are missing. Install python3-gi, "
            "gir1.2-gtk-3.0 and gir1.2-ayatanaappindicator3-0.1."
        ) from exc

    backend = SystemdUserBackend(root)
    backend.start()
    icon = root / "app" / "assets" / "sugar-logo.png"
    indicator = AppIndicator3.Indicator.new(
        "sugaragent",
        str(icon),
        AppIndicator3.IndicatorCategory.APPLICATION_STATUS,
    )
    indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
    indicator.set_title("SugarAgent")

    menu = Gtk.Menu()

    def add(label: str, callback, *, sensitive: bool = True) -> Gtk.MenuItem:
        item = Gtk.MenuItem(label=label)
        item.set_sensitive(sensitive)
        item.connect("activate", callback)
        item.show()
        menu.append(item)
        return item

    def separator() -> None:
        item = Gtk.SeparatorMenuItem()
        item.show()
        menu.append(item)

    def show_error(message: str) -> None:
        dialog = Gtk.MessageDialog(
            transient_for=None,
            flags=0,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text="SugarAgent",
        )
        dialog.format_secondary_text(str(message))
        dialog.run()
        dialog.destroy()

    def confirm(message: str) -> bool:
        dialog = Gtk.MessageDialog(
            transient_for=None,
            flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text="SugarAgent",
        )
        dialog.format_secondary_text(message)
        result = dialog.run() == Gtk.ResponseType.YES
        dialog.destroy()
        return result

    def background(action) -> None:
        def worker() -> None:
            try:
                action()
            except Exception as exc:
                GLib.idle_add(show_error, str(exc))

        threading.Thread(target=worker, daemon=True).start()

    add("打开 Agent", lambda _item: open_webui("/"))
    add("高级设置", lambda _item: open_webui("/setup/env"))
    add("MCP 配置", lambda _item: open_webui("/setup/mcp"))

    def view_logs(_item) -> None:
        try:
            open_logs_in_terminal(backend)
        except Exception as exc:
            show_error(str(exc))

    add("运行日志", view_logs)
    if lifecycle_menu_enabled(root):
        separator()

        def restart(_item) -> None:
            if confirm("重启会中断当前正在运行的任务，是否继续？"):
                background(backend.restart)

        def update(_item) -> None:
            if confirm("更新会中断当前任务并执行安全的 Git 快进更新，是否继续？"):
                launch_updater(backend)
                Gtk.main_quit()

        add("重启", restart)
        add("更新", update)
    separator()

    def exit_agent(_item) -> None:
        if confirm("退出将停止 SugarAgent 服务，是否继续？"):
            try:
                backend.stop()
            finally:
                Gtk.main_quit()

    add("退出 Agent", exit_agent)
    menu.show_all()
    indicator.set_menu(menu)
    Gtk.main()
    return 0
