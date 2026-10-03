"""子进程控制台标志的统一入口（Windows 桌面"黑框一闪"的集中修复点）。

背景：后端可能在没有可继承控制台的形态下运行（``pythonw.exe`` 或
``DETACHED_PROCESS``）。此时任何**未加** ``CREATE_NO_WINDOW`` 的控制台子系统子进程
（``git`` / ``cmd`` / ``powershell`` / ``taskkill`` / ``pip`` …）都会被 Windows
新建一个**可见**控制台窗口，表现为桌面"黑框一闪"。

约定：

* 输出被 ``PIPE`` / ``DEVNULL`` 接管的子进程 → 直接用 :data:`NO_WINDOW`
  （或 :func:`hidden_flags`），隐藏是纯收益。
* 输出本身就是给用户看的进度（例如启动 ``RUN.bat``）→ 用
  :func:`inherit_or_hide_flags`：调用方自己**有**控制台时继承它（保留可见进度），
  只有在没有控制台可用时才隐藏，避免凭空多出一个浮动黑窗。

非 Windows 平台所有标志取值为 0，``Popen(creationflags=0)`` 合法，可无脑使用。
"""

from __future__ import annotations

import subprocess
import sys

#: Windows：为新进程隐藏控制台窗口；其他平台：0。
NO_WINDOW: int = getattr(subprocess, "CREATE_NO_WINDOW", 0)
#: Windows：让子进程独立于父进程的 Ctrl+C 信号组；其他平台：0。
NEW_PROCESS_GROUP: int = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

#: 引用 ``win32`` 静态标志常量，避免各模块再写一遍 ``getattr(subprocess, ...)``。
_STD_OUTPUT_HANDLE = 0xFFFFFFF5  # -11
_STD_ERROR_HANDLE = 0xFFFFFFF4  # -12


def hidden_flags(*, new_process_group: bool = False) -> int:
    """返回"不要让子进程弹出控制台窗口"的 ``creationflags``。"""
    flags = NO_WINDOW
    if new_process_group:
        flags |= NEW_PROCESS_GROUP
    return flags


def console_attached() -> bool:
    """当前进程是否已经附着在某个控制台上。

    不能只看 ``GetConsoleWindow()``：它对"无窗口控制台"（本进程由
    ``CREATE_NO_WINDOW`` 启动，例如后端主进程）和 ConPTY 终端（Windows Terminal）
    都可能返回 0。因此再探测标准输出/错误句柄是否为控制台句柄。
    """
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.GetConsoleWindow.restype = ctypes.c_void_p
        if kernel32.GetConsoleWindow():
            return True
        kernel32.GetStdHandle.restype = ctypes.c_void_p
        kernel32.GetStdHandle.argtypes = [ctypes.c_ulong]
        for std_handle in (_STD_OUTPUT_HANDLE, _STD_ERROR_HANDLE):
            handle = kernel32.GetStdHandle(std_handle)
            if not handle or handle == ctypes.c_void_p(-1).value:
                continue
            mode = ctypes.c_ulong()
            if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                return True
    except Exception:
        return False
    return False


def inherit_or_hide_flags(*, new_process_group: bool = False) -> int:
    """调用方有控制台则继承（用户能看到输出），否则隐藏新控制台窗口。"""
    flags = NEW_PROCESS_GROUP if new_process_group else 0
    if not console_attached():
        flags |= NO_WINDOW
    return flags
