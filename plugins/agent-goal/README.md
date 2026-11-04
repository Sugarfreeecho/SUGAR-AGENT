# Goal Workflow（agent-goal）

耐久目标：把「做什么、做到什么程度」写进会话状态，模型能自查进度、跨轮续跑，完成时由独立 Judge 审核而不是自己宣布完成。

- 工具：`create_goal`、`get_goal`、`update_goal`。
- `update_goal(status="continue", reason="阻塞已解除")` 可让模型恢复当前暂停或阻塞的目标，效果与 ▶ 相同：保留目标和进度、清除停止标记、重置阻塞累计并恢复自动续跑。预算耗尽时需用户明确授权后传 `additional_budget`；手动暂停只在用户要求恢复时继续。已完成或取消的目标不能通过此操作重启。
- 路由：`GET /sessions/{session_id}/goal`、`POST /sessions/{session_id}/goal/{action}`（`pause` / `resume` / `cancel` / `edit` / `delete` / `review`）。
- 会话面板与徽标：面板显示目标、已用 token、剩余额度与最近一次 Judge 结论；徽标在 `active` 与待审核时出现。
- 目标阻塞后，会话侧栏与输入框上方的 Goal 操作条均显示「继续 Goal」。点击后保留原目标和进度并重新续跑；预算耗尽时先追加预算，阻塞累计从零重新计算。
- 「暂停 Goal」只关闭后续 Goal 检查、Judge 与自动续跑，当前正在执行的任务（含 Goal 发起的续跑）继续到本轮结束；仍记录本轮用量和结果。它不会设置会话中断标记。「取消目标」保留停止当前任务的行为。
- 点击 ▶ / 暂停后立即显示进度提示，两处入口同步反馈并避免重复提交；成功提示保留 5 秒，失败显示具体原因并允许重试。请求超时会提示先刷新确认状态。
- 两轮之间显示「本轮收尾 → 等待下一轮 → 续跑已排队 → 准备下一轮 → 正在请求模型」，并显示当前阶段用时；人工停止、待用户处理和重试分别提示。`GET /sessions/{id}/goal/progress` 提供无对话内容的精简阶段快照，等待期间最多每 2 秒查询一次，执行期间每 15 秒校准，离开页面终止查询。
- 已知活跃 Goal 优先提交续跑，再做每分钟的全量会话发现；已接收的执行操作独立唤醒共享派发器，不必等待规则扫描或其他会话的事件维护。每会话执行租约、持久去重、暂停/停止和预算检查仍在派发前生效。
- `goal_scheduler`、`control_dispatch`、`control_run_prepare`、`queued_turn_handoff`、`post_final_handoff` 的慢阶段只记录标识与耗时；可用 `scripts/diagnose_goal_handoff.py` 只读分析历史交接。调度器与派发器的宿主改动需重启服务后加载。
- 目录：`host.py`（工具、路由、`SessionWorkflow` 注册）、`runner.py`（Judge 与续跑循环）、`runtime.py`（宿主 workflow 回调）、`web/`（面板渲染）。

属于 `system` 级插件：设置页不显示，随宿主常开。

续跑通过 `session_control.public` 提交持久 continue，复用后端单一执行协调器；Goal 继续拥有目标、Judge、预算和退避。执行前核对目标仍需续跑，执行后按实际 run 对账，等待者退出不取消已接收操作。只读生命周期查询使用公共 HostRuntimeState。

## 热重载

- 改本目录里的代码、前端或 `plugin.json` → 设置页「重新发现 / 热重载」即生效，不必重启：`tool_definitions` 按内容摘要换新模块，`start()` 会重新执行 `runner.py`，`runtime.py` 的回调按摘要重建，`install()` 会先摘掉上一轮注册的 `/sessions/{id}/goal*` 路由再注册。
- 目标存储本体在宿主 `app/agent_goal.py`，改那里必须重启。
- 重建 Goal 监听前会让旧的撤销回调完成代际捕获，避免较早版本宿主在同一轮事件循环中误删新监听。共享监控器也已修正同轮撤销的捕获时机；这部分宿主修正会在下次服务重启时加载。
- 判定口径见 [插件热重载](../../docs/plugin_hot_reload.md)。

## 目标控制台

入口为「设置 → Goal 目标」，也可直接打开 `/settings#plugin:agent-goal:main`。从聊天打开设置会自动绑定当前会话，页内仍可选择其他会话。原独立地址 `/plugins/agent-goal?session=<id>` 保留兼容，详情栏不再列出此控制台。

提供目标创建/编辑、暂停/恢复、可选预算与追加预算、取消/删除、Token 与运行诊断、Judge 结论及人工审核。审核可保存、批准移除或带反馈继续执行。自动刷新保留未保存的审核输入，超时后请先刷新核对状态。

控制台采用指标卡片、目标阶段条、Judge 与执行诊断分区及人工验收表单。无目标时显示创建引导；宽屏将引导和表单并排，窄屏按顺序排列。原生设置分区使用宿主的卡片、输入框、按钮和主题，显示绑定会话名称，不要求重复输入会话 ID。

独立页外观与「刷B站」控制台统一：黑色主按钮、灰底与白色卡片、彩色状态胶囊、小型指标格、相同字体和表单间距。原生设置直接沿用设置组件和深色主题，不再加载 iframe 或独立页顶栏。

公共样式、控制台模块和页面桥由 `app/plugin_page_assets.py` 注册白名单静态路由；资源使用重新验证缓存策略，避免热更新后继续命中一小时前的脚本。浏览器测试通过实际 ASGI 资源路由加载页面。

目标存储等宿主改动仍需重启；本次原生设置迁移通过目录热刷新和重载主界面生效。实现与 DSH 对照见 [检查报告](../../docs/goal-agent-team-console-audit-2026-10-27.md)。

原生入口由 `web/settings.js` 的 `mountSettings` 提供；独立页与原生设置共用 `web/view.js` 和可挂载的 `web/app.js`，离开分区时清理控制器及请求。
