# General Agent Runtime V2 Design

## 目标

Runtime V2 是一套旁路运行时内核，目标是在不直接拆改现有 General Agent 主流程的前提下，吸收 Claude Code、OpenClaw 和 Codex 本地会话落盘方式的经验，先建立一套可测试、可镜像、可逐步接管的运行状态与事件系统。

它不替换现有 Agent loop、工具系统、技能系统和前端 UI。第一阶段只新增独立模块和测试，等稳定后再通过镜像写入、只读调试接口、局部替换等方式逐步接入。

## 学习对象

### Claude Code

Claude Code 的价值主要在工程可靠性：

- 历史记录以追加日志为核心。
- 工具权限有明确规则。
- 运行结束、异常、退出有清理路径。
- 本地状态倾向于可恢复、可追踪。

Runtime V2 学习它的重点不是 CLI 形态，而是：

- append-only event log。
- 权限规则 allow / deny / ask。
- 失败必须有终态事件。
- 本地日志能作为恢复依据。

### OpenClaw

OpenClaw 的价值主要在控制平面：

- Gateway 统一接入消息与运行状态。
- 事件发布与订阅解耦。
- 运行时健康检查和恢复。
- 多会话、多代理、多渠道状态隔离。

Runtime V2 学习它的重点是：

- RuntimeGateway 作为后端事实入口。
- StreamPublisher 统一广播事件。
- HealthMonitor 修复孤儿 run 和超时 heartbeat。
- Repository 层隔离文件细节。

### Codex 本地 sessions

本地观察到 Codex 会话目录按日期分层：

```text
.codex/sessions/YYYY/MM/DD/rollout-...jsonl
```

单个会话文件是 JSONL transcript，每行包含：

```json
{"timestamp":"...","type":"event_msg","payload":{"type":"task_started"}}
```

Runtime V2 采用同类思路：

- 一个会话一个主事件日志。
- 每次事实变化追加一行。
- 刷新、恢复、调试都以事件日志为基础。
- 额外增加 `seq`、`run_id`，支持 Web UI、SSE 重连和子 Agent 归属。

## 核心原则

1. 事件日志是事实源。
2. 运行状态只能来自 RunRegistry 或从事件日志重建。
3. SSE 只广播事件，不维护事实。
4. 前端只消费 snapshot 和 event，不猜运行状态。
5. metadata、snapshot、index 都是缓存，可从事件日志重建。
6. 子 Agent 状态必须有明确 final、failed、consumed 事实。
7. 异常、停止、断线、进程退出都必须形成终态事件。

## 推荐落盘结构

```text
workspace/sessions/{session_id}/
├── metadata.json
├── events.jsonl
├── snapshots/
│   └── latest.json
├── blobs/
│   └── {sha256}.txt
└── subagents/
    └── {agent_id}/
        ├── metadata.json
        ├── events.jsonl
        ├── snapshots/
        │   └── latest.json
        └── blobs/
            └── {sha256}.txt
```

全局索引：

```text
workspace/sessions/index.json
```

其中：

- `events.jsonl` 是唯一核心事实源；暂缓事件日志分段，除非有真实性能数据证明必须引入。
- `metadata.json` 保存标题、归档、置顶、更新时间等快速字段。
- `snapshots/latest.json` 是加速恢复的派生数据。
- `blobs/` 保存大工具输出、长文本、附件等；镜像路径会把超过阈值的工具/legacy 文本外置为 `*_ref`。
- `subagents/{agent_id}/` 保存子 Agent 独立事件日志、快照、metadata；父会话只保留瘦身后的索引/状态事件。
- `index.json` 只加速左侧列表，可重建。

## 标准事件

基础结构：

```json
{
  "seq": 1,
  "timestamp": "2026-06-13T12:00:00.000Z",
  "type": "run_started",
  "session_id": "session-id",
  "run_id": "run-id",
  "payload": {}
}
```

第一批事件类型：

```text
session_meta
message_user
message_assistant_delta
message_assistant_final

run_started
run_heartbeat
run_finished
run_failed
run_interrupted

tool_started
tool_delta
tool_finished
tool_failed

subagent_started
subagent_progress
subagent_finished
subagent_failed
subagent_result_consumed

context_tokens
context_summary_started
context_summary_finished
todo_updated
```

## 新模块

```text
app/runtime_v2/
├── __init__.py
├── event_schema.py
├── event_log.py
├── run_registry.py
├── stream_publisher.py
├── session_repository.py
├── subagent_repository.py
├── permission_manager.py
├── health_monitor.py
└── gateway.py
```

## 分阶段接入

### 阶段 A：只新增，不接入

完成：

