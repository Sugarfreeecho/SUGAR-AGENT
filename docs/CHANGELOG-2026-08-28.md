# CHANGELOG — 2026-08-28

本批次来自 8/28 的两个 Codex 会话：game-arena 插件页面修复、执行轨迹性能优化（含 Runtime V2 日志压缩）。

## 一、Runtime V2 事件日志压缩（新）

- 新增 `app/runtime_v2/log_compaction.py`：基于 `SessionEventLog` + `RuntimeProjector` + `SnapshotStore` + `RuntimeUiProjection` 的日志压缩（旧事件折叠为摘要、保留投影与快照一致性）。
- 配套运维脚本 `scripts/compact_runtime_v2_logs.py` 与测试 `test_log_compaction.py`。

## 二、Runtime V2 历史/投影性能优化

- `history_ops`/`projector`/`model_projection`/`ui_projection`/`event_schema`/`versions` 适配压缩与性能路径；`agent_loop.py` 记录 `reconcile_model_history` 时序诊断；`agent_subagent.py` 同步适配。
- 新增 `test_process_aggregate_performance.py`（过程聚合性能回归）。

## 三、执行轨迹渲染性能优化

- `message-rendering.js`：流式期间跳过 feed chunk 溢出测量（`measureFeedChunkOverflow`），避免每块布局计算拖慢首条轨迹出现；首条轨迹立即显示，后续行继续平滑动画。

## 相关提交

- `feat(runtime_v2): event log compaction tooling`
- `perf(runtime_v2): history ops and projection performance`
- `perf(webui): execution trace first-row and overflow measurement`