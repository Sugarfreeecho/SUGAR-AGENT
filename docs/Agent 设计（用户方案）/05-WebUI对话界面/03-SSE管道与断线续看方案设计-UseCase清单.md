# SSE 管道与断线续看 · 功能方案设计（UseCase 清单）

- 版本：2026-10-07 v7（覆盖至：当前工作区；压缩 reasoning 活动流续接）
- 用途：逐条审查（四字段格式）。
- 适用实现：`modules/sse-handling.js`（3.6k 行）、`modules/event-dispatch.js`、后端 `runtime_v2_session_stream`。
- 上级：`00-WebUI对话界面整体设计.md`

---

## 1. 功能定位

界面的"生命线"：SSE 事件如何到达、如何续、如何防重复——参数全部显式。

## 2. UseCase

### UC-5C1 实时事件流
- **触发**：会话运行中（含新建未入库会话）。
- **预期现象**：事件按序到达并驱 UI；发送管线锁防止"新旧事件交错"；无事件丢失或重复上屏；工具执行期的运行中命令输出以 ephemeral 增量事件（`tool_command_delta`）下发，工具结果下行取**限长 UI 投影**（`tool_detail_ui`）而非原始模型结果。
- **依据**：`sse-handling.js`（send pipeline 锁、事件应用）。

### UC-5C2 断线续看
- **触发**：网络闪断/代理切断/后台休眠导致 SSE 中断。
- **预期现象**：自动重连续看——**空闲 120s 触发探测、重连 ≤10 次、退避 0.5s→15s**；从上次游标继续（不丢不重）；次数耗尽后明确提示"刷新页面"。
- **规则与边界**：续看靠后端游标（after_seq/after_index），不是内存重放；提示写入界面日志（error-log）不弹窗轰炸。服务端**自主续跑**（如 goal 工作流）另由 5 秒心跳提示并自动接管（见 UC-5C5）。
- **依据**：`sse-handling.js` 顶部常量（SSE_IDLE_TIMEOUT_MS / STREAM_RECONNECT_MAX_ATTEMPTS 等）、`runtime_v2_session_stream`。

### UC-5C3 观察者重连（多视图）
- **触发**：同一会话在多个视图（主界面/子代理视图）同时打开。
- **预期现象**：各视图独立续看；互不拖垮；开关受 `MYAGENT_ENABLE_STREAM_RECONNECT` 控制；观察者流会把 `extension_state_changed` 以 `ephemeral+control_event` 转发，前端消费后派发 `myagent:extension-state-changed` 刷新扩展面板，且**不推进** UI 投影游标。
- **依据**：`streamReconnect` 配置、观察者流设计（webui L190）、`_observer_extension_control_event`。

### UC-5C4 事件回放一致性
- **触发**：刷新页面 / 打开历史会话。
- **预期现象**：已渲染内容与历史一致（含已撤销/已恢复类状态）；不发生"重放重复执行"（回放只读）。
- **依据**：`event-dispatch.js`、change-review 前端历史扫描（`plugins/change-review/web/change-review.js::scanExisting`）。

### UC-5C5 服务端自主运行自动接管
- **触发**：服务端自发的续跑/恢复运行（如 goal 工作流 `workflow-runner-*`），当前会话被打开且本地无流。
- **预期现象**：≤5 秒内浏览器自动挂接观察流并开始渲染新事件；已手动停止（stop suppress）或已在流中的会话不被重复接管。
- **规则与边界**：由 5 秒心跳 `GET /api/runtime-status` 的 `active_session_ids` 驱动（`maybeTakeOverActiveRuntimeSession`），接管时伴随一次扩展状态收敛刷新；不改变"停止/插话"语义。
- **依据**：`webui._runtime_status_payload`、`session-management.js`（心跳接管）、`sse-handling.js::attachSessionEventStream`。

### UC-5C6 终态单调与恢复接管一致性
- **触发**：SSE/历史回放收到 `run_finished`、`run_interrupted` 或 `run_failed`，或页面根据 runtime-status 重新挂接服务端自主运行。
- **预期现象**：终态到达后前端结束该 run、封口过程块并记录 terminal run；只有不同的新 run 才能重新进入活动状态。同一 `run_id` 不得在终态后继续产生模型/工具/上下文事件。
- **规则与边界**：前端把终态视为不可逆事实；后端恢复扫描必须用跨进程 exact-run 租约避免制造假终态。若耐久历史已经存在“同 run 终态后继续写入”，刷新只会重放矛盾状态，不能作为修复手段；应先修复事件生产者/恢复接管路径，不得用高频强制重绘掩盖。
- **依据**：`session-event-reducer.js` 的 terminal run 归约、`sse-handling.js::endRunForClient/attachSessionEventStream`、`webui._discover_recoverable_react_sessions`。

### UC-5C7 子代理会话的流唤醒与收流
- **触发**：打开/观察一个由 task 托管运行的子代理会话（非主聊天运行）。
- **预期现象**：事件到达更及时——心跳间隔由通常的 15s 缩短为 1s（仅子代理执行中的会话）；超时先重抽投影并下发增量；**无本地 worker 活动**时以 `[DONE]` 正常收流（不留僵尸观察流），仍有活动则继续等待。
- **规则与边界**：只作用于子代理执行中的会话；普通会话维持原心跳/keepalive 行为；收流由“无本地 worker”而非猜测驱动，与 UC-5C6 的终态单调性不冲突。
- **依据**：`webui.py::stream_session_events`（`_is_subagent_execution_active` / `_has_local_worker_activity` 判定）。