- RuntimeEvent 数据结构。
- SessionEventLog 追加、读取、修复。
- RunRegistry 运行态管理。
- StreamPublisher 发布订阅。
- RuntimeGateway 统一入口。
- RuntimeProjector 从 events.jsonl 重建 session/run/subagent 快照。
- SnapshotStore 写入可重建快照缓存。
- 基础单元测试。

风险：

- 不影响现有功能。

当前状态：

- 已完成第一版阶段 A 旁路内核。
- 已覆盖 run finished / failed / interrupted 投影。
- 已覆盖坏行 repair、并发 append seq 单调性、publisher 收事件、snapshot rebuild。
- 尚未接入现有 General Agent 主流程。

### 阶段 B：镜像写入

现有 General Agent 继续照旧写 `ui_events.json` 和 SSE，同时 Runtime V2 旁路写 `events.jsonl`。

目标：

- 对照旧系统和 V2 的运行终态。
- 找出异常、停止、刷新不一致来源。

当前接入范围：

- `SessionManager.append_ui_event()` 会把旧 `user`、`final`、context/todo、subagent、tool 等事件镜像为 Runtime V2 事件。
- `agent_loop.astream_events()` 会把主对话 run started / finished / failed / interrupted 镜像为 Runtime V2 run 事件。
- `agent_loop.astream_events_continuation()` 会把续接 run started / finished / failed / interrupted 镜像为 Runtime V2 run 事件。
- Runtime V2 镜像失败只写 debug，不影响旧流程。
- Runtime V2 镜像日志写在现有 session 目录下的 `events.jsonl`，快照写在 `snapshots/latest.json`。
- Snapshot 采用增量投影：正常追加时用旧 snapshot + 新 event 更新，缺失或损坏时再全量重放。
- Subagent 事件会写入父会话 `subagents/{agent_id}/events.jsonl`，父会话主日志只保留瘦身索引事件。
- 工具结果、legacy 事件中的超长文本会外置到 `blobs/{sha256}.txt`，事件 payload 中保留引用。
- EventLog 提供 `read_latest(limit)`、`read_before_seq(before_seq, limit)`、`read_after_seq(after_seq)`，作为后续前端分页和 SSE 重连的按需读取基础。

### 阶段 B2：原生历史操作与对比

阶段 B2 不重复旧 truncate，也不把旧 `ui_events.json` 的裁剪结果写回 Runtime V2。

Runtime V2 采用 append-only 操作事件：

- `message_deleted`
- `message_rewritten`
- `history_branch_created`
- `history_compacted`
- `context_summary_committed`
- `visible_range_changed`
- `model_window_changed`

Projector 根据这些事件生成：

- `messages`：原始消息流，不物理删除。
- `visible_messages`：当前前端可见历史。
- `model_messages`：当前可组装给模型的历史，支持压缩摘要替代早期消息。

新增对比脚本：

```text
python scripts/compare_runtime_v2_session.py <session_id>
```

它只读旧 `ui_events.json` 和 Runtime V2 投影，输出缺失、额外、重复、顺序差异。用途是定位旧路径与 V2 投影从哪一步开始分叉。

### 阶段 C：只读调试接口

新增：

```text
GET /runtime-v2/state
GET /runtime-v2/sessions/{id}/events
GET /runtime-v2/runs
```

目标：

- 不改变 UI。
- 可观察 V2 是否比旧状态更准确。

当前状态：

- 已提供 `/runtime-v2/state`：从 V2 snapshots 汇总会话与 active runs。
- 已提供 `/runtime-v2/sessions/{id}/events`：按 `after_seq`、`before_seq`、`limit` 只读查询单会话 V2 event log。
- 已提供 `/runtime-v2/runs`：只读查看 V2 active runs。
- 这些接口只读 V2，不改变 `RUNTIME_VERSION=1/2` 主路径选择。

### 阶段 D：局部接管运行态

让 `/sessions/state` 的 active runs 来源切到 Runtime V2。

优先解决：

- 黄点卡住。
- 发送按钮不恢复。
- 停止后状态延迟。
- 流式异常后刷新卡 loading。

### 阶段 E：接管 SSE

新增：

```text
GET /runtime-v2/events?session_id=...&after_seq=...
```

目标：

- SSE 重连去重。
- 黑屏/睡眠后恢复。
- 异常一定收到 `run_failed` 或可通过 state 恢复。

当前状态：

- 已提供 `/runtime-v2/events?session_id=...&after_seq=...`，可按 `after_seq` 只读拉取 V2 events。
- 前端主 SSE 仍消费 `/chat` / `/sessions/{id}/stream`，但流结束、自然断开、重连后会按旧 UI `eventIndex` 从 `/sessions/{id}/messages?after_index=...` 拉取 Runtime V2 UI 投影增量补漏。
- `/runtime-v2/sessions/{id}/stream?after_seq=...` 已提供 Runtime V2 原生 `seq` 事件 SSE。
- `/sessions/{id}/stream?after_index=...` 在 V2 模式下已切到 RuntimeUiProjection 增量流，用于前端 reattach 恢复。
- 完整接管仍需要把 `/chat` 主实时响应本身切到 Runtime V2 原生 `seq` 事件，而不是只在 reattach/收尾阶段做投影补漏。

