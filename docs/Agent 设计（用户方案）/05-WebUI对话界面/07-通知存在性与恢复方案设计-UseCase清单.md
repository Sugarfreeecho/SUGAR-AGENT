# 通知、存在性与恢复 · 功能方案设计（UseCase 清单）

- 版本：2026-09-20 v3（覆盖至：HEAD `6cd82d7` + Windows WebUI 启动复用修复）
- 用途：逐条审查（四字段格式）。
- 适用实现：`app/tray_launcher.py`、`app/platform_lifecycle.py`、`app/webui.py`（ui-presence / ui-activation / 通知段）、`modules/message-rendering.js`、`modules/session-management.js`、恢复 runner（`start_react_recovery_runner`）。
- 上级：`00-WebUI对话界面整体设计.md`

---

## 1. 功能定位

"人不在电脑前"和"重新进入界面"两端的保障：桌面通知、页面存在性、已开页面精确复用、启动去重与意外恢复。

## 2. UseCase

### UC-5G1 桌面通知
- **触发**：页面失焦时关键事件（完成/失败/需人工处理）。
- **预期现象**：按配置触发系统通知（同 run 不重复轰炸）；点击通知回到会话；页面聚焦时不打扰。
- **依据**：通知优先级/合并逻辑、`ui-presence` 使用。

### UC-5G2 UI 存在性上报
- **触发**：页面打开/关闭/切前后台。
- **预期现象**：presence 被上报（后端据此决定通知与资源策略）；页面关闭、进入后台或浏览器节能/睡眠后，会话不因此崩溃。
- **规则与边界**：前端打开时注册、每 10 秒刷新、关闭时尽力注销；浏览器节能模式可能冻结 JavaScript 定时器，因此 presence 是通知和激活的辅助信号，不作为 Windows 上"这个标签页一定不存在"的唯一依据。后端激活复用窗口使用 20 秒新鲜度，长期遗留 token 再按配置 TTL 清理。
- **依据**：`message-rendering.js::registerUiPresence/sendUiPresence`、`webui.ui_presence`、`_ui_presence_has_active`、`_ui_presence_has_reusable`。

### UC-5G3 恢复运行（刷新/重启后）
- **触发**：任一方式重开应用。
- **预期现象**：中断的 ReAct 会话被识别并可**继续跑**（干净续接）；孤儿运行被清理或提示（不放任假"运行中"）。
- **依据**：`recover_interrupted_react_sessions`、`_cleanup_orphan_runtime_v2_active_runs`。

### UC-5G4 客户端计时回传
- **触发**：界面渲染/交互关键点。
- **预期现象**：前端性能数据回传到后端日志（排查用处）；对用户不可见。
- **依据**：`client_timing`。

### UC-5G5 已打开 WebUI 精确复用（含节能标签页）
- **触发**：双击托盘、托盘菜单打开 Agent、运行 `RUN.bat` 后自动打开，或点击 `sugaragent://` 桌面通知。
- **预期现象**：已打开的 WebUI 被切到前台，不新增重复标签页；WebUI 位于 Edge/Chrome/Firefox 后台标签或处于节能/睡眠状态时，Windows 会选中该标签并唤醒；已关闭或无法可靠选中的页面才走新开页面回退。
- **规则与边界**：先按顶层窗口标题复用当前标签；找不到时通过 Windows UI Automation 在可见浏览器窗口的 TabItem 中精确匹配 `General Agent` / `SugarAgent`，执行 SelectionItem 选择后再校验前台窗口。禁止仅因存在页面心跳就随便聚焦任意浏览器窗口并宣告成功。UI Automation 被浏览器策略禁用、标签页标题被改写或运行在嵌入式宿主中时，允许回退为新开页面，以"用户确实看到 WebUI"优先。
- **依据**：`tray_launcher._visible_webui_windows`、`_select_webui_browser_tab`、`_focus_existing_webui_tab`、`_bring_window_to_foreground`。

