# 运行生命周期与 Goal 续跑防风暴 · 功能方案设计（UseCase 清单）

- 版本：2026-09-20 v2（覆盖至：当前工作区；补充跨进程恢复租约与验证服务隔离）
- 用途：逐条审查 run 身份、终态落盘、看门狗隔离、Goal 续跑租约与失败熔断。
- 适用实现：`app/agent_loop.py`、`app/agent_harness.py`、`app/session_lifecycle.py`、`app/main.py`、`app/webui.py`、`app/agent_goal.py`、`app/execution_metrics.py`、`app/runtime_observability.py`、`plugins/agent-goal/runner.py`、`scripts/subagent_ui_verify.py`。
- 上级：`00-ReAct运行时整体设计.md`

---

## 1. 功能定位

run 从“取得执行权”到“唯一终态”的完整协议，也是 Goal 自动续跑的防重叠与防风暴边界。核心原则是：**控制动作以 `(session_id, run_id)` 为最小身份，任何失败都必须收敛为终态或进入有界退避，不能用会话级取消替代 run 级隔离。**

## 2. UseCase

### UC-2I1 run 身份与精确中断
- **触发**：用户停止、运行时看门狗、Goal 调度器或新 run 接管需要中断某次运行。
- **预期现象**：中断请求和任务取消同时匹配 `session_id + run_id`；旧 run 的迟到中断不会取消同会话内已启动的新 run。
- **规则与边界**：会话级取消仅用于明确要求停止整会话的管理操作；看门狗不得调用会话级批量取消。设置/清除中断都刷新 metadata `updated_at`，清除时移除旧 `interrupt_run_id` 与 `interrupt_reason`，避免 `user_button` 等原因常驻污染下一 run。
- **依据**：`SessionManager.request_interrupt/is_interrupt_requested/get_interrupt_reason`、`session_lifecycle.is_run_active/cancel_run_tasks_by_id`、`main.runtime_watchdog`。

### UC-2I2 写栅栏接管与可解释终态
- **触发**：同一会话出现新的合法 run，旧 run 在检查点发现自己已失去写栅栏。
- **预期现象**：旧 run 停止继续写入，并以 `run_interrupted(reason=superseded_by_new_run)` 收敛；新 run 保持执行权，不被旧 run 的中断标记污染。
- **规则与边界**：栅栏只决定谁可写，不得让旧 run 无终态消失；`cancelled`、`runtime_watchdog`、`user_button` 与 `superseded_by_new_run` 必须保持不同语义。
- **依据**：`_state_run_has_write_fence`、`_state_interrupt_requested`、`_RuntimeV2RunLifecycle`、聊天与 continuation 收尾分支。

### UC-2I3 启动/终结成对与线程耗尽兜底
- **触发**：`run_started` 已提交后，正常完成、异常、取消，或出现 `RuntimeError: can't start new thread`。
- **预期现象**：每个已开始 run 最多写入一个终态（finished / failed / interrupted）；线程池无法再建线程时，生命周期事件退化为当前线程同步追加，避免留下永久 `running` 行。
- **规则与边界**：终态写入有幂等 operation id、有限重试和冲突终态抑制；即使终态持久化失败，指标/观测收尾仍必须执行并带上 reason，随后再上抛错误。
- **依据**：`_RuntimeV2RunLifecycle.commit/_append_once`、`_finalize_agent_run_lifecycle`、`execution_metrics.finish_run`。

### UC-2I4 看门狗只处理真正失联的 run
- **触发**：观测表中 `status=running` 的 run 心跳超过阈值（默认 90 秒）。
- **预期现象**：若本机仍有同一 run 的活动任务，则不判 stale；否则只标记、请求中断并取消该 run，不影响同会话内其他 run。
- **规则与边界**：扫描器只扫描 `running` 行；已标记 `stale` 的历史行不会被再次当作取消源。看门狗没有“总运行时长”硬超时，长任务只要本地任务仍活跃即可继续。
- **依据**：`runtime_observability.scan_stale_runs`、`main.runtime_run_is_locally_active/runtime_watchdog`、`cancel_run_tasks_by_id`。

### UC-2I5 观测线程耗尽时降级而非杀死业务
- **触发**：执行指标、观测刷盘或 power guard 尝试创建后台线程/定时器时失败。
- **预期现象**：诊断能力降级但业务 run 不因此失败；心跳由进程级共享线程统一泵送，不再为每个 run 创建一个原生线程；定时器启动失败时直接同步刷盘。
- **规则与边界**：观测是辅助能力，不能成为 run 启动的硬前置；降级应留下日志且不吞业务终态。
- **依据**：`execution_metrics._heartbeat_pump/_ensure_heartbeat_thread`、`runtime_observability._schedule_write`、`runtime_power.AgentRunPowerGuard`。

