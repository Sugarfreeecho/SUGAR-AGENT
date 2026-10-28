# Goal Workflow（agent-goal）

耐久目标：把「做什么、做到什么程度」写进会话状态，模型能自查进度、跨轮续跑，完成时由独立 Judge 审核而不是自己宣布完成。

- 工具：`create_goal`、`get_goal`、`update_goal`。
- 路由：`GET /sessions/{session_id}/goal`、`POST /sessions/{session_id}/goal/{action}`（`pause` / `resume` / `cancel` / `edit` / `delete` / `review`）。
- 会话面板与徽标：面板显示目标、已用 token、剩余额度与最近一次 Judge 结论；徽标在 `active` 与待审核时出现。
- 目录：`host.py`（工具、路由、`SessionWorkflow` 注册）、`runner.py`（Judge 与续跑循环）、`runtime.py`（宿主 workflow 回调）、`web/`（面板渲染）。

属于 `system` 级插件：设置页不显示，随宿主常开。

续跑通过 `session_control.public` 提交持久 continue，复用后端单一执行协调器；Goal 继续拥有目标、Judge、预算和退避。执行前核对目标仍需续跑，执行后按实际 run 对账，等待者退出不取消已接收操作。只读生命周期查询使用公共 HostRuntimeState。

## 热重载

- 改本目录里的代码、前端或 `plugin.json` → 设置页「重新发现 / 热重载」即生效，不必重启：`tool_definitions` 按内容摘要换新模块，`start()` 会重新执行 `runner.py`，`runtime.py` 的回调按摘要重建，`install()` 会先摘掉上一轮注册的 `/sessions/{id}/goal*` 路由再注册。
- 目标存储本体在宿主 `app/agent_goal.py`，改那里必须重启。
- 判定口径见 [插件热重载](../../docs/plugin_hot_reload.md)。

## 目标控制台

打开 `/plugins/agent-goal`，或会话右侧的 Goals 页。独立页面可选择最近会话或输入 ID，支持 `?session=<id>`；右侧页面自动绑定当前会话。

提供目标创建/编辑、暂停/恢复、可选预算与追加预算、取消/删除、Token 与运行诊断、Judge 结论及人工审核。审核可保存、批准移除或带反馈继续执行。自动刷新保留未保存的审核输入，超时后请先刷新核对状态。

控制台采用指标卡片、目标阶段条、Judge 与执行诊断分区及人工验收表单。无目标时显示创建引导；宽屏将引导和表单并排，窄屏按顺序排列。详情栏沿用宿主主题并显示绑定会话名称，不要求重复输入会话 ID。

外观与「刷B站」控制台统一：紧凑固定顶栏、黑色主按钮、灰底与白色卡片、彩色状态胶囊、小型指标格、相同字体和表单间距。详情栏继续支持宿主深色主题。

公共样式、控制台模块和页面桥由 `app/plugin_page_assets.py` 注册白名单静态路由；资源使用重新验证缓存策略，避免热更新后继续命中一小时前的脚本。浏览器测试通过实际 ASGI 资源路由加载页面。

本轮宿主改动需要重启后端。实现与 DSH 对照见 [检查报告](../../docs/goal-agent-team-console-audit-2026-10-27.md)。
