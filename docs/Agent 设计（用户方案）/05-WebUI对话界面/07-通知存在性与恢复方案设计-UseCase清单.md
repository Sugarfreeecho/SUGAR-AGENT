# 通知、存在性与恢复 · 功能方案设计（UseCase 清单）

- 版本：2026-09-14 v2（覆盖至：HEAD `d022831`）
- 用途：逐条审查（四字段格式）。
- 适用实现：`app/webui.py`（ui-presence / 通知段）、`modules/layout-panels.js`、恢复 runner（`start_react_recovery_runner`）。
- 上级：`00-WebUI对话界面整体设计.md`

---

## 1. 功能定位

"人不在电脑前"的三种保障：桌面通知、存在性上报、意外后的恢复。

## 2. UseCase

### UC-5G1 桌面通知
- **触发**：页面失焦时关键事件（完成/失败/需人工处理）。
- **预期现象**：按配置触发系统通知（同 run 不重复轰炸）；点击通知回到会话；页面聚焦时不打扰。
- **依据**：通知优先级/合并逻辑、`ui-presence` 使用。

### UC-5G2 UI 存在性上报
- **触发**：页面打开/关闭/切前后台。
- **预期现象**：presence 被上报（后端据此决定通知与资源策略）；页面关闭后会话不因此崩溃。
- **依据**：`ui-presence` API、`_ui_presence_has_active`。

### UC-5G3 恢复运行（刷新/重启后）
- **触发**：任一方式重开应用。
- **预期现象**：中断的 ReAct 会话被识别并可**继续跑**（干净续接）；孤儿运行被清理或提示（不放任假"运行中"）。
- **依据**：`recover_interrupted_react_sessions`、`_cleanup_orphan_runtime_v2_active_runs`。

### UC-5G4 客户端计时回传
- **触发**：界面渲染/交互关键点。
- **预期现象**：前端性能数据回传到后端日志（排查用处）；对用户不可见。
- **依据**：`client_timing`。

## 3. 边界

- 通知与流观察者重连（UC-5C3）独立：前者管"提醒"，后者管"数据"。
- 恢复的存储侧依赖见 ../08/06。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-5G1/5G2 | `webui.py` L4388+（presence 工具段；路由 `/api/ui-presence` L4710）、通知段 |
| UC-5G3 | `recover_interrupted_react_sessions` L938+ |
| UC-5G4 | `client_timing` L4305 |

## 5. 版本记录

- 2026-09-14 v2：修正 presence/client_timing 行号并更新版本线至 `d022831`（另：服务端自主运行的自动接管见 05-03 UC-5C5）。
- 2026-09-13 v1：拆分首版（承接 UC-512/514）。
