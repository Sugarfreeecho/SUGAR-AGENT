# 写路径与摘要持久化 · 功能方案设计（UseCase 清单）

- 版本：2026-09-13（覆盖至：HEAD `6acc6bf`）
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
- **预期现象**：`context_summary_committed` 事件落库（含 source_seq 关联）；重启后摘要可用；UI 回放可见压缩过程。
- **依据**：`commit_context_summary`（L423）。

### UC-8C4 回滚与恢复语义
- **触发**：提交后事件写失败 / 需要还原。
- **预期现象**：按准备好的回滚路径还原（不留半状态）；恢复数据（restore_context_summary 等）可被修复服务使用。
- **依据**：history_ops 回滚段（L597 restore 数据）、`repair.py`。

## 3. 边界

- 提交的**时机**属于 ReAct 写栅栏（../02-ReAct运行时/05）；
- 压缩算法本体见 ../09-横切能力/01。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-8C1 | `history_ops.py` L38+ |
| UC-8C2 | `agent_loop.py` L2352–2379 |
| UC-8C3 | `history_ops.py` L423；`agent_loop.py` L2379–2404 |
| UC-8C4 | `history_ops.py` L597 |

## 5. 版本记录

- 2026-09-13 v1：拆分首版（承接 UC-805/806）。