### UC-2I6 Goal continuation 租约防重叠
- **触发**：Goal 调度器准备启动下一次 continuation。
- **预期现象**：`current_run_id` 为空且退避到期才允许启动；成功占用后，在该 run 结算前其他调度轮次不得再启动新 run。
- **规则与边界**：`mark_continuation_started` 对重复占用明确报错，`should_continue` 在租约存在时返回 false；run 结算时清除租约。
- **依据**：`GoalManager.mark_continuation_started/should_continue/record_run`。

### UC-2I7 遗留租约先对账再续跑
- **触发**：进程重启或调度器发现 Goal 保留 `current_run_id`，但本地没有对应 worker。
- **预期现象**：若观测仍显示 running，则等待；若终态已存在，或超过宽限期仍没有观测行，则先把旧 continuation 结算为 `interrupted`，进入退避，后续 tick 才可启动替代 run。
- **规则与边界**：不得在同一调度 tick 中“判旧 run 丢失并立即起新 run”；这样可避免旧 run 晚到与新 run 争抢写栅栏。
- **依据**：`plugins/agent-goal/runner.py::_reconcile_incomplete_run/_discover`。

### UC-2I8 interrupted 计入失败、退避与熔断
- **触发**：Goal run 以 `failed`、`error` 或 `interrupted` 结束。
- **预期现象**：`consecutive_failures` 递增并设置指数退避；默认连续 3 次失败后 Goal 自动转为 `paused`，`pause_reason=consecutive_run_failures`。
- **规则与边界**：成功 run 清零连续失败；ReAct 单轮迭代上限 `react_limit` 不计失败，可在新 run 中继续；token budget 仍独立生效。
- **依据**：`GoalManager.record_run`、`GOAL_MAX_CONSECUTIVE_FAILURES`。

### UC-2I9 状态展示不冒充运行事实
- **触发**：Goal 处于 active、continuation 启动，或 run 发生非用户中断。
- **预期现象**：Goal active 使用普通 badge，不显示 activity 脉冲；`Workflow continuation started` 只作为瞬时状态事件，不写入耐久消息历史；只有明确的用户原因才显示“用户中断”，其他原因显示可恢复的运行中断文案。
- **规则与边界**：Goal 状态与 run 状态是两个维度；“目标仍 active”不等于“当前正在运行”。
- **依据**：`plugins/agent-goal/.myagent-plugin/plugin.json`、`agent_loop.py` continuation 状态事件与 `_interrupt_terminal_text`。

### UC-2I10 跨进程恢复扫描不得接管仍存活的 run
- **触发**：同一工作区出现第二个 WebUI 进程；该进程能从 Runtime V2 看到 active run，但自己的进程内任务表中没有对应 worker。
- **预期现象**：恢复扫描先核对 Runtime V2 最近活动和 `runtime_observability.json` 中同一 `run_id` 的共享心跳；任一租约仍新鲜时，不写 `run_interrupted(no_local_activity)`，也不启动替代 recovery run。
- **规则与边界**：`session_lifecycle._run_tasks` 是进程内事实，不能单独证明跨进程孤儿；共享心跳必须绕过本进程缓存直接读盘，并严格匹配 active `run_id + status=running`。Runtime V2 只在事件边界前进，长模型/工具调用期间以约 15 秒一次的观测心跳续租；孤儿清理必须 `respect_grace=True`。只有本地无 exact run、无活动子代理且两类耐久租约都过期，才允许补记终态并恢复。
- **依据**：`webui._discover_recoverable_react_sessions`、`_runtime_v2_active_runs_are_recent`、`_runtime_observability_active_runs_are_recent`、`_cleanup_orphan_runtime_v2_active_runs`、`execution_metrics._heartbeat_pump`。

### UC-2I11 验证服务必须使用隔离工作区
- **触发**：UI/浏览器验证脚本需要临时启动第二个 `uvicorn webui:fastapi_app`。
- **预期现象**：临时服务、测试会话与子代理种子统一落到一次性 `WORK_DIR`；测试结束时先经拥有者服务删除测试会话，再停止服务并清理临时目录，生产 `workspace/sessions` 不发生变化。
- **规则与边界**：子进程设置 `WORK_DIR` 时必须同时设置 `MYAGENT_DOTENV_OVERRIDE=0`，否则正常启动语义中的 `app/.env override=True` 会把显式临时目录改回生产 `./workspace`。默认应用启动仍保持 `.env` 覆盖行为；该开关只供明确隔离的子进程使用。
- **依据**：`agent_harness.load_app_dotenv`、`scripts/subagent_ui_verify.py`、`tests/test_react_recovery_runner.py`。

## 3. 事件与状态不变式

