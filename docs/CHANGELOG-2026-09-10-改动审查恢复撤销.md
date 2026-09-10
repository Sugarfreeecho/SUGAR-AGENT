# CHANGELOG — 改动审查：撤销的"恢复"（redo）功能（2026-09-10）

给撤销配了一个对称的**恢复**能力：已撤销的改动可以重新应用回去。

## 1. 为什么需要它

在此之前，撤销是一次性的：一旦点了"撤销"，记录被标记 `reverted`，提交后即使撤销里那步快照字节也会被回收——用户无法反悔把改动要回来（只能让模型重做一遍）。本次按"撤销与恢复成对"的语义补齐闭环。

## 2. 后端（`plugins/change-review/store.py`）

### 新增 API

- `restore(snapshot_ids, operation_id)`：把已撤销的改动重新应用到工作区。
  - 冲突保护与 undo 完全对称：要求文件当前状态 == 记录的 `before`，否则整批中止（`ChangeConflictError`，返回冲突路径列表）；**不会半量应用**。
  - 幂等：journal 键为 `restore:<operation_id>`，重放返回缓存结果。
  - 写盘前校验所需 blob 完整性；失败时把已改动的记录回滚（`_restore_record(record, "before")`）。
  - 空目录组：恢复时对 `delete_file` 产生的目录清单执行 `rmdir`（沿长路径逆序），使"删除目录→撤销（目录回来）→恢复（目录再次消失）"闭环。
- `commit_restore(operation_id)` / `rollback_restore(operation_id)`：与 undo 同构的事务收尾；rollback 在事件/通知持久化失败时把字节放回撤销后状态。

### 快照留存策略调整（关键）

- 原来 `_gc_blobs` 会跳过所有 `reverted` 记录 → 撤销提交后快照即被回收，恢复不可能。
- 现在只回收 **`dropped`**（历史被修剪、永远不会再被恢复）或 `neutralized`（净零）的记录；`reverted` 但仍有历史引用的记录保留 `before`/`after` 两片 blob，直到 `prune_unreferenced` 标记 `dropped` 后由下一次 GC 回收。
- `prune_unreferenced` 新增 `dropped` 标记；`_gc_blobs` 条件同步。

## 3. 宿主 API（`plugins/change-review/host.py`）

- 新增 `POST /sessions/{session_id}/change-reviews/restore`（与 undo 共用同一 `run_review_action` 骨架：活动任务拒绝 409、工作区锁、幂等重放）。
- 成功后持久化 UI 事件 `file_changes_restored`，向子会话与根会话各发一条模型通知（"改动已被用户恢复，请按 post-tool 内容理解工作区"）。
- `runtime.py` 的 `referenced_snapshot_ids` 同时收集 `file_changes_restored` 的引用，防止恢复过的记录被历史修剪误回收。

## 4. 前端（`web/change-review.js` / `change-review.css`）

- 已撤销的记录**不再从面板消失**：保留在列表中，置灰 + "已撤销"标签，行内按钮由"撤销"变为"恢复"（单项带确认，与撤销同一交互）。
  - 面板可见性从「仅有活动改动」改为「活动 + 已撤销」；底部按钮按作用域显示：有活动改动→"全部撤销"，有已撤销记录→"全部恢复"。
  - 汇总行：有已撤销时追加 " · N 已撤销"；全部撤销后显示"N 个文件已撤销，可恢复"；徽标同理。
- `splitReviewRows(rows)`（导出，供测试）：拆分活动 / 已撤销两组。
- 冲突提示按动作区分："文件已再次修改，撤销已中止 / 恢复已中止"。

## 5. 测试

- 后端新增：`test_undo_then_restore_round_trip`（含 commit 后仍可恢复、幂等重放、恢复后可再次撤销）、`test_restore_conflict_aborts_without_touching_files`、`test_restore_requires_a_reverted_snapshot`、`test_pruned_records_cannot_be_restored`、`test_prepared_restore_can_roll_back_when_event_commit_fails`、`test_directory_delete_restore_round_trip`（含空目录）、`test_restore_api_reapplies_and_persists_ui_event`（host 层，镜像 undo 的 API 测试）。
- 前端：`tests/js/change_review_stats_runtime.mjs` 增加 `splitReviewRows` 断言；`test_plugin_ui_frontend.py` 固定 `file_changes_restored` / `change-review-restore(-all)` 存在。
- 结果：`test_change_review_plugin.py` + `test_plugin_ui_frontend.py` 共 44 通过。

## 6. 涉及文件

- `plugins/change-review/store.py`（restore/commit_restore/rollback_restore、GC/prune 策略）
- `plugins/change-review/host.py`（restore 路由、事件与通知）
- `plugins/change-review/runtime.py`（引用收集）
- `plugins/change-review/web/change-review.js`、`web/change-review.css`
- `tests/test_change_review_plugin.py`、`tests/test_plugin_ui_frontend.py`、`tests/js/change_review_stats_runtime.mjs`
