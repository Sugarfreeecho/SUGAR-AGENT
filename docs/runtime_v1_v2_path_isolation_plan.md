# Runtime V1 / V2 路径完全隔离计划

## 目标

让 Runtime V1 和 Runtime V2 在读取、写入、修复、分支、截断、UI 加载、模型上下文构建上形成硬隔离：

- V1 模式只读取和写入 V1 文件。
- V2 模式只读取和写入 V2 事件日志、快照、投影。
- Legacy 文件只能作为明确迁移输入，不能在 V2 正常运行中参与读写。
- Legacy 修复逻辑不能反写 V2 model history。
- V2 的 UI 展示历史、模型历史、运行状态生命周期都必须能从 V2 event log 独立恢复。

## 非目标

- 不删除已有 V1 文件格式。
- 不强制一次性迁移所有旧会话。
- 不把 UI 展示历史和模型上下文历史合并成同一份文件。
- 不在 V2 下继续维护 `work_messages.json` 作为事实源。

## 当前问题

现在 V2 仍然不是纯 V2，而是：

```text
V2 主链路 + legacy 兼容层 + legacy fallback/backfill + legacy repair/reconcile
```

主要风险是 legacy 逻辑仍可影响 V2：

- V2 projection 缺失时会 fallback 到 `llm_history.json`。
- V2 UI 加载必要时会从 `ui_events.json` 回填。
- `reconcile_llm_work_to_ui_user_count()`、`repair_compacted_llm_history_from_ui()`、分支、截断、append tail 等逻辑仍基于 legacy 文件重建历史。
- 部分 legacy 操作会 mirror 成 V2 `replace_model_history`。
- `work_messages.json` 虽已退出 V2 API 热路径，但仍被分支、修复、子会话兼容逻辑读取。

这些混用会导致：

- ReAct 工具过程被 `user/final` 主对话链覆盖。
- UI 加载、TOC、滚动恢复和模型历史投影来源不一致。
- 断线重连、追问中断、继续运行时状态判断复杂化。
- 修一个兼容问题时容易破坏另一个链路。

## 隔离原则

1. 事实源唯一
   - V1 事实源：`ui_events.json`、`llm_history.json`、`work_messages.json`。
   - V2 事实源：`events.jsonl`。

2. 投影只能由本版本事实源生成
   - V1 UI 从 `ui_events.json` 生成。
   - V1 model history 从 `llm_history.json` 生成。
   - V2 UI 从 `RuntimeUiProjection(events.jsonl)` 生成。
   - V2 model history 从 `RuntimeModelProjection(events.jsonl)` 生成。

3. 兼容迁移必须显式
   - 允许 `migrate_legacy_to_v2(session_id)` 读取 V1 文件并写入 V2。
   - 禁止普通会话加载、发送消息、继续运行时隐式 fallback legacy。

4. legacy 不能反写 V2
   - V1 repair/reconcile/truncate/branch 只能改 V1 文件。
   - V2 repair/reconcile/truncate/branch 只能追加 V2 事件。

5. UI 展示历史和模型上下文分离
   - UI 可展示完整执行过程。
   - 模型上下文可压缩、裁剪、摘要。
   - 模型压缩不能删除 UI 可恢复执行过程。

6. 压缩只影响模型投影
   - V2 压缩通过事件表达：`context_compacted`、`model_history_replaced`、`model_message_appended`。
   - 原始工具过程仍应在 UI 事件或 blob 引用中可恢复。

## 目标路径划分

### V1 路径

```text
workspace/sessions/{session_id}/
  ui_events.json
  llm_history.json
  work_messages.json
  dialogue_history.json
  key_context.md
  todo_plan.md
  metadata.json
  subagent_tasks.json
  pending_subagent_results.json
```

V1 模式允许：

- 读取 `ui_events.json` 渲染 UI。
- 读取 `llm_history.json` 构建模型上下文。
- 读取/写入 `work_messages.json` 做 legacy 工作历史。
- 使用 legacy repair/reconcile/truncate/branch。

V1 模式禁止：

- 依赖 `events.jsonl` 作为必要事实源。
- 修改 V2 snapshot/model projection。

### V2 路径

```text
workspace/sessions/{session_id}/
  events.jsonl
  snapshots/
    latest.json
  blobs/
    {sha256}.txt
  metadata.json
  subagents/
    {agent_id}/
      events.jsonl
      snapshots/
        latest.json
      blobs/
        {sha256}.txt
```

V2 模式允许：

- 追加 `events.jsonl`。
- 从 `RuntimeUiProjection` 读取 UI 历史。
- 从 `RuntimeModelProjection` 读取模型历史。
- 从 snapshot 加速恢复。
- 从 blobs 恢复大文本、工具输出、长 reasoning。