### UC-5C8 模型临时增量的有序异步桥接

- **触发**：离线程 Agent 向主循环发布明确为 ephemeral 的 `llm_reasoning_delta / llm_response_delta / tool_call_delta`。
- **预期现象**：生产者入队即返回；一个 drain 按队列顺序向原事件出口发送。仅合并同身份的相邻增量，正文/思考 `delta`、工具 `name_delta / arguments_delta` 按原顺序拼接，最新序列元数据保留，内容不丢。
- **规则与边界**：
  - 身份同时匹配 `type / session_id / run_id / react_iter / stream_seq / index / tool_call_index / id / tool_call_id`；不同身份、非相邻或跨确认事件的增量不合并。入队复制事件字典，调用方之后修改字典不改变待投递事件。
  - 只有上述三个明确的临时增量类型走无确认入队；完整工具事件、其他状态/终态事件仍按序等待确认，不能越过此前增量。耐久提交仍由调用方执行。
  - 正常/异常退出先排空；`_prune_stream_ephemeral` 在删除重连草稿前先 flush，避免迟到增量重新生成被中断/完成轮的草稿。flush 只确认先前队列已处理，不替代 Runtime V2 耐久提交。
  - 临时增量投递异常尽力记录，确认事件异常传回发送方；普通发送异常后继续处理后续队列。循环取消/关闭走队列失败路径。该队列没有新增硬容量限制，仍须观察积压与排空耗时。
- **依据**：`app/stream_event_bridge.py::StreamEventBridge`、`agent_loop.py::_run_react_node_off_loop / _prune_stream_ephemeral`；`tests/test_stream_event_bridge.py` 覆盖阻塞 UI 时 1,000 条增量入队、完整工具事件等待、内容与身份/顺序、错误、异常退出排空及清理后无迟到草稿。

桥接只改变后端交付调度，浏览器游标/断线回放仍遵守 UC-5C2/5C4。生产者等待和实际投递分别记录，字段与验收口径见 [09/04 · UC-9D10](../09-横切能力/04-观测与运行看板方案设计-UseCase清单.md)；当前生产提速结论见 [09/05](../09-横切能力/05-性能优化基线与已完成项方案设计-UseCase清单.md)。

### UC-5C9 压缩 reasoning 活动流续接
- **触发**：本地摘要流在 reasoning 增量期间发生 SSE 断线重连，或同一运行的另一个观察流接入。
- **预期现象**：重连后可从进程内聚合的累计 reasoning 快照恢复当前“压缩思考”行；前端以快照替换已有草稿，不重复拼接；收到该次摘要请求的结束事件后清除活动快照，后续不会把已结束思考当作活跃内容再次恢复。
- **规则与边界**：快照仅服务于活动运行期，非 Runtime V2 耐久事件，不用于刷新历史会话恢复已结束的 reasoning。结束/清理按压缩请求身份收束，失败候选和下一次重试保持独立；reasoning 的生产端及展示规则见 09/01·UC-9A11 与 05/02·UC-5B10。
- **依据**：`session_event_bus.py` 的活动 reasoning 聚合/结束清理、`webui.py` 的运行态投影、`sse-handling.js` 与 `session-event-reducer.js` 的快照归并。

## 3. 边界

- 与"运行日志文件"无关：这里是界面流；
- 网关/服务面细节见 ../08-会话存储RuntimeV2/06。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-5C1 | `sse-handling.js` L40–120（锁） |
| UC-5C2 | 常量区 L1–24 + 重连逻辑 |
| UC-5C3 | `webui.py` L190/1736；`_observer_extension_control_event` |
| UC-5C4 | `event-dispatch.js` |
| UC-5C5 | `webui._runtime_status_payload`；`session-management.js` 心跳接管 |
| UC-5C6 | `session-event-reducer.js` 终态归约；`sse-handling.js` 终结/重挂；`webui.py` 跨进程恢复租约 |
| UC-5C7 | `webui.py::stream_session_events`（子代理执行判定 / 无本地 worker 收流） |
| UC-5C8 | `StreamEventBridge`、`_run_react_node_off_loop`、`_prune_stream_ephemeral` |

## 5. 版本记录

- 2026-10-07 v7：新增 UC-5C9，明确压缩 reasoning 只在活动期保留累计快照供 SSE 重连恢复；前端以快照替换草稿，结束即清除，不进入耐久历史。
- 2026-09-30 v6：新增 UC-5C8，补录三个模型临时增量的异步排队、同身份相邻合并、其他事件确认、退出排空与草稿清理屏障；不改变耐久回放游标。
- 2026-09-28 v5：新增 UC-5C7《子代理会话的流唤醒与收流》——子代理执行中的会话心跳缩短为 1s 并优先重抽投影，无本地 worker 活动时正常 `[DONE]` 收流。
- 2026-09-21 v4：补记工具命令输出增量事件（`tool_command_delta`，ephemeral、节流）与工具结果限长投影（`tool_detail_ui`）；工具调用增量在桥接层按帧合并后下发。
- 2026-09-20 v3：新增 UC-5C6，确立 run 终态单调性；记录假 `no_local_activity` 与后续同 run 事件会造成终结/重挂振荡，明确修复必须落在跨进程恢复接管端。
- 2026-09-14 v2：补录服务端自主运行自动接管（UC-5C5）与扩展状态控制事件（UC-5C3）；澄清 scanExisting 归属；更新版本线至 `d022831`。
- 2026-09-13 v1：拆分首版（承接 UC-505）。