### 阶段 F：接管消息历史

消息区从 Runtime V2 event log 回放。

目标：

- 历史回放和实时流同源。
- 加载更早历史不与实时事件冲突。
- 消息不会因为多文件状态不同步而消失。

## 和原 1-10 阶段重构的关系

Runtime V2 是原重构方案的干净新内核版本。

| 原阶段 | Runtime V2 覆盖情况 |
|---|---|
| 1 前端状态核心 | 后续通过 snapshot/event 简化 |
| 2 会话列表刷新 | SessionRepository + state 覆盖 |
| 3 后端状态快照 | RuntimeGateway.get_state 覆盖 |
| 4 SSE seq 化 | StreamPublisher + after_seq 覆盖 |
| 5 运行状态统一 | RunRegistry 覆盖 |
| 6 消息渲染重构 | EventLog 提供统一数据源 |
| 7 Subagent 状态 | SubagentRepository 覆盖 |
| 8 Context/Todo/Token | 标准事件覆盖来源 |
| 9 文件写入与落盘 | SessionEventLog + Repository 覆盖 |
| 10 构建保护 | 继续保留现有机制 |

## 成功标准

Runtime V2 完整接入后，应满足：

- 正常完成一定产生 `run_finished`。
- 手动停止一定产生 `run_interrupted`。
- 异常一定产生 `run_failed`。
- 刷新页面只需 state + after_seq 即可恢复。
- 左侧黄点与发送按钮来自同一事实源。
- 子 Agent 是否完成、是否有 final、结果是否读取过都有明确事件。
- 事件日志能重放出当前会话状态。
- metadata/index/snapshot 损坏时可重建。

## 当前切换与兼容状态

### Runtime 版本选择

当前运行时通过环境变量选择主读写路径：

```text
RUNTIME_VERSION=2
  read  = Runtime V2
  write = Runtime V2 first, Runtime V1 mirror

RUNTIME_VERSION=1
  read  = Runtime V1
  write = Runtime V1 first, Runtime V2 mirror
```

兼容旧变量：

```text
RUNTIME_V2_ENABLED=1  # 未设置 RUNTIME_VERSION 时等价于 RUNTIME_VERSION=2
RUNTIME_V2_ENABLED=0  # 未设置 RUNTIME_VERSION 时等价于 RUNTIME_VERSION=1
```

明确设置 `RUNTIME_VERSION` 时，它优先于 `RUNTIME_V2_ENABLED`。

### 当前已经接管的 V2 能力

- UI 历史读取：`/sessions/{id}/messages` 在 V2 模式下读取 Runtime V2 投影，必要时从旧 `ui_events.json` 回填。
- 模型历史读取：V2 模式下模型输入读取 `model_messages` 投影；V1 模式仍读旧 `llm_history.json`，同时镜像 V2。
- 运行状态：V2 模式下会话黄点、发送按钮运行态读取 `snapshots/latest.json.active_runs`。
- Subagent 状态：V2 模式下 task index、pending result、task output 从 `subagents/` 目录读取；V1 文件仍同步镜像。
- Context/Todo/Token：V2 snapshot 记录 `context.tokens`、`context.todo`、`context.summary`，API 优先读 snapshot，失败再回退旧路径。
- UI 投影性能：`RuntimeUiProjection` 按 `events.jsonl` 的 `mtime_ns + size` 缓存投影，减少重复切会话时的全量 JSONL 解析。
- 前端状态：Context token 请求已按 session 去重并短时复用；Todo 面板已短时复用 store，减少 SSE 后重复 fetch。

### 双路径能力审计表