### UC-5G6 启动单一打开者与重复抑制
- **触发**：冷启动、已有托盘下再次运行 `RUN.bat`、陈旧端口监听器被替换，或浏览器冷启动尚未出现窗口。
- **预期现象**：一次启动最多发起一次浏览器打开；陈旧监听器路径只生成一个托盘 daemon；快速双击不会叠出多个窗口，失败后又能较快重试。
- **规则与边界**：托盘启动子进程时固定 `OPEN_BROWSER=0`，首次打开只归 `_auto_open_webui_when_ready` 所有；`run_starter` 仅等待端口/请求驻留托盘重启，不再并行发第二次 UI 激活。浏览器打开槽只抑制 1.5 秒内的并发或双击，不以长时间锁定掩盖失败。
- **依据**：`tray_launcher.run_starter`、`TrayLauncher._start_agent`、`_auto_open_webui_when_ready`、`_claim_ui_open_slot`。

### UC-5G7 忙碌后端激活与可信失败回退
- **触发**：打开/通知激活恰逢后端启动、会话索引或其它同步工作短暂占用事件循环。
- **预期现象**：短暂繁忙不会因为 0.8 秒过早超时而误开重复页面；确实无法复用时不会只聚焦无关浏览器或静默无响应，而会打开目标 URL（通知深链保留 `session`）。
- **规则与边界**：Windows 托盘激活单次 HTTP 超时为 2.5 秒，失败后间隔 0.15 秒再试一次；HTTP `reused=true` 仍必须配合精确标签页选择/前台校验。页面心跳残留、嵌入式页面或 Windows 拒绝前台切换时，记录决策日志并走真实浏览器打开。
- **依据**：`tray_launcher.UI_ACTIVATION_TIMEOUT_SECONDS`、`_request_webui_activation_with_retry`、`_activate_webui_from_external`、`TrayLauncher._open_url`、`platform_lifecycle.request_webui_activation`。

## 3. 边界

- 通知与流观察者重连（UC-5C3）独立：前者管"提醒"，后者管"数据"。
- 页面节能/睡眠影响前端心跳及时性，但不影响后端会话和运行；Windows 复用以 UI Automation 作为独立于页面 JavaScript 的第二信号。
- UI Automation 精确选标签仅适用于 Windows 托盘链；非 Windows 平台继续使用 `platform_lifecycle.open_webui` 的页面心跳复用与默认浏览器回退。
- 修改 `tray_launcher.py` 后，托盘菜单里的"重启"只重启后端子进程，不会重载托盘代码；需先"退出 Agent"再运行 `RUN.bat` 才能让启动器改动生效。
- 恢复的存储侧依赖见 ../08/06。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-5G1/5G2 | `webui.py::ui_presence/_ui_presence_has_active/_ui_presence_has_reusable`、`message-rendering.js::registerUiPresence`、通知段 |
| UC-5G3 | `recover_interrupted_react_sessions` L938+ |
| UC-5G4 | `client_timing` L4305 |
| UC-5G5 | `tray_launcher.py::_select_webui_browser_tab/_focus_existing_webui_tab/_bring_window_to_foreground` |
| UC-5G6 | `tray_launcher.py::run_starter/TrayLauncher._start_agent/_auto_open_webui_when_ready/_claim_ui_open_slot` |
| UC-5G7 | `tray_launcher.py::_request_webui_activation_with_retry/_activate_webui_from_external/TrayLauncher._open_url`、`platform_lifecycle.py::request_webui_activation`、`webui.py::request_ui_activation` |

## 5. 版本记录

- 2026-09-20 v3：新增 UC-5G5~5G7——Windows 精确复用后台/节能 WebUI 标签页（UI Automation）、启动浏览器单一所有者、激活超时放宽与可信失败回退；明确 presence 在浏览器睡眠时只是辅助信号，以及托盘代码需完整退出后重载。
- 2026-09-14 v2：修正 presence/client_timing 行号并更新版本线至 `d022831`（另：服务端自主运行的自动接管见 05-03 UC-5C5）。
- 2026-09-13 v1：拆分首版（承接 UC-512/514）。
