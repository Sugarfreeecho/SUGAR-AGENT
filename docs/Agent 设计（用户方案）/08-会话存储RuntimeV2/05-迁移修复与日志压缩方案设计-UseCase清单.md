# 迁移、修复与日志压缩 · 功能方案设计（UseCase 清单）

- 版本：2026-09-14 v2（覆盖至：HEAD `d022831` + API 识图工作区改动）
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
- **触发**：日志膨胀。
- **预期现象**：压缩后**语义不变**（回放结果一致）、文件变小；幂等可重跑；失败不动原文件。
- **依据**：`RuntimeV2LogCompactionService / RuntimeV2LogCompactionError`。

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

## 3. 边界

- 修复与压缩都是**离线/受控**操作（不并发写同一会话）；
- 损坏的应急语义见 01（Corruption）。
- 图片的统一准入、权限和全局 GC 见 [识图与多模态投影](../09-横切能力/02-识图与多模态投影方案设计-UseCase清单.md)。

## 4. 依据映射

见上表。

## 5. 版本记录

- 2026-09-14 v2：明确 RuntimeEvent 纯值边界、旧图片懒迁移和含附件会话导出。
- 2026-09-13 v1：拆分首版（承接 UC-811/813）。
