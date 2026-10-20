"""本机文件/目录选择对话框，供 Web UI 配置项与聊天输入使用。"""

from __future__ import annotations

import os
import platform
import subprocess
import threading
from pathlib import Path
from typing import Callable, Literal, Optional, Tuple

try:  # 生产环境按扁平模块导入（app/ 在 sys.path 上）
    from proc_flags import hidden_flags
except ImportError:  # 以 app.* 包路径导入时（测试 / 工具脚本）
    from app.proc_flags import hidden_flags

PathPickKind = Literal["file", "directory"]

HRESULT_CANCELLED = 0x800704C7
RPC_E_CHANGED_MODE = 0x80010106

# 一次只允许一个原生选择框：两个请求同时弹框时用户会看到样式不同的两个窗口，
# 而且第二个窗口的返回值会盖掉第一个。并发请求直接拒绝并提示先处理已打开的窗口。
_pick_lock = threading.Lock()


class PathPickerUnavailable(RuntimeError):
    """该后端无法弹出对话框（未安装 / COM 不可用 / 程序缺失）。

    报这个错时用户还没看到任何窗口，兜底链可以继续尝试下一个后端。
    """


class PathPickerDialogError(RuntimeError):
    """对话框已经弹出、用户已经选过，但没能拿到可用结果。

    此时绝对不能再弹下一个后端的选择框：那会让用户在同一件事上先后面对
    两种/三种样式的"选择文件夹"窗口，并且第一次的选择看起来"无效"。
    """


def _hresult_unsigned(hr: int) -> int:
    return int(hr) & 0xFFFFFFFF


def _hresult_succeeded(hr: int) -> bool:
    return _hresult_unsigned(hr) < 0x80000000


def _is_cancelled_hr(hr: int) -> bool:
    return _hresult_unsigned(hr) == HRESULT_CANCELLED


def _is_com_mode_conflict(exc: BaseException) -> bool:
    """异常是否为 CoInitializeEx 的 RPC_E_CHANGED_MODE（线程已属于别的套间）。

    ctypes 的 OleDLL 把失败的 HRESULT 抛成 OSError：真实的 Windows 错误码在
    `winerror` 上，手工构造的 OSError 只留 `errno` / `args[0]`，两者都要看。
    """
    candidates = [getattr(exc, "winerror", None), getattr(exc, "errno", None)]
    if exc.args:
        candidates.append(exc.args[0])
    for value in candidates:
        if isinstance(value, int) and _hresult_unsigned(value) == RPC_E_CHANGED_MODE:
            return True
    text = str(exc).lower()
    return "80010106" in text or "2147549446" in text


def _is_user_cancelled_exc(exc: BaseException) -> bool:
    if isinstance(exc, OSError):
        for arg in exc.args:
            if isinstance(arg, int) and _is_cancelled_hr(arg):
                return True
    text = str(exc).lower()
    return "800704c7" in text or "2147023673" in text or "操作已被用户取消" in str(exc)

_hidden_owner_hwnd: Optional[int] = None
_wndproc_ref = None  # 防止回调被 GC


def _initial_dir(initial: str) -> Optional[str]:
    raw = (initial or "").strip().strip('"').strip("'")
    if not raw:
        return None
    try:
        p = Path(raw).expanduser()
        if p.is_file():
            return str(p.parent.resolve())
        if p.is_dir():
            return str(p.resolve())
        parent = p.parent
        if parent.is_dir():
            return str(parent.resolve())
    except OSError:
        pass
    return None


def _is_windows_network_path(path: str) -> bool:
    s = str(path or "").strip().replace("/", "\\")
    if s.startswith("\\\\"):
        return True
    if len(s) >= 2 and s[1] == ":" and platform.system() == "Windows":
        try:
            import ctypes

            root = s[:3] if len(s) >= 3 and s[2] == "\\" else s[:2] + "\\"
            return ctypes.windll.kernel32.GetDriveTypeW(root) == 4  # DRIVE_REMOTE
        except Exception:
            return False
    return False