1. 一个 run 的控制身份始终是 `(session_id, run_id)`；reason 不能作为身份。
2. `run_started` 之后必须最终出现且只出现一个耐久终态；快照落后可重建，但不得长期保留 `running`。
3. 看门狗只消费当前 `running` 观测行，并在取消前再次核对本机同 run 活性。
4. Goal continuation 同时最多一个租约；遗留租约必须先对账、计失败和退避。
5. 观测、指标和 UI activity 都不能反向决定业务 run 是否存活。
6. run 终态具有单调性：同一 `run_id` 写入 finished / failed / interrupted 后，不得继续提交模型、工具或上下文事件。
7. “本进程没有 worker”不等于“系统中没有 worker”；多进程场景必须使用耐久的 exact-run 租约判定。

## 4. 历史事故验证基线

### 4.1 会话 dcb36e1a：运行中断风暴

- 原报告关于“接管导致旧 run 在检查点取消”“90 秒 stale 后会话级取消误杀新 run”“线程耗尽会制造未终结 run”“interrupted 未计入 Goal 熔断”的机制判断成立。
- `events.jsonl` 当前可确认 9 条 `run_interrupted(reason=cancelled)`、2 条 90 秒 stale 记录；按 `run_started` 与终态事件直接配对，未闭合 run 为 **7 个**，不是报告中的“8–9 个”。
- stale 扫描只读取 `status=running` 行，因此历史 `stale` 行本身不会被重复消费；自激来源是仍保持 running 的幽灵行叠加会话级取消。
- 当前快照已追平事件尾部且 `active_runs/running_runs=0`；历史上的 seq 2273/2276 延迟说明当时终态/快照收敛不及时，不代表现状仍永久卡住。
- 旧 `scripts/subagent_ui_smoke.py` 已不在当前工作树，当前全局 `.hidden` 与响应式样式块也已存在；原报告第 12–16、19 项保留为历史线索，不作为本轮仍待修缺陷。

### 4.2 会话 5cd95437：第二 WebUI 误接管与过程块抖动

- `seq=644`（17:10:58.631Z）由原 run `f2f739cd…` 发起 `python scripts\subagent_ui_verify.py`；事故版本脚本会在随机端口启动第二个 `uvicorn webui:fastapi_app`，但没有隔离 `WORK_DIR`。
- `seq=645`（17:11:06.411Z）仅约 8 秒后，同一原 run 被写入 `run_interrupted(reason=no_local_activity)`；`seq=647` 随即启动 `react-recovery-4a014…`。
- `seq=649`（17:12:01.991Z）原 `f2f739cd…` 仍写入验证脚本的 `tool_finished`，比其“终态”晚约 55 秒，直接证明 `seq=645` 是假终态。
- 第二次同类矛盾：`react-recovery-59d2…` 在 `seq=688` 被写入 `no_local_activity` 后，仍在 `seq=689–707` 持续提交模型、工具、上下文和 UI 事件，直到 `seq=708/709` 才由 `user_button` 真正停止。
- `no_local_activity` 的写入链唯一落在 `webui._discover_recoverable_react_sessions → _cleanup_orphan_runtime_v2_active_runs → RuntimeMirror.mirror_run_interrupted`；与进程内 `_run_tasks` 的可见性边界及验证脚本第二服务启动时机一致。
- 前端把 `run_interrupted` 视为终态并执行 `endRunForClient`，而后续 active snapshot/事件又会触发历史恢复与过程块重新标记 `is-running`；“终态收起—活动重挂”的矛盾解释了无新增内容与高频抖动。该 UI 因果为事件序列与状态机共同推导，第二进程、假终态及终态后继续写入则是耐久日志中的直接事实。
- 刷新无法自愈：错误终态已经写入 `events.jsonl`，页面刷新只会重放同一组矛盾历史。

## 5. 验收

1. 构造同会话旧 run stale、新 run 活跃：看门狗只能取消旧 run。
2. 模拟 `asyncio.to_thread` 抛出 `can't start new thread`：仍能写入唯一终态。
3. 连续三次以 interrupted 结算 Goal：应依次退避，并在第三次自动 paused。
4. 保留 `current_run_id` 且移除本地 worker：首次发现只做对账，不在同 tick 启动替代 run。
5. 长任务超过 stale 阈值但本地 exact run task 活跃：不得被看门狗标 stale。
6. 用第二进程模拟“本地 task 表为空、共享 exact-run 心跳新鲜”：不得清理 active run，也不得启动 recovery。
7. 让 Runtime V2 在长工具调用期间无新事件、只刷新 `runtime_observability` 心跳：跨进程恢复扫描仍必须跳过。
8. 运行 `scripts/subagent_ui_verify.py` 前后对生产会话 `events.jsonl` 做哈希和行数比对；必须完全不变，且临时会话/目录全部清理。

## 6. 版本记录

- 2026-09-20 v2：补录会话 5cd95437 的第二 WebUI 误接管证据链；新增跨进程 exact-run 租约、共享心跳直接读盘、孤儿宽限保护及验证服务 `WORK_DIR` 隔离契约。
- 2026-09-20 v1：依据中断风暴排查新增；记录 run 级看门狗、终态兜底、共享心跳、Goal 租约/对账/熔断及 UI 状态语义，并校正历史统计口径。
