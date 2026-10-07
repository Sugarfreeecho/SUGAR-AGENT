# 2026-10-07 会话加载第三波：UI 行存储、执行检查点与有界派生缓存

## 一、目标

打开会话 / 翻历史页不再重放整段事件日志：把**可重建的派生品**落盘，并可校验地直读；读取路径的内存占用有明确上限。

## 二、新增模块

| 文件 | 机制 |
|---|---|
| `app/runtime_v2/ui_row_store.py` | **不可变、可分址的 UI 行段**：`ui_rows_*.jsonl`，每行记录 `[文件号, 偏移, 长度, sha256]`；索引只存 `row_locations`/`row_version`（`UI_ROW_PROJECTION_VERSION=1`）；读取按位置直取、逐段校验；段损坏经失效路径重建一次；旧代在 120 s 宽限（容忍并发读者持旧索引）后回收 |
| `app/runtime_v2/recovery_checkpoint.py` | **执行日志检查点**：终态事件后合并调度（每会话一个实时状态引用、待写 ≤64、估算 ≤64 MB、单 worker 线程）；`EXECUTION_RECOVERY_VERSION=1`；跨进程锁 + 原子替换写 `snapshots/execution_recovery.chk`；`wait()/cancel()` 与删除会话联动；写失败只告警 |
| `app/runtime_v2/derived_cache.py` | **派生品校验与原子封存**：`source_boundary`（dev/ino + 4 KiB head/tail + mtime_ns/size）、`source_matches`（追加式守卫；等大小但 mtime 变化 = 修复过的日志，拒绝信任；仅在首次加载/发布前做全量 sha256）、`seal_source`（双相封存，发布期间源变化即失败）、`estimate_bytes`（缓存预算的保留体积估算） |

## 三、接线（改动）

- `event_log.py`：终态事件（`assistant_final_committed`/`message_assistant_final`/`run_finished`/`run_failed`/`run_interrupted`）追加后按需调度检查点（`checkpoint_cached`，失败不反噬追加）；新增 `iter_after_seq`/`iter_from_offset`/`read_metadata`（读取时回传文件身份、字节边界与最后 seq）。
- `execution_journal.py`：内存缓存（128 MB 软预算 + LRU 修剪，活跃生成会话免受修剪）；检查点加载 + 从封存边界增量回放（非单调或源被替换即丢弃并**只回退一次**）；`read(min_runtime_seq=, diagnostics=)` 下移过滤并回报来源/回放耗时；`record()` 前移 `_valid`/`_recent_write` 并调度检查点。
- `ui_projection.py`：索引内存缓存（32 MB）、行段增量追加与**尾部重投影**（`_reproject_ui_tail`：历史编辑/顺序修复只作用于派生行）、页缓存（64 MB；生成中会话只保留最新一页）、`seed_compacted_ui`（压实后直接种子行段）、全程 `diagnostics`。
- `log_compaction.py`：压实成功后种子 UI 行段（失败仅告警——事实已提交，派生品可按需重建）。
- `webui.py`：`/history_snapshot` 新增 `loading_diagnostics`（page/execution 明细进载荷与日志）；`execution_journal.read(min_runtime_seq=…)` 替代读取后过滤。
- `agent_harness.py`：删除会话先 `RecoveryCheckpoint.cancel()`（与既有快照检查点取消同口径）。
- `versions.py`：新增 `UI_ROW_PROJECTION_VERSION=1`、`EXECUTION_RECOVERY_VERSION=1`。

## 四、契约更新（7 处红测试随机制收尾）

| 用例 | 更新 |
|---|---|
| `test_ui_projection` ×2、`test_webui_messages` ×2 | 页面来源标签 `runtime_v2_seq_index → runtime_v2_ui_rows`（行存储直读路径的新契约；seq-index 标签仅剩薄索引退化路径） |
| `test_session_loading_performance::test_cold_journal_read_does_not_block_another_sessions_generation` | "慢读不阻塞他会话"的挂点从 `read_after_seq` 迁移到 `iter_from_offset`（生成器门闩，语义不变） |
| `test_session_loading_performance::test_incremental_index_stops_at_its_published_file_boundary` | "边读边追加"挂点迁移到 `iter_from_offset`（扩展现在从封存边界回放） |
| `test_ui_projection::…appends_after_index_read` | 挂点迁移到 `UiRowStore.read`（且使用 `app.runtime_v2` 前缀导入——仓库测试对同名模块存在两种导入副本，补丁必须打在投影实际使用的那一份类对象上） |
| `test_projection_versions::test_ui_index_with_stale_version_rebuilds` | 进程内索引缓存热时权威；用例先 `invalidate_cache` 再验"陈旧版本 → 磁盘重建" |

## 五、验证

- 全量 `pytest`：**2311 passed / 5 skipped / 0 failed**；node **34/34**；`py_compile` 与模块导入冒烟通过。
- 全部派生失败路径均只降级（告警），不改事实日志、不做登录式重试；`min_runtime_seq` 过滤语义与旧后置过滤一致。

## 六、边界与留意

- **收益未测**：本批提供机制与正确性证据；打开会话的整体提速仍需新代码加载后的同任务复测。
- `RecoveryCheckpoint._cancelled` 为终态集合（会话删除后不再调度）；当前仅删除路径使用。
- 派生品与事实的强一致依靠"封存 + 双相校验"；若未来出现第三方直接改写事件日志的需求，需走既有修复服务（08/01 UC-8A4）而非绕过守卫。