def _default_local_initial_dir() -> str:
    candidates = [
        os.getenv("USERPROFILE", ""),
        os.path.expanduser("~"),
        os.path.join(os.getenv("USERPROFILE", ""), "Desktop") if os.getenv("USERPROFILE") else "",
        os.getenv("WORK_DIR", ""),
        str(Path(__file__).resolve().parent.parent / "workspace"),
        os.getcwd(),
    ]
    for raw in candidates:
        if not raw:
            continue
        try:
            p = Path(raw).expanduser()
            if p.is_file():
                p = p.parent
            if p.is_dir():
                resolved = str(p.resolve())
                if platform.system() == "Windows" and _is_windows_network_path(resolved):
                    continue
                return resolved
        except OSError:
            continue
    return os.path.abspath(os.sep)


def _safe_initial_dir(initial: str) -> str:
    init = _initial_dir(initial)
    if init and not (platform.system() == "Windows" and _is_windows_network_path(init)):
        return init
    return _default_local_initial_dir()


def _norm_result(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    s = str(path).strip()
    if not s:
        return None
    return os.path.normpath(s)


def _dialog_owner_hwnd() -> int:
    """对话框父窗口：优先当前前台窗口，否则用不显示在任务栏的隐藏宿主。"""
    global _hidden_owner_hwnd, _wndproc_ref
    import ctypes
    import ctypes.wintypes as wt

    user32 = ctypes.windll.user32
    fg = user32.GetForegroundWindow()
    if fg:
        return int(fg)

    if _hidden_owner_hwnd and user32.IsWindow(_hidden_owner_hwnd):
        return _hidden_owner_hwnd

    WndProcType = ctypes.WINFUNCTYPE(
        ctypes.c_ssize_t, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM
    )

    def _wndproc(hwnd, msg, wparam, lparam):
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    _wndproc_ref = WndProcType(_wndproc)
    wndproc = _wndproc_ref

    class WNDCLASSW(ctypes.Structure):
        _fields_ = [
            ("style", wt.UINT),
            ("lpfnWndProc", WndProcType),
            ("cbClsExtra", ctypes.c_int),
            ("cbWndExtra", ctypes.c_int),
            ("hInstance", wt.HINSTANCE),
            ("hIcon", wt.HANDLE),
            ("hCursor", wt.HANDLE),
            ("hbrBackground", wt.HANDLE),
            ("lpszMenuName", wt.LPCWSTR),
            ("lpszClassName", wt.LPCWSTR),
        ]

    wc = WNDCLASSW()
    wc.lpfnWndProc = wndproc
    wc.lpszClassName = "MyAgentPathPickerOwner"
    if not user32.RegisterClassW(ctypes.byref(wc)):
        pass

    WS_EX_TOOLWINDOW = 0x00000080
    hwnd = user32.CreateWindowExW(
        WS_EX_TOOLWINDOW,
        "MyAgentPathPickerOwner",
        "",
        0,
        0,
        0,
        0,
        0,
        None,
        None,
        None,
        None,
    )
    if not hwnd:
        return 0
    _hidden_owner_hwnd = int(hwnd)
    return _hidden_owner_hwnd


def _release_dialog_owner() -> None:
    """销毁本线程创建的隐藏宿主窗口（STA 选择线程收尾时调用）。"""
    global _hidden_owner_hwnd
    hwnd, _hidden_owner_hwnd = _hidden_owner_hwnd, None
    if not hwnd:
        return
    try:
        import ctypes

        ctypes.windll.user32.DestroyWindow(hwnd)
    except Exception:
        pass


def _pick_dialog_timeout() -> float:
    """用户在新版选择框里停留的最长等待时间（秒）。"""
    try:
        value = float(os.getenv("MYAGENT_PATH_DIALOG_TIMEOUT", "1800"))
    except ValueError:
        value = 1800.0
    return value if value > 0 else 1800.0


def _run_in_sta_thread(callback: Callable[[], object]) -> object:
    """在一条独立的 STA 线程里执行 callback，并原样回传结果或异常。

    IFileDialog 必须在单线程套间（STA）里创建。Web 侧是 `run_in_threadpool`
    调用本模块，而线程池线程可能已被别的库初始化为 MTA（此时 CoInitializeEx
    返回 RPC_E_CHANGED_MODE，ctypes 的 OleDLL 会直接抛 OSError）——旧实现在
    这种情况下会放弃新版对话框、继续走 tkinter / PowerShell 兜底，于是用户
    先看到新版窗口、再被要求到另一种样式的旧窗口里重选一次。固定用一条新的
    STA 线程执行，选择框的样式就不再取决于请求恰好落在哪条线程池线程上。
    """
    box: dict[str, object] = {}
    done = threading.Event()

    def _runner() -> None:
        ole32 = None
        initialized = False
        try:
            import ctypes

            ole32 = ctypes.OleDLL("ole32")
            try:
                ole32.CoInitializeEx(None, 0x2)  # COINIT_APARTMENTTHREADED
                initialized = True
            except OSError as exc:
                if _is_com_mode_conflict(exc):
                    raise PathPickerUnavailable("线程已初始化为 MTA，无法使用系统文件夹对话框")
                raise PathPickerUnavailable(f"COM 初始化失败（{exc}）")
            box["value"] = callback()
        except BaseException as exc:  # noqa: BLE001 - 原样转交给调用线程
            box["error"] = exc
        finally:
            _release_dialog_owner()
            if initialized and ole32 is not None:
                try:
                    ole32.CoUninitialize()
                except Exception:
                    pass
            done.set()

    thread = threading.Thread(target=_runner, name="myagent-path-picker", daemon=True)
    thread.start()
    if not done.wait(_pick_dialog_timeout()):
        raise PathPickerDialogError("系统文件夹对话框长时间没有返回，请重试")
    if "error" in box:
        raise box["error"]  # type: ignore[misc]
    return box.get("value")


def _pick_windows_ifiledialog(kind: PathPickKind, initial: str) -> Optional[str]:
    path, cancelled = _run_in_sta_thread(
        lambda: _pick_windows_ifiledialog_impl(kind, initial)
    )  # type: ignore[misc]
    if cancelled:
        return None
    if not path:
        raise PathPickerDialogError("系统文件夹对话框已关闭，但没有返回所选目录")
    return path


def _pick_windows_ifiledialog_impl(
    kind: PathPickKind, initial: str
) -> Tuple[Optional[str], bool]:
    """返回 (路径, 是否用户取消)。"""
    import ctypes
    import ctypes.wintypes as wt
    import uuid

    class GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", wt.DWORD),
            ("Data2", wt.WORD),
            ("Data3", wt.WORD),
            ("Data4", wt.BYTE * 8),
        ]

        @classmethod
        def from_str(cls, s: str) -> "GUID":
            u = uuid.UUID(s)
            g = cls()
            g.Data1 = u.time_low
            g.Data2 = u.fields[1]
            g.Data3 = u.fields[2]
            g.Data4 = (wt.BYTE * 8).from_buffer_copy(u.bytes[8:])
            return g

    CLSID_FileOpenDialog = GUID.from_str("DC1C5A9C-E88A-4dde-A5A1-60F82A20AEF7")
    IID_IFileOpenDialog = GUID.from_str("d57c7288-d4ad-4768-be02-9d969532d960")
    IID_IShellItem = GUID.from_str("43826d1e-e718-42ee-bc55-a1e261c37bfe")

    FOS_PICKFOLDERS = 0x20
    FOS_FORCEFILESYSTEM = 0x40
    FOS_PATHMUSTEXIST = 0x800
    FOS_FILEMUSTEXIST = 0x1000
    SIGDN_FILESYSPATH = 0x80058000
    # 不是所有 shell 项都能给出文件系统路径（例如"此电脑"、网络位置、库、
    # 压缩包内的目录），但都能给出解析名。解析名同样指向用户确认的那一项，
    # 读不到文件系统路径时用它兜住，避免"选完却拿不到结果"。
    SIGDN_DESKTOPABSOLUTEPARSING = 0x80028000

    ole32 = ctypes.OleDLL("ole32")
    shell32 = ctypes.OleDLL("shell32")

    def _shell_item_path(item: ctypes.c_void_p) -> Optional[str]:
        if not item:
            return None
        item_vtbl = ctypes.cast(
            item, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))
        ).contents
        get_display_name = ctypes.WINFUNCTYPE(
            ctypes.c_long, ctypes.c_void_p, wt.DWORD, ctypes.POINTER(wt.LPWSTR)
        )(item_vtbl[5])
        for display_form in (SIGDN_FILESYSPATH, SIGDN_DESKTOPABSOLUTEPARSING):
            psz = wt.LPWSTR()
            hr = get_display_name(item, display_form, ctypes.byref(psz))
            if hr < 0 or not psz.value:
                continue
            try:
                resolved = _norm_result(psz.value)
            finally:
                ole32.CoTaskMemFree(psz)
            if resolved:
                return resolved
        return None

    try:
        ole32.CoInitializeEx(None, 0x2)
    except OSError as exc:
        # 线程已被其它库初始化为 MTA 时 ctypes 会直接抛 HRESULT：这里属于
        # "还没弹窗"，交给上层换一条 STA 线程（_run_in_sta_thread）或兜底链。
        if _is_com_mode_conflict(exc):
            raise PathPickerUnavailable("线程已初始化为 MTA，无法使用系统文件夹对话框") from exc
        raise PathPickerUnavailable(f"COM 初始化失败（{exc}）") from exc
    dialog = ctypes.c_void_p()
    hr = ole32.CoCreateInstance(
        ctypes.byref(CLSID_FileOpenDialog),
        None,
        1,
        ctypes.byref(IID_IFileOpenDialog),
        ctypes.byref(dialog),
    )
    if hr < 0:
        ole32.CoUninitialize()
        raise PathPickerUnavailable(f"CoCreateInstance 失败: {hr:#010x}")

    try:
        vtbl = ctypes.cast(dialog, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents

        def _fn(idx: int, restype, *argtypes):
            proto = ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)
            return proto(vtbl[idx])

        # ctypes.HRESULT raises OSError on failure before our cancellation and
        # result checks run. Read the raw signed HRESULT for explicit handling.
        set_options = _fn(9, ctypes.c_long, wt.DWORD)
        set_folder = _fn(12, ctypes.c_long, ctypes.c_void_p)
        set_title = _fn(17, ctypes.c_long, wt.LPCWSTR)
        show = _fn(3, ctypes.c_long, wt.HWND)
        get_result = _fn(20, ctypes.c_long, ctypes.POINTER(ctypes.c_void_p))

        options = FOS_FORCEFILESYSTEM | FOS_PATHMUSTEXIST
        dlg_title = "选择文件夹" if kind == "directory" else "选择文件"
        if kind == "directory":
            options |= FOS_PICKFOLDERS
        else:
            options |= FOS_FILEMUSTEXIST

        hr = set_options(dialog, options)
        if hr < 0:
            raise PathPickerUnavailable(f"SetOptions 失败: {hr:#010x}")

        set_title(dialog, dlg_title)

        init_dir = _safe_initial_dir(initial)
        folder_item = ctypes.c_void_p()
        hr = shell32.SHCreateItemFromParsingName(
            wt.LPCWSTR(init_dir),
            None,
            ctypes.byref(IID_IShellItem),
            ctypes.byref(folder_item),
        )
        if hr >= 0 and folder_item:
            set_folder(dialog, folder_item)

        owner = _dialog_owner_hwnd()

        hr = show(dialog, owner or None)
        if _is_cancelled_hr(hr):
            return None, True
        if not _hresult_succeeded(hr):
            # 对话框已经弹出过：换成另一种样式的选择器会让用户重选一遍。
            raise PathPickerDialogError(
                f"系统文件夹对话框异常结束（HRESULT {_hresult_unsigned(hr):#010x}）"
            )

        # GetResult is the user's confirmed selection for both files and
        # FOS_PICKFOLDERS. GetFolder reports the browsing location (or the
        # initial folder after the dialog closes), which can still be the
        # default directory when a child folder was selected without opening it.
        result = ctypes.c_void_p()
        hr = get_result(dialog, ctypes.byref(result))
        if _hresult_succeeded(hr) and result:
            path = _shell_item_path(result)
            if path:
                return path, False
        raise PathPickerDialogError("系统文件夹对话框没有返回可用的目录路径")
    finally:
        ole32.CoUninitialize()


