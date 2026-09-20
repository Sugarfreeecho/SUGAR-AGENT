# 子代理任务生命周期与事件循环隔离 · 功能方案设计（UseCase 清单）

- 版本：2026-09-20 v1（覆盖至：当前工作区；后台子代理任务的进程级持久托管）
- 用途：逐条审查（四字段格式）。
- 适用实现：`app/agent_subagent.py`（`_BackgroundSubagentLoop`、`SubagentTaskRegistry`、`_execute_subagent_run`）、`app/agent_subagent_events.py`、`app/agent_loop.py`（`_run_react_node_off_loop`）、`app/webui.py`（取消入口）、`tests/test_agent_subagent_runtime_v2.py`。
- 上级：`00-ReAct运行时整体设计.md`

---

## 1. 功能定位

子代理（task 工具）任务的生命周期与**事件循环归属**协议：后台任务不得随“创建它的父轮临时循环”关闭而被取消；前台任务继续与父任务同生死。本专项同时定义跨事件循环的等待/取消桥接，以及后台运行的事件与结果交付通道。

## 2. UseCase

### UC-2J1 后台子代理任务绑定进程级持久事件循环
- **触发**：`task(run_in_background=true)` 启动子代理后，父轮 ReAct 临时循环（离线程 `asyncio.run`）或聊天 worker 循环结束。
- **预期现象**：子代理继续运行至完成；结果以 pending 结果落账（父会话可见、可续接综合）；不因父轮结束被取消。
- **规则与边界**：后台任务由独立守护线程（`subagent-background-loop`）上的持久事件循环托管，懒启动、进程内复用、不随任何父轮循环关闭；“创建 + 注册”在目标循环上原子完成（同一回调内先建任务后登记），注册被拒或交接被打断时任务立即取消并注销，不存在“已创建但登记不上”的窗口。
- **依据**：`agent_subagent.py::_BackgroundSubagentLoop.submit`、`SubagentTaskRegistry.start_background`、`_execute_subagent_run` 后台分支；回归 `tests/test_agent_subagent_runtime_v2.py::test_background_registry_task_survives_launching_loop_shutdown`、`::test_real_off_loop_task_chain_keeps_background_subagent_alive`。

### UC-2J2 前台与后台的取消语义
- **触发**：删除前台子代理；取消父任务；对后台子代理执行显式停止（会话停止/删除/中断）。
- **预期现象**：删除前台子代理不取消父任务（父收到 interrupted 工具结果后可继续）；取消父任务连带取消前台子代理；后台子代理不随父轮结束中断，但显式停止仍级联取消。
- **规则与边界**：前台任务由专用 Task + `asyncio.shield` 保护，“子级被取消”被翻译成普通工具结果，只有父级真取消才向上传播；后台任务的显式取消经注册表跨循环投递（见 UC-2J4）。
- **依据**：`_execute_subagent_run` 前台分支、`SubagentTaskRegistry.cancel/cancel_for_parent`；回归 `::test_cancelling_parent_still_cancels_foreground_subagent`、`::test_deleting_foreground_subagent_does_not_cancel_parent_task`。

### UC-2J3 跨事件循环等待桥接
- **触发**：从另一个事件循环等待子代理结果（如聊天 worker 等待后台任务、状态查询等待）。
- **预期现象**：完成/异常/取消被复制回等待方；**等待超时或被取消不会取消、不会迁移 owner 循环上的任务**；owner 循环已停时，已完成任务仍返回结果、未完成返回 None。
- **规则与边界**：同循环等待保留原语义（无超时等待被取消会连带取消子任务；带超时用 shield）；跨循环只桥接结果，不改任务归属。
- **依据**：`SubagentTaskRegistry.wait`；回归 `::test_registry_wait_bridges_background_task_from_another_loop`。

### UC-2J4 跨事件循环取消与结算
- **触发**：从非 owner 循环取消后台任务（用户停止、删除子代理、task action=interrupt）。
- **预期现象**：取消请求经线程安全通道投递到 owner 循环执行，等待结算（上限 8 秒）后从注册表注销；任务确实停止。
- **规则与边界**：owner 循环已停时尽力 `cancel()`；结算超时只记警告、不阻塞调用方。
- **依据**：`SubagentTaskRegistry.cancel`。

### UC-2J5 后台运行的事件与结果通道
- **触发**：后台任务运行中产生事件、完成或失败。
- **预期现象**：子事件照常持久化到子会话（可独立回放；运行期约每 15 秒刷新一次子代理心跳状态）；不再向父流实时转发（父循环可能已关闭）；启动瞬间仍向父级发一次 `subagent_start`；完成/失败以 pending 结果 + 任务行状态呈现。
- **规则与边界**：实时转发仅限前台运行（`not run_in_background` 门控）；后台的“可见性”由子会话流与待处理结果承担，不依赖父级回调存活。
- **依据**：`_execute_subagent_run::child_emit`（转发门控）、`_append_parent_pending_result`、`agent_subagent_events.py::should_forward_subagent_event_to_parent`。

### UC-2J6 重启后的孤儿对账
- **触发**：应用重启，上一进程遗留 `running` 子代理任务行。
- **预期现象**：注册表中无对应运行、且记录执行实例不是本进程的遗留行被标记为 `orphaned`（错误态可见），不留“永远运行中”。
- **规则与边界**：本进程实例拥有的行与注册表仍在运行的行跳过；对账在启动生命周期内执行。
- **依据**：`agent_subagent.py::reconcile_orphaned_subagent_runs`、`main.py` 启动时段调用。

## 3. 事件与状态不变式

1. 后台任务的生命周期与其创建方的循环解耦：任何父轮临时循环关闭都不构成取消。
2. “创建 + 注册”原子：注册表不会出现调度不达的任务（要么登记成功、要么任务被取消）。
3. 跨循环操作只桥接：等待超时不误取消；取消在 owner 循环执行并结算。
4. 显式停止仍级联取消后台任务；进程退出后的遗留由重启对账收敛为 `orphaned`。
5. 后台运行不依赖父级回调：子事件持久化 + pending 结果构成完整交付通道。

## 4. 验收

1. `python -m pytest tests/test_agent_subagent_runtime_v2.py -q`：22 passed（含 3 条新增：后台任务跨循环存续 / 真实离线程链路存续 / 跨循环等待桥接）。
2. 独立复现（父轮临时循环与 worker 循环先后关闭）：`workspace/subagent修复核查/复现_子agent循环归属_v2.py`，输出 `复现运行结果_v2.json`——子任务仍完成（pending=completed）、显式取消仍生效（pending=interrupted）。

## 5. 版本记录

- 2026-09-20 v1：首版。依据“主 Agent 结束导致后台子代理被中断”的修复补录：进程级持久事件循环托管、创建/注册原子交接、跨循环等待/取消桥接、前后台取消语义与事件通道边界；同步 02 整体设计、ReAct 能力清单、00-总览与 05/04 交叉引用。
