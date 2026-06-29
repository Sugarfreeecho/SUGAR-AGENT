# Runtime V2 问题收敛执行步骤计划

## 目标

同时解决三类问题：

1. 发送 API 前准备阶段耗时过长。
2. V1 / V2 路径未完全独立。
3. 历史上下文中的工具执行过程丢失。

执行原则：

- 先保护数据完整性，再优化性能。
- 先断开 legacy 反写 V2，再清理 fallback。
- 不用补丁式恢复单个会话，优先修规则和边界。
- 每一步都必须有可验证测试。

## 总体顺序

```text
阶段 1：封锁工具过程丢失的剩余入口
阶段 2：建立 V2 正常路径硬边界
阶段 3：V2 模型历史纯化，解决 API 前耗时
阶段 4：V2 UI 历史纯化，解决 TOC/正文加载错位
阶段 5：V2 分支/截断/repair 原生化
阶段 6：性能收尾：token、MCP、projection cache
阶段 7：旧会话 migration 与 legacy 只读导出
```

## 阶段 1：封锁工具过程丢失的剩余入口

### 目的

防止任何 legacy 对齐/修复/截断逻辑把完整 ReAct 历史覆盖成 `user/final` 主对话链。

### 已完成

- `reconcile_llm_work_to_ui_user_count()` 已改为只允许裁剪尾部多写盘回合。
- 用户轮数未超出 `ui_events` 时，不再重建 `llm_history`。
- 已新增回归测试：
  - `tests/test_agent_harness_reconcile.py`

### 继续执行步骤

1. 检查所有会调用 `_rebuild_llm_work_from_ui()` 的入口。

   重点文件：

   - `app/agent_harness.py`

   重点函数：

   - `truncate_session_at_event_index`
   - `branch_session_at_event_index`
   - `repair_compacted_llm_history_from_ui`
   - `append_ui_events_tail`
   - `reconcile_llm_work_to_ui_user_count`

2. 给这些入口加保护规则：

   - V1 模式：允许 legacy rebuild。
   - V2 模式：禁止 legacy rebuild 反写 Runtime V2。
   - V2 模式下如需修复，只能追加 V2 repair event。

3. 新增测试：

   - V2 下 truncate 不调用 `_rebuild_llm_work_from_ui`。
   - V2 下 branch 不调用 `_rebuild_llm_work_from_ui`。
   - V2 下 repair 不保存 `llm_history.json`。
   - V2 下 append tail 不保存 `work_messages.json`。

### 验收标准

- V2 正常操作不会产生 `reason=legacy_reconcile` 的 `model_history_replaced`。
- V2 正常操作不会因为 legacy rebuild 让 tool/tool_call 消失。
- 已损坏会话不自动覆盖，但新运行不会继续制造同类损坏。

## 阶段 2：建立 V2 正常路径硬边界

### 目的

让 V2 正常运行路径里出现 legacy 文件读写时测试直接失败。

### 执行步骤

1. 增加 V2 guard 测试工具。

   新增测试 helper：

   ```text
   tests/runtime_v2/test_no_legacy_hot_path.py
   ```

2. 在测试里 monkeypatch 以下函数，一旦 V2 正常路径调用就报错：

   - `_load_llm_history`
   - `_save_llm_history`
   - `_load_work_messages`
   - `_save_work_messages`
   - `_load_ui_events`
   - `_save_ui_events`
   - `_rebuild_llm_work_from_ui`
   - `reconcile_llm_work_to_ui_user_count`
   - `repair_compacted_llm_history_from_ui`

3. 给允许例外加明确白名单：

   - migration 函数
   - V1 模式测试
   - debug/export 工具

4. 把 V2 入口按场景覆盖：

   - 新会话发送消息
   - 已有会话发送消息
   - continuation
   - stop 后继续
   - stream reconnect
   - messages loading
   - count loading

### 验收标准

- V2 热路径 legacy 调用有自动测试保护。
- 新增 legacy 读写必须显式说明属于 migration/debug/export。

## 阶段 3：V2 模型历史纯化

### 目的

发送 API 前只从 Runtime V2 model projection 构建上下文，减少准备耗时并消除 legacy 干扰。

### 现状

已完成：

- V2 下发送前不再读取 `work_messages.json`。
- V2 持久化不再写 `work_messages.json`。
- pre API timing 已记录主要阶段耗时。

仍存在：

- RuntimeModelProjection 缺失时仍可能 fallback `llm_history.json`。
- continuation 中 projection 缺失时仍可能调用 legacy reconcile。

### 执行步骤

1. 修改 `_load_model_history_dicts_v2_primary()`：

   - V2 模式下只读 `RuntimeModelProjection`。
   - projection 缺失时返回明确错误状态。
   - 不自动 `_load_llm_history()`。
   - 不自动 `sync_from_legacy_if_needed()`。

2. 新增显式 migration 入口：

   ```text
   migrate_legacy_session_to_v2(session_id)
   ```

   只在以下场景调用：

   - 用户主动迁移。
   - 打开旧会话时后台迁移。
   - 管理命令/维护脚本。

3. continuation 路径调整：

   - V2 continuation 只读 RuntimeModelProjection。
   - projection 缺失时中止并返回 migration required。
   - 不调用 legacy reconcile。

4. sanitize 逻辑调整：

   - V2 sanitize 只裁剪 model projection 的尾部未闭合 tool_call。
   - 通过 V2 event 记录修复。
   - 不写 legacy `llm_history.json`。

### 验收标准

- V2 发送 API 前不读取 `llm_history.json`。
- V2 发送 API 前不读取 `work_messages.json`。
- `pre_api_timing` 中 legacy load/reconcile 项为 0 或不存在。
- projection 缺失时不会静默 fallback。