def _pick_tkinter(kind: PathPickKind, initial: str) -> Optional[str]:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError as exc:
        raise PathPickerUnavailable(f"未安装 tkinter（{exc}）") from exc

    init_dir = _safe_initial_dir(initial)
    try:
        root = tk.Tk()
    except Exception as exc:  # TclError 等：还没有任何窗口
        raise PathPickerUnavailable(f"tkinter 无法创建窗口（{exc}）") from exc
    root.withdraw()
    try:
        root.attributes("-topmost", True)
    except tk.TclError:
        pass
    try:
        if kind == "directory":
            chosen = filedialog.askdirectory(
                initialdir=init_dir,
                mustexist=False,
                parent=root,
            )
        else:
            chosen = filedialog.askopenfilename(
                initialdir=init_dir,
                parent=root,
            )
    except Exception as exc:  # 窗口已弹出，不再换第二种样式
        raise PathPickerDialogError(f"tkinter 选择框出错（{exc}）") from exc
    finally:
        try:
            root.destroy()
        except Exception:
            pass
    return _norm_result(chosen)


def _pick_tkinter_multi_files(initial: str) -> list[str]:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError as exc:
        raise PathPickerUnavailable(f"未安装 tkinter（{exc}）") from exc

    init_dir = _safe_initial_dir(initial)
    try:
        root = tk.Tk()
    except Exception as exc:
        raise PathPickerUnavailable(f"tkinter 无法创建窗口（{exc}）") from exc
    root.withdraw()
    try:
        root.attributes("-topmost", True)
    except tk.TclError:
        pass
    try:
        chosen = filedialog.askopenfilenames(
            initialdir=init_dir,
            parent=root,
        )
    except Exception as exc:
        raise PathPickerDialogError(f"tkinter 选择框出错（{exc}）") from exc
    finally:
        try:
            root.destroy()
        except Exception:
            pass
    out: list[str] = []
    for item in chosen or []:
        p = _norm_result(item)
        if p:
            out.append(p)
    return out