| 能力 | V1 模式 | V2 模式 | 当前状态 |
|---|---|---|---|
| 会话列表与 state | 读 V1 metadata/index + legacy run state，镜像 V2 | 读 V2 snapshot active runs，并按本进程真实 task/SSE/start 占位过滤孤立 active run | 已接入，仍需继续端到端压测 |
| 消息历史 `/messages` | 读 `ui_events.json` | 读 RuntimeUiProjection；TOC/user_turns 也读 active runtime。普通打开、刷新、滚动恢复不得回填 legacy，legacy 导出只允许显式 sync/migration | 已接入，需继续压测大历史与分支/改写 |
| 消息计数 `/messages/count` | 读 V1 `ui_event_count`/ui_events | 读 RuntimeUiProjection index | 已接入 |
| 模型历史 | 读 `llm_history.json`，镜像 V2 | 读 `model_messages` 投影；旧会话 partial projection 会按需用 legacy 同步 | 已接入，需覆盖更多双向测试 |
| 运行态 | legacy active run + chat connection | V2 `active_runs` snapshot + 本地活动证据过滤 | 已接入 |
| SSE | 现有 `/stream` / `/chat` 事件 | `/runtime-v2/events?after_seq=...`、`/runtime-v2/sessions/{id}/stream`、V2 模式 `/sessions/{id}/stream` 投影增量流 | reattach 已接管，主 `/chat` 实时流尚未切 raw V2 seq |
| 历史操作：删除/改写/截断 | 改写 V1 文件，追加 V2 observation/history event | 应追加 V2 原生事件并镜像 V1 | 部分完成，需补 V2-first 写路径 |
| 分支 | V1 创建新会话文件，镜像 V2 | V2 seed 分支事件流，并用源 Runtime seq 记录 branch point | 部分完成，仍需进一步减少 V1-first 外壳 |
| Context/Todo/Token | 读旧文件/即时计算，镜像 V2 | 读 snapshot，失败回退旧路径 | 部分完成 |
| Subagent | 读 V1 subagent 文件 | 读 V2 `subagents/` task/output/pending | 部分完成，需补端到端审计 |
| 调试接口 | 不影响 V1 | `/runtime-v2/state`、`events`、`runs` | 已实现 |

### 当前仍保留的兼容文件

这些文件仍会写入，用于 V1/V2 对比和回退：

- `ui_events.json`
- `llm_history.json`
- `work_messages.json`
- `metadata.json`
- `key_context.md`
- `todo_plan.md`
- `subagent_tasks.json`
- `pending_subagent_results.json`
- `subagent_outputs/*.md`

这些文件是 Runtime V2 的事实源和投影：

- `events.jsonl`
- `snapshots/latest.json`
- `blobs/{sha256}.txt`
- `subagents/{agent_id}/events.jsonl`
- `subagents/{agent_id}/snapshots/latest.json`
- `subagents/{agent_id}/metadata.json`
- `subagents/{agent_id}/output.md`
- `subagents/tasks.json`
- `subagents/pending_results.json`

### 审计与修复命令

对比旧 UI/model 文件与 Runtime V2 投影：

```text
python scripts/audit_runtime_versions.py --only-mismatches
```

修复 UI/model 投影不一致：

```text
python scripts/audit_runtime_versions.py --repair-ui --repair-model --only-mismatches
```

检查并清理 V2 僵尸 active run：

```text
python scripts/audit_runtime_versions.py --only-mismatches
python scripts/audit_runtime_versions.py --repair-runs --only-mismatches
```

注意：`--repair-runs` 会给 V2 active run 追加 `run_interrupted` 事件。只应在确认没有真实任务仍在执行时使用。

对比读取性能：

```text
python scripts/benchmark_runtime_versions.py --session-id <session_id>
```

### 长期双路径保留策略

Runtime V2 的目标是完整接管一条新主路径，但不是删除 Runtime V1。即使 V2 完成后，也必须长期保留 V1/V2 切换能力，用于回退、对照、审计和问题隔离。

必须长期保留：

1. `RUNTIME_VERSION=1` 在线路径：读取 V1 文件，写入 V1 后镜像 V2。
2. `RUNTIME_VERSION=2` 在线路径：读取 V2 事件/投影，写入 V2 后镜像 V1。
3. V1 兼容文件：`ui_events.json`、`llm_history.json`、`work_messages.json`、`metadata.json`、`key_context.md`、`todo_plan.md`、`subagent_tasks.json`、`pending_subagent_results.json`、`subagent_outputs/`。
4. V2 事实源与投影：`events.jsonl`、`snapshots/latest.json`、`blobs/{sha256}.txt`、`subagents/{agent_id}/events.jsonl`、`subagents/{agent_id}/snapshots/latest.json`、`subagents/tasks.json`、`subagents/pending_results.json`。
5. 双向 mirror：V1 写入必须持续镜像 V2；V2 写入必须持续镜像 V1。
6. 审计与修复脚本：作为常驻保护，而不是迁移临时工具。
7. API fallback：允许在主路径异常时兜底读取另一条路径，但 fallback 不能掩盖审计差异，必须记录日志或可被审计脚本发现。

V2 完整完成的标准不是“可以删除 V1”，而是：

- 切到 `RUNTIME_VERSION=2` 后，消息历史、运行状态、SSE 恢复、模型历史、历史操作、subagent、context/todo/token 都可由 V2 独立支撑。
- 切回 `RUNTIME_VERSION=1` 后，V1 文件仍完整可用，且不丢失在 V2 模式下产生的会话事实。
- 任一模式写入后，另一模式读取不应丢消息、不应恢复错误运行态、不应改变分支/改写/删除边界。
- 审计脚本能持续发现并定位 V1/V2 投影差异。
