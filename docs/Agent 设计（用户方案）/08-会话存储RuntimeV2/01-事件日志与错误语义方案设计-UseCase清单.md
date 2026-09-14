# 事件日志与错误语义 · 功能方案设计（UseCase 清单）

- 版本：2026-09-13（覆盖至：HEAD `6acc6bf`）
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

## 3. 边界

- 事件类型清单由 `event_schema.py` 白名单管理（新增类型需要登记）；
- 日志压缩见 05（不改变语义）。

## 4. 依据映射

见上表（全为 runtime_v2 文件）。

## 5. 版本记录

- 2026-09-13 v1：拆分首版（承接 UC-801/802）。