def _ps_quote(s: str) -> str:
    return "'" + str(s or "").replace("'", "''") + "'"


def _pick_windows_powershell(
    kind: PathPickKind, initial: str, multiple: bool = False
) -> Optional[str] | list[str]:
    init_dir = _safe_initial_dir(initial)
    if multiple and kind != "file":
        raise ValueError("multiple=true 仅支持 kind=file")
    if kind == "directory":
        script = (
            "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8;"
            "Add-Type -AssemblyName System.Windows.Forms;"
            "$d=New-Object System.Windows.Forms.FolderBrowserDialog;"
            "$d.Description='选择文件夹';"
            "$d.ShowNewFolderButton=$true;"
            f"$init={_ps_quote(init_dir)};"
            "if($init -and [System.IO.Directory]::Exists($init)){$d.SelectedPath=$init};"
            "$r=$d.ShowDialog();"
            "if($r -eq [System.Windows.Forms.DialogResult]::OK){[Console]::WriteLine($d.SelectedPath)}"
        )
    else:
        script = (
            "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8;"
            "Add-Type -AssemblyName System.Windows.Forms;"
            "$d=New-Object System.Windows.Forms.OpenFileDialog;"
            "$d.Title='选择文件';"
            "$d.CheckFileExists=$true;"
            f"$d.Multiselect={'$true' if multiple else '$false'};"
            f"$init={_ps_quote(init_dir)};"
            "if($init -and [System.IO.Directory]::Exists($init)){$d.InitialDirectory=$init};"
            "$r=$d.ShowDialog();"
            "if($r -eq [System.Windows.Forms.DialogResult]::OK){"
            "if($d.Multiselect){$d.FileNames | ForEach-Object {[Console]::WriteLine($_)}}"
            "else{[Console]::WriteLine($d.FileName)}}"
        )
    try:
        timeout = float(os.getenv("MYAGENT_PATH_PICKER_TIMEOUT", "600"))
    except ValueError:
        timeout = 600.0
    if timeout <= 0:
        timeout = 600.0
    try:
        proc = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-STA",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=hidden_flags(),
        )
    except FileNotFoundError as exc:
        raise PathPickerUnavailable(f"找不到 powershell（{exc}）") from exc
    except subprocess.TimeoutExpired as exc:
        raise PathPickerDialogError("PowerShell 选择框长时间没有返回") from exc
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "PowerShell 文件选择器失败").strip()
        # 脚本本身失败（通常是窗口没能创建）→ 按"还没弹窗"处理，允许继续兜底。
        raise PathPickerUnavailable(err)
    lines = [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]
    if multiple:
        return [_norm_result(line) for line in lines if _norm_result(line)]
    return _norm_result(lines[0]) if lines else None


