# 子代理任务生命周期与事件循环隔离 · 功能方案设计（UseCase 清单）

- 版本：2026-09-30 v4（覆盖至：当前工作区；父轮通知查询去除无关读取）
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

### UC-2J7 未取得执行权也要终结化
- **触发**：持久化为 `running` 的子代理运行，其后台任务无法启动（启动异常 / 预约丢失），或运行中被打断 / 执行异常。
- **预期现象**：不再滞留"永远运行中"——子会话补写元数据（`subagent_ok=false` + 错误）、追加 `final` UI 事件、写出结果输出文件，并向父级发 `subagent_finish`（ok=false）与对应 pending 结果（`failed` / `interrupted`）；若该子代理已有更新的一次运行接管（注册表仍在运行），陈旧的启动尝试不再改写状态。
- **规则与边界**：取消（`interrupted`）与异常路径同样补写 `final`，子会话历史可直接看到中止原因；中断文本统一为 `Subagent interrupted.`，启动失败为 `Error: subagent <id> failed to start: …`。
- **依据**：`agent_subagent.py::_execute_subagent_run::_fail_before_execution`（前台预约丢失、后台 `start_background` 异常/失败分支）；回归 `::test_background_start_failure_terminalizes_persisted_run`、`::test_foreground_attach_failure_terminalizes_persisted_run`、`::test_subagent_react_exception_is_visible_in_child_history`。

### UC-2J8 首轮先行落盘
- **触发**：子代理运行启动（前台或后台；Runtime V2 主路径或 legacy 路径）。
- **预期现象**：分配给子代理的首条 user 消息在**所有权转交给子 ReAct 之前**已持久化到子会话——Runtime V2 下经 `RuntimeHistoryOps.commit_user_turn`（`operation_id = subagent-user:<run_id>`，UI 文案与模型负载分离）；legacy 下先 append `user` UI 事件并更新会话历史（文案与附件随行）。
- **规则与边界**：首轮提交失败（如元数据被锁）时运行不得静默继续——按终结化路径处理（见 UC-2J9）；提交后的 UI 侧效应刷新失败只告警不阻断（`SessionRepository` 元数据 `replace` 对 Windows 瞬时锁做有界重试）。
- **依据**：`agent_subagent.py::_commit_subagent_initial_turn`；回归 `::test_subagent_initial_turn_failure_releases_reservation_and_terminalizes`。

### UC-2J9 预约期受控与未启动运行的收敛
- **触发**：预约（reserve）已建立、asyncio 任务尚未挂载时收到取消（删除/停止/中断）；或带 `pre_reserved_run_id` 的启动发现归属失效；或更新的运行已接管该子代理。
- **预期现象**：任务挂载前的取消同样生效——落盘中断请求（`request_interrupt`）并释放预约（`unregister`），不存在“已预约但不可取消”的窗口；未启动的失败运行写入任务行 `failed` + 元数据（`subagent_run_status=failed / subagent_ok=false / subagent_error`）+ `final` 事件 + 父级 `subagent_finish`（失败）。
- **规则与边界**：归属按 **run-id** 精确判定（`SubagentTaskRegistry.owns`）——更新的运行已接管时不改写状态、不释放他人预约；重启对账把 `pending` 与 `running` 一视同仁（见 UC-2J6）。
- **依据**：`SubagentTaskRegistry.owns / cancel`、`agent_subagent.py::_fail_unstarted_subagent`、`reconcile_orphaned_subagent_runs`（`pending` 纳入）；回归 `::test_reserved_subagent_can_be_interrupted_before_task_attachment`。

### UC-2J10 结果上报与续跑档案
- **触发**：best-of-n 运行结束汇总结果；或 `task(action='resume')` 续跑既有子代理。
- **预期现象**：best-of 汇总如实报告失败尝试（"finished with errors" + 每个失败原因），不因部分成功而隐藏失败；resume 沿用既有子代理的**工具档案**（如 `explore` + `readonly_strict`），不因续跑回退为默认档案。
- **规则与边界**：只影响结果呈现与续跑参数装配，不改变调度与生命周期语义；resume 仍要求非空 follow-up prompt。
- **依据**：`_format_best_of_results`、`_run_single_subagent`（resume 分支复用既有元数据）；回归 `::test_best_of_result_reports_failed_attempts`、`::test_resume_keeps_existing_explore_and_readonly_tool_profile`。