V2 模式禁止：

- 正常运行中读取 `llm_history.json` 作为模型输入。
- 正常运行中读取 `work_messages.json`。
- 正常运行中从 `ui_events.json` 生成 UI。
- 保存 `llm_history.json` / `work_messages.json`。
- 调用 `_rebuild_llm_work_from_ui()`。
- 调用 legacy repair/reconcile 后反写 V2。

## 兼容迁移边界

唯一允许跨路径的入口应是显式 migration：

```text
migrate_legacy_session_to_v2(session_id)
```

职责：

- 读取 V1 文件。
- 生成 V2 `events.jsonl`。
- 生成 V2 snapshot。
- 标记 migration 状态。
- 不在用户发送消息的热路径执行。

迁移状态写入 metadata：

```json
{
  "runtime_v2_migration": {
    "status": "complete",
    "source": "legacy",
    "completed_at": "..."
  }
}
```

V2 打开会话时：

- 如果 migration complete：只读 V2。
- 如果未迁移：提示/后台迁移/显式迁移。
- 不允许静默 fallback legacy 并继续运行。

## 分阶段实施计划

### 阶段 0：硬边界审计

目标：先知道 V2 正常路径还有哪些 legacy 调用。

任务：

- 新增 V2 guard 测试。
- 在 V2 模式下禁止以下调用出现在正常运行路径：
  - `_load_llm_history`
  - `_save_llm_history`
  - `_load_work_messages`
  - `_save_work_messages`
  - `_rebuild_llm_work_from_ui`
  - `reconcile_llm_work_to_ui_user_count`
  - `repair_compacted_llm_history_from_ui`
- 允许这些函数只在 migration 流程或 V1 模式出现。

验收：

- 测试能枚举并阻断 V2 热路径 legacy 调用。
- 当前已知例外必须有白名单和移除计划。

### 阶段 1：断开 legacy 对 V2 的反写

目标：legacy 逻辑不能再覆盖 V2 model history。

任务：

- 禁止 legacy reconcile 触发 V2 `replace_model_history`。
- 禁止 legacy truncate/branch/append_tail 触发 V2 model history 替换。
- V2 下所有 model history 变更必须通过 `RuntimeHistoryOps`。
- legacy 文件更新只服务 V1 兼容，不得改变 V2 projection。

验收：

- V2 `events.jsonl` 中不再出现 `reason=legacy_reconcile` 的 `model_history_replaced`。
- 分支/截断 legacy 文件不影响 RuntimeModelProjection。

### 阶段 2：V2 模型历史纯化

目标：发送 API 前只读 RuntimeModelProjection。

任务：

- `_load_model_history_dicts_v2_primary()` 在 V2 下只读 `RuntimeModelProjection`。
- projection 缺失时返回明确错误或触发显式 migration。
- 移除 V2 下 `_load_llm_history()` fallback。
- token 估算、上下文策略、sanitize 均基于 V2 model projection。

验收：

- V2 发送消息前不会读取 `llm_history.json`。
- V2 发送消息前不会读取 `work_messages.json`。
- 大历史会话发送前准备耗时可观测下降。

### 阶段 3：V2 UI 历史纯化

目标：前端打开会话只读 RuntimeUiProjection。

任务：

- `/sessions/{id}/messages` V2 下只读 RuntimeUiProjection。
- `/sessions/{id}/messages/count` V2 下只读 RuntimeUiProjection。
- `/sessions/{id}/stream` reattach 只读 V2 event seq。
- TOC、user_turns、分页、滚动定位使用同一套 V2 投影索引。
- 移除 V2 UI 加载中的 `ui_events.json` fallback。

验收：

- 打开 V2 会话不会读取大 `ui_events.json`。
- TOC 和正文来自同一 projection，不再互相刷新/清空/重建。
- 已缓存和未缓存会话滚动恢复行为一致。

### 阶段 4：V2 分支/截断/改写原生化

目标：分支、截断、改写只操作 V2 events。

任务：

- `truncate_session_at_event_index()` V2 分支改为追加 `visible_range_changed` 或生成新 session event log。
- `branch_session_at_event_index()` V2 分支从 event seq 复制/派生新 session。
- 改写基于 event seq，而不是 legacy UI index。
- 不调用 `_rebuild_llm_work_from_ui()`。
- 不保存 `llm_history.json/work_messages.json`。

验收：

- V2 分支后新会话有独立 `events.jsonl`。
- 原会话和分支会话的 UI/model projection 可独立恢复。
- 分支/截断不会造成 ReAct 工具过程丢失。