def _pick_zenity(kind: PathPickKind, initial: str) -> Optional[str]:
    init = _initial_dir(initial)
    cmd = ["zenity"]
    if kind == "directory":
        cmd.append("--file-selection")
        cmd.append("--directory")
    else:
        cmd.append("--file-selection")
    if init:
        cmd.append(f"--filename={init}{os.sep}")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except FileNotFoundError as exc:
        raise PathPickerUnavailable(f"找不到 zenity（{exc}）") from exc
    except subprocess.TimeoutExpired as exc:
        raise PathPickerDialogError("zenity 选择框长时间没有返回") from exc
    if proc.returncode == 1:
        return None
    if proc.returncode != 0:
        raise PathPickerUnavailable((proc.stderr or proc.stdout or "zenity 失败").strip())
    return _norm_result((proc.stdout or "").strip())


def _pick_macos(kind: PathPickKind, initial: str) -> Optional[str]:
    if kind == "directory":
        script = 'POSIX path of (choose folder with prompt "选择文件夹")'
    else:
        script = 'POSIX path of (choose file with prompt "选择文件")'
    try:
        proc = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=600,
        )
    except FileNotFoundError as exc:
        raise PathPickerUnavailable(f"找不到 osascript（{exc}）") from exc
    except subprocess.TimeoutExpired as exc:
        raise PathPickerDialogError("osascript 选择框长时间没有返回") from exc
    if proc.returncode != 0:
        err = (proc.stderr or "").strip()
        if "User canceled" in err or proc.returncode == 1:
            return None
        raise PathPickerUnavailable(err or "osascript 失败")
    return _norm_result((proc.stdout or "").strip())