### UC-2J11 父轮通知领取不装配无关历史

- **触发**：父 Agent 在轮次边界领取或消费 pending 子代理结果。
- **预期现象**：pending 行为空时，在读取父会话 metadata/取得其锁之前返回；给定 `parent_run_id` 时按该 run 精确过滤，不为确定归属生成完整 UI 历史投影。
- **规则与边界**：未提供 parent run ID 的旧调用仍按 final index 与 UI 历史判定；claim/ack/release 及结果耐久性保持。空队列早返回仍要先读取 pending 行，不等于完全没有文件检查。存储落点见 [08/04 · UC-8D8](../08-会话存储RuntimeV2/04-扩展子代理与运行注册方案设计-UseCase清单.md)。
- **依据**：`agent_harness.py::_load_pending_subagent_results / consume_pending_subagent_notifications / claim_pending_subagent_notifications`；`tests/test_agent_harness_reconcile.py`；`subagent_note_claim_timing`。

## 3. 事件与状态不变式

1. 后台任务的生命周期与其创建方的循环解耦：任何父轮临时循环关闭都不构成取消。
2. “创建 + 注册”原子：注册表不会出现调度不达的任务（要么登记成功、要么任务被取消）。
3. 跨循环操作只桥接：等待超时不误取消；取消在 owner 循环执行并结算。
4. 显式停止仍级联取消后台任务；进程退出后的遗留由重启对账收敛为 `orphaned`。
5. 后台运行不依赖父级回调：子事件持久化 + pending 结果构成完整交付通道。
6. 运行必须收敛到终局：启动失败 / 预约丢失 / 中断 / 异常都要终结化（元数据 + `final` 事件 + 输出文件 + 父级通知），不存在"已持久化为 running 但永远无终态"的窗口。

7. 预约即受控、归属精确：任务挂载前的取消同样落盘中断并释放预约；状态改写以 run-id 归属判定（`owns`），陈旧的启动尝试不得覆盖更新的运行。

## 4. 验收

1. `python -m pytest tests/test_agent_subagent_runtime_v2.py -q`：30 passed（v1/v2 见前；2026-09-28 新增：首轮提交失败释放预约并终结化 / 预约期（任务挂载前）可打断 / 子代理事件唤醒子会话页流 / best-of 失败尝试上报 / resume 保持 explore 只读档案）。
2. 独立复现（父轮临时循环与 worker 循环先后关闭）：`workspace/subagent修复核查/复现_子agent循环归属_v2.py`，输出 `复现运行结果_v2.json`——子任务仍完成（pending=completed）、显式取消仍生效（pending=interrupted）。
3. 本批通知查询回归 `tests/test_agent_harness_reconcile.py`：**40 passed**；验证精确 run 过滤、旧调用回退及空队列提前返回。该组与上方子代理生命周期组分别记录，不混作一次全量测试。

## 5. 版本记录

- 2026-09-30 v4：新增 UC-2J11，记录空 pending 不读 metadata、精确 parent run 通知查询跳过完整 UI 投影，以及原领取/确认/释放语义。
- 2026-09-28 v3：新增 UC-2J8《首轮先行落盘》、UC-2J9《预约期受控与未启动运行的收敛》、UC-2J10《结果上报与续跑档案》——首条 user 消息在所有权转交前持久化（Runtime V2 `commit_user_turn` / legacy 双路径）；任务挂载前可打断、未启动失败运行释放预约并终结化；归属按 run-id；对账纳入 `pending`；不变式补第 7 条，验收更新为 30 passed。
- 2026-09-25 v2：新增 UC-2J7《未取得执行权也要终结化》——启动失败/预约丢失的运行不再滞留 `running`：补写元数据、`final` 事件、输出文件与父级 `subagent_finish` 通知；中断/异常路径同样补 `final`；不变式补第 6 条，验收更新为 25 passed。
- 2026-09-20 v1：首版。依据“主 Agent 结束导致后台子代理被中断”的修复补录：进程级持久事件循环托管、创建/注册原子交接、跨循环等待/取消桥接、前后台取消语义与事件通道边界；同步 02 整体设计、ReAct 能力清单、00-总览与 05/04 交叉引用。
