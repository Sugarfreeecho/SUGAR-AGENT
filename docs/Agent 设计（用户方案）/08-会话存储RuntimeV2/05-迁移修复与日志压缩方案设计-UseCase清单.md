# 迁移、修复与日志压缩 · 功能方案设计（UseCase 清单）

- 版本：2026-10-05 v3（覆盖至：当前工作区；日志压缩实操与写预算维护补录）
- 用途：逐条审查（四字段格式）。
- 适用实现：`runtime_v2/migration.py`（511 行）、`repair.py`（606 行）、`root_log_repair.py`（564 行）、`log_compaction.py`（158 行）、`attachment_migration.py`。
- 上级：`00-会话存储RuntimeV2整体设计.md`

---

## 1. 功能定位

账本的"修史与瘦身"：旧数据迁入、坏数据修好、长日志压小——每步都可校验。

## 2. UseCase

### UC-8E1 v1→v2 迁移
- **触发**：打开旧格式会话 / 后台迁移任务。
- **预期现象**：迁移前扫描 → 迁移 → **校验通过才切换**（VerificationError 语义）；失败保留旧数据（可回退）；迁移清单/进度可查。
- **依据**：`RuntimeV2MigrationService / RuntimeV2VerificationError`、runtime sync worker（webui）。

### UC-8E2 子代理修复
- **触发**：子代理数据引用异常/顺序问题。
- **预期现象**：按确定性算法修复（可重放）；修复范围与结果有报告；不丢可救数据。
- **依据**：`RuntimeV2SubagentRepairService`。

### UC-8E3 根日志修复
- **触发**：主事件日志引用错乱（如 context_summary source_seq 断裂）。
- **预期现象**：按已知约束修复（如补 source_seq 引用）；修复前后可对比。
- **依据**：`RuntimeV2RootEventLogRepairService`（含 `context_summary_committed: ("source_seq",)` 约束）。

### UC-8E4 日志压缩
- **触发**：日志膨胀（含百 MB 级 / 万级事件的超大会话）。
- **预期现象**：压缩后**语义不变**（回放结果一致）、文件变小；幂等可重跑；失败不动原文件。
- **规则与边界**：压缩形态为单条 `runtime_snapshot_compacted`（内嵌投影基线 + UI 事件、seq 保持末值），随后重建索引、失效 UI 缓存；默认保留备份 `events.precompact.<last_seq>.jsonl.bak`，压缩后自动复核投影一致性、不一致即回滚。自动安全门槛（`_assert_offline_safe`）：存在活动 run、待人工交互、自身含分叉标记或被其他分叉会话引用时默认拒绝；被分叉引用的会话须显式 `--force`（既有分叉副本不受影响；压缩后不宜再从该会话新建分叉）。操作脚本：`scripts/compact_runtime_v2_logs.py <sessions_dir> <session_id…> [--all] [--min-bytes 16MB] [--force] [--no-backup]`；操作窗口内独占该会话事务锁，勿并发写同一会话。
- **依据**：`RuntimeV2LogCompactionService / RuntimeV2LogCompactionError`、`scripts/compact_runtime_v2_logs.py`。

### UC-8E5 附件迁移
- **触发**：旧版附件载荷格式进入。
- **预期现象**：旧 data URL、原始图片块和历史附件形态在事件仓库的明确读写边界迁移为耐久 `attachmentId` 引用；事件对外形态统一，日志与诊断输出不会包含原始 base64。
- **规则与边界**：`RuntimeEvent` 是纯值对象，构造和 `to_dict` 不执行文件读取、网络下载或附件写入；`to_dict` 仅做内存脱敏。迁移采用懒迁移，不破坏性批量重写全部旧 JSONL；唯一旧图片必须先准入成功才能删除原载荷。
- **依据**：`attachment_migration.migrate_payload / event_from_record`、`event_schema.RuntimeEvent`、`event_log.py`。

### UC-8E6 含附件的会话导出

- **触发**：调用 `GET /sessions/{sessionId}/export` 导出包含图片引用的会话。
- **预期现象**：归档除会话目录外，还包含从该会话文件扫描出的可达规范附件及 manifest；在另一环境导入附件包后，历史引用仍能解析到相同内容身份。
- **规则与边界**：只打包该会话可达附件，不打包全局对象库、请求缩放缓存、设备 grant 或队列 pin。构建期间发现会话条目越界即失败；临时 ZIP 在响应完成后删除。
- **依据**：`webui._build_session_export_archive`、`attachments.lifecycle.collect_references/add_bundle`。

### UC-8E7 超大会话的写延迟治理（压缩实操与预算调优）
- **触发**：单个会话事件日志达百 MB 级、写事务耗时升至秒级（`runtime_v2_write_timing` 数秒、工具结果消息提交排队），甚至撞上事务预算。
- **预期现象**：按“先压缩、后调预算”的顺序治理——压缩后写延迟与排队消除，预算调整只提高容忍度。2026-10-05 实操样本：某会话 106.4 MB / 21,971 条事件压缩为 44.3 MB / 1 条；压缩后续跑（新增 50 条事件）全程无超时。同批把事务预算 10 s 调至 30 s（01·UC-8A5）。
- **规则与边界**：压缩前确认无活动 run / 待人工交互（脚本自检）；被分叉引用须 `--force`（见 UC-8E4）；压缩期间勿向该会话发消息；备份在确认稳定前保留。本记录只说明该会话的局部治理结果，不外推为全局写性能结论；Busy 未命中失败时的落地链见 01·UC-8A3。
- **依据**：`scripts/compact_runtime_v2_logs.py`、`log_compaction.py::_assert_offline_safe`、实操样本（`workspace/sessions/a874ad4d-…`：压缩输出 21971→1、106,420,482→44,270,166 B；备份 `events.precompact.21971.jsonl.bak`；压缩后续跑事件 21972–22020）。

## 3. 边界

- 修复与压缩都是**离线/受控**操作（不并发写同一会话）；
- 损坏的应急语义见 01（Corruption）。
- 图片的统一准入、权限和全局 GC 见 [识图与多模态投影](../09-横切能力/02-识图与多模态投影方案设计-UseCase清单.md)。

## 4. 依据映射

见上表。

## 5. 版本记录

- 2026-10-05 v3：扩写 UC-8E4（安全门槛 / `--force` / 备份与校验回滚 / 单事件形态 / 操作窗口），新增 UC-8E7（超大会话写延迟治理实操与预算调整边界）。
- 2026-09-14 v2：明确 RuntimeEvent 纯值边界、旧图片懒迁移和含附件会话导出。
- 2026-09-13 v1：拆分首版（承接 UC-811/813）。
