# 写路径与摘要持久化 · 功能方案设计（UseCase 清单）

- 版本：2026-09-20 v4（覆盖至：当前工作区）
- 用途：逐条审查（四字段格式）。
- 适用实现：`runtime_v2/history_ops.py`（1282 行）、`agent_loop.py`（提交调用点）。
- 上级：`00-会话存储RuntimeV2整体设计.md`

---

## 1. 功能定位

"写"的家族：用户轮、答复、模型消息、历史替换、摘要提交——事务化、可回滚、可审计。

## 2. UseCase

### UC-8C1 历史事务
- **触发**：提交用户轮/答复/消息。
- **预期现象**：原子提交（一条 event + 快照更新）；失败不产生半截；重放同一提交幂等（以 seq 判重）。
- **依据**：`RuntimeHistoryOps`（_append_and_snapshot 等）。

### UC-8C2 历史替换
- **触发**：压缩/编辑导致历史被替换。
- **预期现象**：以显式事件记录替换（含原因与快照）；投影/模型视图立即一致；旧消息可从事件回溯。
- **依据**：`_runtime_v2_replace_model_history`、history_ops 替换段。

### UC-8C3 摘要提交
- **触发**：压缩完成（自动/强制/手动）。
- **预期现象**：`context_summary_committed` 事件落库（`source_seq` 为**可选**关联：仅显式传参时写入，ReAct 主路径当前不传）；重启后摘要可用；UI 回放可见压缩过程。
- **依据**：`commit_context_summary`（L423）。

### UC-8C4 回滚与恢复语义
- **触发**：提交后事件写失败 / 需要还原。
- **预期现象**：按准备好的回滚路径还原（不留半状态）；恢复数据（restore_context_summary 等）可被修复服务使用。
- **依据**：history_ops 回滚段（L597 restore 数据）、`repair.py`。

### UC-8C5 未变化摘要的进程内提交去重
- **触发**：ReAct 每轮尝试持久化与上次已提交内容相同的 context summary。
- **预期现象**：命中 `_RUNTIME_V2_COMMITTED_SUMMARY` 后直接跳过磁盘快照读取和重复提交；首次未命中仍读取权威快照比较，避免覆盖其他写者。
- **规则与边界**：该缓存只证明本进程已成功提交的摘要；冷启动或未命中必须回到 Runtime V2 权威读取，不能仅凭内存假定磁盘状态。
- **依据**：`agent_loop._runtime_v2_commit_context_summary`、`_RUNTIME_V2_COMMITTED_SUMMARY`。

### UC-8C6 压缩原文独立归档
- **触发**：本地压缩进入模型摘要轮。
- **预期现象**：被压缩前缀按原消息结构写入会话目录下 `history_context_archives/<archive_id>.jsonl`，每条记录获得稳定 `history:` 引用；摘要、活跃摘录和检索工具可引用同一份原文。
- **规则与边界**：归档采用临时文件替换方式一次性发布，创建后不可变；它是 Runtime V2 事件流之外的检索副本，不改写 event，不承担事件序列或快照的权威语义；同一摘要轮的模型重试不重复归档。
- **依据**：`history_context.archive_messages / archive_ref / archive_item_ref`、`agent_memory._compress_summary_round`。

## 3. 边界

- 提交的**时机**属于 ReAct 写栅栏（../02-ReAct运行时/05）；
- 压缩算法本体见 ../09-横切能力/01。
- 归档搜索同时覆盖 `history_context_archives/*.jsonl` 与 `events.jsonl`；搜索返回 `source_file`，但不会修改两者。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-8C1 | `history_ops.py` L38+ |
| UC-8C2 | `agent_loop.py` L2352–2379 |
| UC-8C3 | `history_ops.py` L423；`agent_loop.py` L2379–2404 |
| UC-8C4 | `history_ops.py` L597 |
| UC-8C5 | `_runtime_v2_commit_context_summary`、`_RUNTIME_V2_COMMITTED_SUMMARY` |
| UC-8C6 | `history_context.archive_messages`、`agent_memory._compress_summary_round` |

## 5. 版本记录

- 2026-09-20 v4：补入本地压缩原文的不可变 JSONL 归档、稳定引用及其与 Runtime V2 权威事件流的边界。
- 2026-09-20 v3：补入未变化 context summary 的进程内提交去重及冷未命中权威读取边界。
- 2026-09-14 v2：澄清 `source_seq` 为可选关联；版本线更新至 `d022831`。
- 2026-09-13 v1：拆分首版（承接 UC-805/806）。
