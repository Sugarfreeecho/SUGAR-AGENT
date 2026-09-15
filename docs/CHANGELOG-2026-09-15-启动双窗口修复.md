# CHANGELOG — 2026-09-15 启动双窗口修复

## 现象

从 RUN.bat 启动 Agent 时，浏览器自动弹出**两个路径相同的前端窗口**（托盘常驻图标正常，仅前端重复）。

## 根因

- `bbc70b0` 为托盘增加了 `_auto_open_webui_when_ready` 自动打开线程：端口就绪后由托盘打开 WebUI（后端进程以 `OPEN_BROWSER=0` 启动）。
- 与此同时，RUN.bat 的 `run_starter` 在端口就绪后仍会调用 `_activate_webui_from_external()`，通过 `WM_RESTORE_TRAY` 让托盘“再打开一次”。
- 两条触发几乎同时发生，且都落在“尚无可见窗口”的判定窗口内（浏览器冷启动、页面标题就绪之前），现有的“可见窗口去重 / 页面心跳复用”都拦不住，于是各拉起一个浏览器窗口。

## 修复

`app/tray_launcher.py`：

- 新增 5 秒级浏览器打开去重：常量 `UI_OPEN_DEDUPE_SECONDS` + 进程内 `_claim_ui_open_slot()` / `_release_ui_open_slot()`。
- 只在“确实要新开浏览器窗口”的分支生效；复用 / 聚焦已打开页面的原有逻辑不变。
- 被拦下的重复请求写入日志：`Duplicate UI open request ignored; the browser was launched a moment ago`。
- 浏览器启动抛异常时释放槽位，允许下一次请求立即重试。

`tests/test_tray_launcher.py`（新增 3 个用例）：

- 重复触发只启动一次浏览器；
- 启动失败后可立即重试；
- 去重窗口过期后允许再次打开。

## 验证

- `python -m pytest -q -k "tray_launcher"`：**19 passed**（模块内全部用例）。
- `git diff --check`：通过（无空白错误）。

## 影响范围

- 仅 Windows 托盘启动链（RUN.bat → `app/tray_launcher.py`）。
- Unix / macOS 启动链（`platform_tray*.py`）未改动。
- 改动尚未提交，留在工作区与其它未跟踪改动并存。
