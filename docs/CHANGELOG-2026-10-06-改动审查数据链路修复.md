# 2026-10-06 改动审查数据链路修复（执行记录丢 `ui.changes`）

## 一、症状

会话（例：`538fea5c`）的改动能在**详情栏「修改历史」**里看到，但聊天区的**改动审查**（左栏「改动」页签 / 窄态条目 + 浮窗 / 输入框上方兜底条）完全不出现。

## 二、根因

改动审查是插件，它的行数据一直"搭便车"在工具行的渲染事件（`row._toolCallEvent.ui`）上。2026-10-04 的执行记录批次（`de2d6d6`，execution journal / DSR 适配）把工具行改为由**执行记录**驱动：

- `renderExecutionEvent()`（历史投影）构造 update 时没有带 `ui`；
- `renderExecutionRecord()` 重建的 `_toolCallEvent` 也没有 `ui`（唯一带 `ui` 的 `upsertToolCallResult` 不再是最后写入者）；
- 后端 `runtime_v2/execution_journal.py` 记录工具结果时（`ui_committed=True`）同样没有 `ui`。

于是插件每次 `applyTool()` 的 `incoming` 都是空集合，页签/条目/浮窗全部不显示；而详情栏「修改历史」直接读 `/history_snapshot`（其中 `ui.changes` 完好），所以照常显示。实测（修复前）：`538fea5c` 历史里 18 条带 `ui.changes` 的工具事件，页面派发的 123 次 `myagent:tool-call-rendered` 中带 `ui` 的为 **0**；手动重放一条带 `ui` 的事件，插件立刻正常 ⇒ 缺的只是负载。

## 三、修复

| 位置 | 改动 |
| --- | --- |
| `frontend/src/app/modules/message-rendering.js` | `renderExecutionEvent()` 的 `tool_call` 分支透传 `ui`（`event.ui ? {ui:event.ui} : null`）；`renderExecutionRecord()` 的 `_toolCallEvent` 补 `ui:record.ui` |
| `app/runtime_v2/execution_journal.py` | 工具结果 update 带上 `ui`（`event["ui"]` 非空 dict 时），使实时 `execution_update` 与重放记录都携带该负载 |
| `tests/js/change_review_ui_payload_runtime.cjs` + `tests/test_change_review_ui_payload_runtime.py` | 前端契约回归：历史投影与执行记录两条路径都必须把 `ui.changes` 带到工具行事件；无 `ui` 时不得凭空造 |
| `tests/test_execution_recovery.py` | 日志/投影回归：`execution_recorded` 记录与 `execution_update` 均携带 `ui`，且不进入模型历史 |

`ui` 是插件私有 UI 元数据（含 `snapshot_id/diff/...`），不参与模型历史；写入执行记录会略微增大 `events.jsonl`（与 `tool_finished` 同量级，diff 本身已有 1 MiB/行数上限）。

## 四、验证

- 契约测试：新增 node 用例在**回退修复后失败**、修复后通过（反向验证）；
- `pytest tests/test_change_review_ui_payload_runtime.py tests/test_execution_recovery.py tests/test_change_review_plugin.py -q` → **98 passed**；
- 全量 `pytest -q` → **2272 passed / 5 skipped / 3 failed**，其中 3 项与本次改动无关（见下）；
- 前端 `npm run build` 重建 dist（`main-uyn1ClLc.js` / `main-BWYXI8D-.css`）；
- 实机（Playwright，刷新后的新 bundle）：打开 `538fea5c` → 左栏「改动」页签出现、窄态条目出现、卡片显示本轮改动 `SugarAgent改名/配置迁移到.sugaragent_状态说明.md +47 −0`，点击条目弹出「改动」浮窗（截图：`workspace/改动审查修复_验证/改动审查浮窗_修复后.png`、`改动审查页签_修复后.png`）。

## 五、遗留与边界

- **实时链路**：修复 `execution_journal.py` 属于后端进程内模块，需重启 Agent（托盘/RUN）后新写入的记录才带 `ui`；在那之前"运行中即时出现"仍缺一路，**刷新页面/重新打开会话即恢复**（历史路径已修好）。
- 既有失败（与本次无关，均来自工作区里其它未提交改动）：`test_frontend_session_stream_runtime[new_session_lifecycle_runtime.cjs]`（`document.getElementById is not a function`）、`[model_reasoning_effort_runtime.cjs]`（`newSessionWorkDirTarget is not defined`，该符号只存在于工作区版本）、`test_webui_messages.py::test_sessions_state_cache_serves_stale_value_during_one_background_refresh`（负载下超时，单独复跑通过）。
- 观察（未处理）：窄态浮窗打开时切换会话，浮窗内容仍是上一个会话的宿主，切换后应收起。