### 阶段 5：V2 repair/reconcile 原生化

目标：修复逻辑从“重写历史文件”改为“追加修复事件”。

任务：

- 新增 V2 health check：
  - orphan run
  - missing terminal event
  - unclosed tool call
  - projection mismatch
- 新增 V2 repair events：
  - `run_recovered`
  - `run_marked_interrupted`
  - `model_tail_sanitized`
  - `projection_rebuilt`
- 移除 V2 下 legacy `repair_compacted_llm_history_from_ui()`。
- 移除 V2 下 legacy `reconcile_llm_work_to_ui_user_count()`。

验收：

- V2 repair 不读写 legacy history。
- repair 前后 event log 可审计。
- 修复不会把完整历史降级为 user/final。

### 阶段 6：Subagent V2 独立化

目标：父子 agent 都使用 V2 event log。

任务：

- 子 agent 事件只写 `subagents/{agent_id}/events.jsonl`。
- 父会话只保存子 agent 索引/状态事件。
- pending result 使用 V2 subagent store。
- 子 agent 复制/继续/恢复不读取 parent `work_messages.json`。

验收：

- 父会话打开不需要加载所有子 agent 大历史。
- 子 agent 状态能从自身 event log 独立恢复。
- 父会话 projection 只显示必要子任务摘要和入口。

### 阶段 7：Legacy 文件只读导出

目标：V2 不再维护 legacy 文件，只在需要时导出。

任务：

- 将 `llm_history.json`、`ui_events.json`、`work_messages.json` 在 V2 下改为可选导出产物。
- 导出动作必须显式，例如：
  - debug export
  - migration backup
  - V1 compatibility export
- 默认运行不写这些文件。

验收：

- 新建 V2 会话目录中没有必须存在的 legacy history 文件。
- 删除 legacy history 文件后，V2 会话仍可打开、继续、分支、截断。

## 硬边界测试清单

V2 模式下应新增这些测试：

- 发送消息不调用 `_load_llm_history`。
- 发送消息不调用 `_load_work_messages`。
- 发送消息不调用 legacy reconcile。
- 打开消息列表不读取 `ui_events.json`。
- 分支不调用 `_rebuild_llm_work_from_ui`。
- 截断不保存 `llm_history.json`。
- repair 不保存 `work_messages.json`。
- `events.jsonl` 删除 legacy 文件后仍可投影 UI。
- `events.jsonl` 删除 legacy 文件后仍可投影 model history。
- 压缩后 UI projection 仍保留工具执行过程。
- 压缩后 model projection 可以只保留摘要和尾窗。

## 风险与处理

### 风险：旧会话打不开

处理：

- 打开旧会话时检测 migration 状态。
- 未迁移则进入迁移流程。
- 迁移失败时只读展示 legacy，不允许继续在 V2 下运行。

### 风险：迁移耗时过长

处理：

- 迁移放后台任务。
- UI 显示 migration 状态。
- 大工具输出写入 blobs，event log 只保存引用。

### 风险：V2 projection 缺失或损坏

处理：

- 从 `events.jsonl` 重建 snapshot。
- 如果 `events.jsonl` 损坏，使用 JSONL 截断恢复到最后完整 seq。
- 不从 legacy 文件静默覆盖 V2。

### 风险：功能短期重复实现

处理：

- 接受 V1/V2 同时存在两套分支/截断实现。
- 不再让同一个函数根据 flag 混合处理两种事实源。
- 公共逻辑只抽无状态工具函数，不抽文件读写层。

## 完成标准

达到以下条件才算 V1/V2 路径完全隔离：

- V2 新会话不生成必需的 `llm_history.json`、`work_messages.json`、`ui_events.json`。
- V2 打开会话、发送消息、继续运行、停止、断线重连、追问、分支、截断、修复都只依赖 `events.jsonl/snapshots/blobs`。
- V2 正常运行路径没有 legacy fallback。
- legacy migration 是显式入口，有日志、有状态、有失败处理。
- 删除 V2 会话目录下 legacy history 文件后，所有 V2 功能仍可用。
- ReAct 工具过程在 UI projection 中可恢复，模型上下文压缩不会影响 UI 可见历史。

## 建议优先级

1. 阶段 1：断开 legacy 对 V2 的反写。
2. 阶段 2：V2 模型历史纯化。
3. 阶段 3：V2 UI 历史纯化。
4. 阶段 4：V2 分支/截断/改写原生化。
5. 阶段 5：V2 repair/reconcile 原生化。
6. 阶段 6：Subagent V2 独立化。
7. 阶段 7：Legacy 文件只读导出。