def _backends() -> list[tuple[str, Callable[[PathPickKind, str], Optional[str]]]]:
    sysname = platform.system()
    order: list[tuple[str, Callable[[PathPickKind, str], Optional[str]]]] = []
    if sysname == "Windows":
        order.append(("windows-ifiledialog", _pick_windows_ifiledialog))
        order.append(("tkinter", _pick_tkinter))
        order.append(("windows-powershell", lambda kind, initial: _pick_windows_powershell(kind, initial, False)))  # type: ignore[arg-type]
    elif sysname == "Darwin":
        order.append(("macos-osascript", _pick_macos))
        order.append(("tkinter", _pick_tkinter))
    else:
        if not (os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY")):
            return []
        order.append(("zenity", _pick_zenity))
        order.append(("tkinter", _pick_tkinter))
    return order


# 已经成功弹出过对话框的后端：同一进程内固定用它，避免"这次是系统新样式、
# 下次是 Tk/旧版样式"的窗口在同一个入口上交替出现。
_preferred_backend: Optional[str] = None


def _remember_backend(name: str) -> None:
    global _preferred_backend
    if name:
        _preferred_backend = name


def _ordered_backends() -> list[tuple[str, Callable[[PathPickKind, str], Optional[str]]]]:
    """优先用已经证明可用的后端，其余按平台默认顺序排在后面。"""
    order = _backends()
    if _preferred_backend:
        head = [item for item in order if item[0] == _preferred_backend]
        if head:
            return head + [item for item in order if item[0] != _preferred_backend]
    return order


def _picker_platform_hint() -> str:
    sysname = platform.system()
    if sysname == "Linux":
        return " Linux：请安装 zenity 并从图形桌面会话启动 SugarAgent。"
    if sysname == "Darwin":
        return " macOS：请允许 Terminal/Python 使用系统自动化与文件选择功能。"
    return " Windows：请从桌面正常启动 SugarAgent；或确认系统文件对话框可用。"


def _picker_unavailable_error(failures: list[str]) -> RuntimeError:
    detail = (" 详情：" + " | ".join(failures)) if failures else ""
    return RuntimeError("无法打开本机文件选择对话框。" + _picker_platform_hint() + detail)


def pick_native_path(
    kind: PathPickKind, initial: str = "", multiple: bool = False
) -> Optional[str] | list[str]:
    """弹出系统文件/目录选择框。用户取消时返回 None。

    兜底规则（2026-10-17）：只有"窗口根本没弹出来"（PathPickerUnavailable /
    ImportError / FileNotFoundError）才换下一个后端。对话框一旦弹出过——成功、
    取消或 PathPickerDialogError——本次选择就到此为止，绝不再弹第二种样式的
    窗口让用户重选一次。
    """
    if kind not in ("file", "directory"):
        raise ValueError("kind 须为 file 或 directory")
    if multiple and kind != "file":
        raise ValueError("multiple=true 仅支持 kind=file")
    if platform.system() == "Linux" and not (
        os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY")
    ):
        raise RuntimeError(
            "Native file picker is unavailable in headless Linux mode. "
            "Enter a path manually or connect through a desktop session."
        )
    if not _pick_lock.acquire(blocking=False):
        raise PathPickerDialogError("已有一个文件选择窗口正在等待操作，请先完成或取消它。")
    try:
        return _pick_native_path_locked(kind, initial, multiple)
    finally:
        _pick_lock.release()


def _pick_native_path_locked(
    kind: PathPickKind, initial: str, multiple: bool
) -> Optional[str] | list[str]:
    if multiple:
        failures: list[str] = []
        try:
            return _pick_tkinter_multi_files(initial)
        except PathPickerDialogError:
            raise
        except (ImportError, FileNotFoundError, PathPickerUnavailable) as e:
            failures.append(f"tkinter: {e}")
        except Exception as e:
            if _is_user_cancelled_exc(e):
                return []
            raise PathPickerDialogError(f"多选文件对话框出错：{e}") from e
        if platform.system() == "Windows":
            try:
                result = _pick_windows_powershell("file", initial, True)
                return result if isinstance(result, list) else ([result] if result else [])
            except PathPickerDialogError:
                raise
            except (ImportError, FileNotFoundError, PathPickerUnavailable) as e:
                failures.append(f"windows-powershell: {e}")
            except Exception as e:
                if _is_user_cancelled_exc(e):
                    return []
                raise PathPickerDialogError(f"多选文件对话框出错：{e}") from e
        single = _pick_native_path_locked("file", initial, False)
        return [single] if single else []

    failures: list[str] = []
    for name, fn in _ordered_backends():
        try:
            result = fn(kind, initial)
        except PathPickerDialogError:
            _remember_backend(name)
            raise
        except (ImportError, FileNotFoundError, PathPickerUnavailable) as e:
            failures.append(f"{name}: {e}")
            continue
        except Exception as e:
            if _is_user_cancelled_exc(e):
                _remember_backend(name)
                return None
            failures.append(f"{name}: {e}")
            # 未知异常时无法确认窗口是否已经弹出：按"已弹出"处理，不再级联。
            raise PathPickerDialogError(str(_picker_unavailable_error(failures))) from e
        _remember_backend(name)
        return result

    raise _picker_unavailable_error(failures)

