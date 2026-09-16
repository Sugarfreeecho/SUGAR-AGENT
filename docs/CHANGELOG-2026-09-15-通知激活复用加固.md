# CHANGELOG — 2026-09-15 通知激活复用加固

## 现象

点击系统通知打开前端时，有时会**新开一个浏览器标签/窗口**，而已打开的 WebUI 页面仍然开着（没有复用）。

## 排查结论

- Windows 协议注册 `HKCU\Software\Classes\sugaragent` 正确指向 `python\pythonw.exe app\tray_launcher.py --activate-ui "%1"`，`pythonw.exe` 存在。
- 重启（20:23）后一段时间内没有激活访问日志、`activation_seq` 为 0；但 20:50–20:53 用户实测点击时多次出现 `POST /api/ui-activation` 200，且 `activation_seq` 升至 4 —— 链路本身可用，复用正常。
- 修正判断：超时/被取消的请求不会留下访问日志，**"没有日志"不等于"没有请求"**。先前的新开标签症状更可能是激活请求偶发超时（客户端 0.8 秒超时），而旧代码一次失败即回退到"新开标签"，且没有重试。
- 复用判定依赖三个信号：后端页面心跳（20 秒内）、窗口标题匹配（`General Agent` / `SugarAgent`）、窗口枚举。任一环节瞬断都会退化成"新开标签"。

## 改动（`app/tray_launcher.py`）

1. **激活请求重试**：`_request_webui_activation_with_retry()` 对 `/api/ui-activation` 连续尝试两次（间隔 0.15 秒）；把"后端一时繁忙"与"确实没有打开页面"区分开，避免一次瞬断就落到"新开标签"。`--activate-ui` 通知路径与托盘打开路径都已切换。
2. **浏览器窗口兜底**：新增 `_visible_browser_windows()` / `_focus_any_browser_window()`。当后端确认存在活的页面心跳、但标题匹配或聚焦失败时，按浏览器窗口类（`Chrome_WidgetWin_1` / `MozillaWindowClass`）聚焦现有浏览器窗口，而不是新开标签。
3. **决策日志**：新增 `UI activation: ...` 日志行（复用成功 / 按类聚焦 / 最终新开页面），下次复现可直接定位断点。

## 验证

- `python -m pytest -q -k "tray_launcher"`：**21 passed**（新增 2 个：重试、按类聚焦兜底）。
- `git diff --check`：通过。

## 后续

点击通知若再出现"新开标签"，请查看 `logs/agent_terminal.log` 中 `UI activation:` 行反馈，即可确认断在"请求未达后端"还是"窗口识别"环节。用户 20:50–20:53 的实测未再复现。
