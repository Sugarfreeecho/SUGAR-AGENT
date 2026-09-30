# 事件日志与错误语义 · 功能方案设计（UseCase 清单）

- 版本：2026-09-30 v2（覆盖至：当前工作区；稀疏索引跳过无变化维护）
- 用途：逐条审查（四字段格式）。
- 适用实现：`runtime_v2/event_log.py`（777 行）、`event_schema.py`、`config.py`、`versions.py`。
- 上级：`00-会话存储RuntimeV2整体设计.md`

---

## 1. 功能定位

账本本体的读写规则：追加、游标、并发、损坏——全部显式。

## 2. UseCase

### UC-8A1 追加与顺序
- **触发**：任意状态变更提交。
- **预期现象**：事件以 seq 递增追加到 events.jsonl；一行一事件、可读；崩溃后已追加事件不丢。
- **依据**：`SessionEventLog`（append 段）、`event_schema.RuntimeEvent / now_iso`。

### UC-8A2 游标读取
- **触发**：读取（界面回放/SSE 续看/投影重建）。
- **预期现象**：支持 after_seq/before_seq/limit 读取；不重复不缺失；尾部读取（跟读新事件）可用。
- **依据**：`event_log`（read 段）、`webui._runtime_v2_event_dicts`。

### UC-8A3 并发写语义（Busy）
- **触发**：多进程/多线程同时写。
- **预期现象**：无法获取写权时抛出 **Busy 超时**（明确可重试错误）；不产生交错写坏行。
- **依据**：`RuntimeEventLogBusyError`。

### UC-8A4 损坏语义（Corruption）
- **触发**：日志文件被截断/串行错乱。
- **预期现象**：抛 CorruptionError 并**拒绝静默覆盖**；可交给修复服务（见 05）；受影响范围有提示。
- **依据**：`RuntimeEventLogCorruptionError`、`repair.py`。

### UC-8A5 运行时开关
- **触发**：部署环境差异（V2 主/严格模式、事务超时）。
- **预期现象**：`runtime_v2_primary/strict/enabled` 语义清晰；严格模式下不合规路径直接失败（而不是静默降级）。
- **依据**：`config.py`（runtime_version / strict / timeout）、`versions.py`。

### UC-8A6 无新稀疏锚点时跳过索引维护

- **触发**：向 `events.jsonl` 追加事件后维护 seq 偏移索引。
- **预期现象**：stride 为 32，只有本次追加包含 `(seq - 1) % 32 == 0` 的新锚点时才读取/更新索引；条目数实际增长才重写。无新锚点时跳过索引读取、序列化、fsync 和 replace。
- **规则与边界**：事件日志本身的追加、fsync 与事务顺序保留。索引只是可重建的派生加速器，旧锚点的偏移在追加后仍有效，读侧继续扫描尾部；缺失/损坏索引按原机制懒重建。跨锚点批量追加和 UTF-8 字节偏移必须正确。
- **依据**：`event_log.py` 的 seq offset 索引更新；`tests/runtime_v2/test_event_log.py`（锚点/非锚点、批量追加、after/before/latest/tail、UTF-8、非锚点追加后损坏索引恢复）。与 `test_history_ops.py` 合计 **52 passed**。

连续单条追加且已有索引时，每 32 条由 32 次重写降为 1 次；该结果只说明索引维护次数，不能解释为 Agent 总耗时减少 31/32。本批采用“无变化即跳过”，未新增后台去抖索引写入。

### UC-8A7 索引和事务锁的本地耗时诊断

- **触发**：索引维护或取得事务锁的局部耗时达到 50 ms。
- **预期现象**：`runtime_v2_seq_index_timing` 记录索引维护时间/条目数；`runtime_v2_lock_acquire_timing` 分开记录进程内锁等待与文件打开/跨进程锁获取。
- **规则与边界**：原 Busy 超时与跨进程互斥保持；进程内 RLock 本来已按会话复用，本批没有延长 Windows `msvcrt.locking` 持锁窗口。无达到阈值的记录只表示未观测到相应慢事件，不能证明不存在更短等待。
- **依据**：`SessionEventLog._lock_for` 及事务锁/索引计时；[09/04 · UC-9D11](../09-横切能力/04-观测与运行看板方案设计-UseCase清单.md)。

## 3. 边界

- 事件类型清单由 `event_schema.py` 白名单管理（新增类型需要登记）；
- 日志压缩见 05（不改变语义）。

## 4. 依据映射

见上表（全为 runtime_v2 文件）。

## 5. 版本记录

- 2026-09-30 v2：新增 UC-8A6/8A7，记录稀疏索引无变化跳过、读侧尾部/重建正确性、52 项专项回归，以及索引与两类锁获取诊断；事实日志提交保持原契约。
- 2026-09-13 v1：拆分首版（承接 UC-801/802）。
