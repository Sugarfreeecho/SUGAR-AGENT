# 2026-09-30 侧栏待办不再改写会话活动时间

## 问题

- 在侧栏用「设为待办 / 取消待办」标记会话时，会话会立刻被顶到列表最前，日期分组与时间显示也一并跳到当前时刻。
- 根因：`SessionManager.set_session_todo` 除了写 `todo`，还把 `metadata["updated_at"]` 与索引行的 `updated_at` 改成当前时间。而侧栏排序键 `last_activity_at` 就取自 `updated_at`（`_session_entry_with_activity` → `list_sessions` 的 `sort_key`；前端 `sessionStore._reorderSessionOrder` 用同一套规则），于是纯标记操作被当成了"会话有新活动"。该时间戳随 `metadata.json` / `sessions.json` 落盘，重启后依然生效，也会推迟 14 天自动归档。

## 修复

- `set_session_todo` 只写 `todo`，保留原有 `updated_at`：元数据不再被改写，内存索引行的 `updated_at` 也不再被覆盖；`_save_index()`、`_notify_session_state_changed(session_id, {"todo"})` 与 `/sessions/state` 缓存失效逻辑保持原样。
- 行为边界：`todo` 仍持久化在元数据与索引中，重启、导出、远程控制列表都照常显示待办标记；只有"时间/排序"不再受它影响。真正的对话活动（用户消息、助手回复、运行终态）依旧照旧推进 `updated_at`。
- 前端无需改动：乐观更新只 patch `todo` 字段，随后 `refreshSingleSessionRow` 取回的 `last_activity_at` 与刷新前一致，`sessionStore` 重排结果不变。

## 验证

- 新增回归用例 `tests/test_session_activity_sorting.py::test_todo_toggle_keeps_activity_time_and_sidebar_order`：勾选/取消待办后列表顺序、`updated_at`、`last_activity_at`，以及重启后（含 `events.jsonl` 时间对账）重建索引的结果都不变；该用例在修复前会失败（首个顺序断言处）。
- 复现脚本（修复前 FAIL、修复后 PASS）：`workspace/侧栏待办排序修复/repro_todo_order.py`；端点级校验（修复前 `GET /sessions` 顺序翻转且摘要时间跳变，修复后稳定）：`workspace/侧栏待办排序修复/e2e_sidebar_todo_check.py`。
- 定向回归：`test_session_activity_sorting.py`、`test_session_todo_label.py`、`test_session_action_menu.py`、`test_session_index_startup_rebuild.py`、`test_session_name_editing.py`、`test_session_archive_refresh.py`、`test_session_goal_review_badge.py`、`test_agent_harness_reconcile.py`（67 passed）；`test_webui_messages.py`、`test_remote_control.py`、`test_ui_attention_notifications.py`、`test_subagent_live_state.py`、`test_session_export.py`、`test_session_draft_badge.py`、`test_execution_metrics.py`（98 passed）。
- 本批为纯后端改动，未触及前端源码，`app/templates/dist` 无需重新构建。

## 同类行为（本次未改，需要时可按同一思路处理）

以下侧栏操作同样会写 `updated_at`，因而具备"操作后被置前"的同类表现：

- `set_session_pinned`：取消置顶时会把旧会话标成"刚刚活动"，落到未置顶分组最前（置顶本身按 `pinned_at` 排序，不受影响）。
- `set_session_name`：重命名同样推进 `updated_at`。
- `set_session_goal_review_pending`：运行终态写"待审核"标记时也会推进 `updated_at`。

## 文件

- `app/agent_harness.py`：`SessionManager.set_session_todo` 去掉 `updated_at` 写入并补充说明注释。
- `tests/test_session_activity_sorting.py`：新增待办与活动时间/排序的回归用例。