## 阶段 4：V2 UI 历史纯化

### 目的

解决 TOC 和正文加载时序错乱、页面闪动、滚动被打断、工具过程块丢失等 UI 侧问题。

### 执行步骤

1. `/sessions/{id}/messages` V2 下只读 `RuntimeUiProjection`。

   涉及文件：

   - `app/webui.py`
   - `app/runtime_v2/ui_projection.py`

2. `/sessions/{id}/messages/count` V2 下只读 projection index。

3. TOC 数据和正文数据使用同一 projection snapshot。

   目标：

   - 不允许 TOC 从一套数据来，正文从另一套数据来。
   - 不允许正文先加载 legacy，TOC 后加载 V2。

4. stream reconnect 只通过 V2 seq 恢复。

5. 移除 V2 UI 加载中的 `ui_events.json` fallback。

   fallback 改成：

   - 返回 migration required。
   - 或触发显式 migration。
   - 不直接混读 legacy。

### 验收标准

- 打开 V2 会话不会读取大 `ui_events.json`。
- TOC 不再反复清空/重建。
- 正文不会先显示新会话 logo 再跳成历史。
- 工具执行过程从 V2 UI projection 可完整恢复。

## 阶段 5：V2 分支/截断/repair 原生化

### 目的

彻底移除 V2 对 legacy rebuild 的依赖。

### 执行步骤

1. V2 truncate：

   - 不裁剪 `ui_events.json`。
   - 不重建 `llm_history.json`。
   - 追加 V2 event：

     ```text
     visible_range_changed
     model_history_truncated
     ```

2. V2 branch：

   - 从 event seq 派生新 session。
   - 复制必要 blobs。
   - 生成新 session `events.jsonl`。
   - 不复制 `work_messages.json`。

3. V2 repair：

   - 不再调用 `repair_compacted_llm_history_from_ui()`。
   - 新增 V2 repair events：

     ```text
     run_marked_interrupted
     model_tail_sanitized
     projection_rebuilt
     ```

4. V2 append tail：

   - 禁止用 legacy `ui_events` 拼接后重建 history。
   - 改为追加 V2 event segment。

### 验收标准

- V2 分支/截断/repair 不读写 `llm_history.json/work_messages.json`。
- V2 分支后新会话能独立投影 UI 和 model history。
- 历史工具过程不会因分支/截断消失。

## 阶段 6：性能收尾

### 目的

在边界干净后，再针对发送 API 前耗时做性能优化。

### 执行步骤

1. token 估算增量化。

   - 优先使用 API 返回 usage：

     ```text
     prompt_tokens
     completion_tokens
     ```

   - 没有 usage 时才估算。
   - 每轮只更新增量，不扫描完整历史。

2. RuntimeModelProjection 缓存。

   - 基于 `events.jsonl` 的 size + mtime_ns。
   - 无变化时复用 projection。

3. MCP 工具定义缓存。

   - 按 server config + enabled tools hash 缓存。
   - 每轮发送前不重复完整加载。

4. subagent tool filter 缓存。

   - 按 session/subagent mode 缓存工具列表。

5. context policy idle wait 优化。

   - 只等待同 session 的上下文任务。
   - 添加最大等待时间和日志。

### 验收标准

- 新建简单消息 API 前准备时间接近旧版本。
- 大历史会话 API 前准备时间可解释、可定位。
- `pre_api_timing` 能显示主要耗时来源。

## 阶段 7：legacy 只读导出与旧会话迁移

### 目的

让 V2 新会话完全不依赖 legacy 文件；旧会话通过 migration 进入 V2。

### 执行步骤

1. 新建 V2 会话默认不生成：

   - `llm_history.json`
   - `work_messages.json`
   - `ui_events.json`

2. 提供显式导出：

   ```text
   export_v2_session_to_legacy(session_id)
   ```

3. 提供旧会话迁移：

   ```text
   migrate_legacy_session_to_v2(session_id)
   ```

4. metadata 标记迁移状态：

   ```json
   {
     "runtime_v2_migration": {
       "status": "complete",
       "completed_at": "..."
     }
   }
   ```

### 验收标准

- 删除 V2 会话目录下 legacy history 文件后，V2 功能仍可用。
- 未迁移旧会话不能静默进入 V2 运行。
- migration 失败不会污染 V2 event log。

## 建议当前马上做的第一批改动

优先做这 5 项：

1. 给 V2 正常路径加 no-legacy guard 测试。
2. 禁止 V2 下 legacy truncate/branch/repair 反写 V2 model history。
3. 修改 continuation，projection 缺失时不再跑 legacy reconcile。
4. 修改 V2 model history load，移除自动 fallback legacy。
5. UI messages/count 读取统一到 RuntimeUiProjection，同一请求返回正文 + TOC 所需索引。

这 5 项完成后，三个问题会一起收敛：

- API 前少读大 legacy 文件。
- V1/V2 边界开始变硬。
- 工具执行过程不会再被 legacy rebuild 覆盖。

## 每次提交前必须跑的验证

后端：

```powershell
python -m py_compile app\agent_loop.py app\agent_harness.py app\webui.py
python -m pytest tests\test_agent_harness_reconcile.py tests\test_agent_loop_runtime_v2.py tests\runtime_v2 tests\test_webui_messages.py tests\test_feature_flags.py
```

前端如有改动：

```powershell
cd frontend
npm run build
cd ..
python scripts\check_frontend_dist_sync.py
```

UI raw module 语法检查如有前端 raw JS 改动，也必须执行。

