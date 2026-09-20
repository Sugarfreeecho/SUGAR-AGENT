# SSE 管道与断线续看 · 功能方案设计（UseCase 清单）

- 版本：2026-09-20 v3（覆盖至：当前工作区；补充终态单调性与跨进程恢复接管边界）
- 用途：逐条审查（四字段格式）。
- 适用实现：`modules/sse-handling.js`（3.6k 行）、`modules/event-dispatch.js`、后端 `runtime_v2_session_stream`。
- 上级：`00-WebUI对话界面整体设计.md`

---

## 1. 功能定位

界面的"生命线"：SSE 事件如何到达、如何续、如何防重复——参数全部显式。

## 2. UseCase

### UC-5C1 实时事件流
- **触发**：会话运行中（含新建未入库会话）。
- **预期现象**：事件按序到达并驱 UI；发送管线锁防止"新旧事件交错"；无事件丢失或重复上屏。
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

## 5. 版本记录

- 2026-09-20 v3：新增 UC-5C6，确立 run 终态单调性；记录假 `no_local_activity` 与后续同 run 事件会造成终结/重挂振荡，明确修复必须落在跨进程恢复接管端。
- 2026-09-14 v2：补录服务端自主运行自动接管（UC-5C5）与扩展状态控制事件（UC-5C3）；澄清 scanExisting 归属；更新版本线至 `d022831`。
- 2026-09-13 v1：拆分首版（承接 UC-505）。
