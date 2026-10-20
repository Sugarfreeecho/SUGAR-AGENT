# 投影、回放与快照 · 功能方案设计（UseCase 清单）

- 版本：2026-10-18 v7（快照字节游标与成功写入尾部衔接）
- 用途：逐条审查（四字段格式）。
- 适用实现：`runtime_v2/projector.py`（1270 行）、`ui_projection.py`（1304 行）、`model_projection.py`、`snapshot_store.py`（580 行）、`blob_store.py`。
- 上级：`00-会话存储RuntimeV2整体设计.md`

---

## 1. 功能定位

从事件到"可用状态"的三层派生：状态投影（内部）、UI 投影（界面）、模型投影（请求），以及加速它们的快照。

## 2. UseCase

### UC-8B1 状态投影
- **触发**：读取会话状态。
- **预期现象**：由事件增量投影出会话状态（消息、运行、计划、上下文水位等）；投影结果与事件序列一致；token 过期标记触发按需重算。
- **依据**：`RuntimeProjector`、`_mark_context_tokens_stale`。

### UC-8B2 UI 投影与回放
- **触发**：界面打开/刷新/续看。
- **预期现象**：产出与界面一致的 SSE payload 序列；回放严格只读、不产生副作用；有序不重复。
- **依据**：`ui_projection.py`、`webui._runtime_v2_chat_sse_payload`。

### UC-8B3 模型历史投影
- **触发**：构建下一轮模型请求。
- **预期现象**：输出干净的消息序列（Responses 续接信息、内部标记被剥离）；不含 UI 专用事件。
- **依据**：`model_projection.py`（strip_responses_continuation_from_message）。

### UC-8B4 快照加速
- **触发**：长会话读取。
- **预期现象**：快照命中 → 快速返回；未命中/失效 → 从事件重建并写新快照；快照永不与真源"唱反调"。
- **依据**：`SnapshotStore`、`blob_store`。

### UC-8B5 一致性检查
- **触发**：诊断/修复入口。
- **预期现象**：经修复服务可对比"事件重放 vs 快照/镜像"并报告差异（`root_log_repair._verify_repaired_state` 与迁移校验）；通用的一键一致性诊断入口 🟡 规划中（不作为当前验收目标）。
- **依据**：`projector` 校验段 + `repair.py` 联动。

### UC-8B6 按需复制 Goal 子状态

- **触发**：Goal 查询仅需扩展状态，而不需要消息、UI、模型等完整投影的可修改副本。
- **预期现象**：复用既有 `read_consistent_view()` 的一致只读视图，保留事件日志新鲜度核对和必要重建；GoalManager 只复制提取出的 Goal。没有 Goal 时不复制其他字段。
- **规则与边界**：view 是共享只读对象，读取方不能就地改写；需要给外部调用方修改的 Goal 必须 deepcopy 后返回。本批调整调用方，未把 `SnapshotStore.read_consistent()` 的完整隔离副本语义改成共享引用，也未跳过快照恢复。
- **依据**：`app/agent_goal.py::GoalManager.get`、`runtime_v2/snapshot_store.py::read_consistent_view / read_consistent`；[02/09 · UC-2I12](../02-ReAct运行时/09-运行生命周期与Goal续跑防风暴方案设计-UseCase清单.md)。真实快照复制步骤 A/B 见 [09/05](../09-横切能力/05-性能优化基线与已完成项方案设计-UseCase清单.md)。

### UC-8B7 正常追加按序补齐投影尾部

- **触发**：助手/工具/system 消息、用户轮、终稿、结束 reconcile 或子代理账本提交时，执行日志等独立写入令缓存投影落后于事件日志。
- **预期现象**：投影版本匹配且紧邻新事件时直接增量应用；落后多条时，复用 `project_after_append()` 仅读取 `last_seq` 后缀，验证序号连续且覆盖本次新事件后依次应用。正常间隙不触发完整日志读入和完整投影。
- **规则与边界**：未建立投影、版本不匹配、后缀缺失/不连续或没有覆盖目标 seq 时，完整回放事实日志。用户/助手/工具结果等耐久提交和会话事务保持同步；仅快照作为派生物按既有策略后台写盘。版本检查也覆盖紧邻追加，不能因 seq 恰好相邻而继续使用旧投影版本。
- **依据**：`RuntimeHistoryOps._append_and_snapshot / _snapshot_for_update / commit_user_turn / commit_assistant_final / reconcile_model_history`、`RuntimeSubagentStore.append_event`、`RuntimeMirror`、`SnapshotStore.project_after_append`；`tests/runtime_v2/test_history_append_suffix.py`。各事实边界均验证补尾、旧版本完整回退、断档重建、幂等，镜像单条/批量追加也检查相邻快照版本。历史 38.3MB 前缀隔离实验的 1400.880→32.419ms 是局部机制对比，不是整体运行提速倍率。

### UC-8B8 降低派生快照后台编码和 seq 读取 CPU

- **触发**：后台 checkpoint 或显式快照写入，以及后台核对磁盘快照是否更新。
- **预期现象**：普通 JSON 值先通过共享类型检查并编码为 bytes，一次写入临时文件；缺失可选依赖或特殊类型时保留原 json.dump 流式编码。后台读取磁盘 seq 使用快速完整 JSON 解析，只在 last_seq 为精确 int 时直接取值，其他情况退回原整数转换。
- **规则与边界**：完整读取解析磁盘 JSON，不使用易陈旧的 seq 缓存或仅头部 regex。NaN、超大整数等旧数据保持原解析/编码语义。fsync、原子替换、会话和跨进程锁、新旧 seq 比较、事件源核验、取消和失败恢复均保留。快速写入会临时保留一份完整编码字节缓冲；这降低 CPU，但有与快照大小对应的额外内存成本。
- **依据**：`json_encoding.encode_plain_json`、`SnapshotStore._write_file / _read_disk_snapshot_seq`、`tests/runtime_v2/test_snapshot_store.py`。同机 24MB 真实快照的只读编码对照为 CPU 中位 359→125ms（各 12 次），不外推为 Agent 全链路倍率。

### UC-8B9 后台执行检查点的文件校验不持有运行中journal锁

- **触发**：`RecoveryCheckpoint`后台封存执行恢复状态。
- **预期现象**：journal锁内只核对状态可用、复制既有`STATE_FIELDS`和对应source；释放锁后验证实际文件边界、完整前缀哈希、编码、fsync和原子替换。文件校验变慢时，同会话的新执行事件仍可追加。
- **规则与边界**：冻结状态与source在同一锁内取得；之后追加的新事实可由恢复时的尾部回放补齐。截断/替换或边界不一致仍拒绝发布，取消在复制前与校验后、写入/替换前复查。磁盘格式和版本不变，UC-8A11的私有原始窗口不进入恢复检查点。
- **依据**：`RecoveryCheckpoint._write`、`tests/runtime_v2/test_incremental_source_boundary.py::test_checkpoint_boundary_validation_does_not_hold_the_live_journal_lock`；并发测试阻塞校验并验证新事实可提交、旧检查点加新尾部可恢复。

### UC-8B10 使用已盖章的字节边界补齐快照

- **触发**：投影版本仍匹配，但执行日志等事实夹入，导致投影落后于本次新事件。
- **预期现象**：`stamp_event_log`在既有size/mtime之外记录设备和文件身份。正常追加优先从旧size对应的完整行边界读取至当前文件末尾；匹配UC-8A12成功回执时直接解码实际写入字节，否则有界读取真实文件后缀，避免重复打开稀疏索引、校验锚点和解析前面的stride。
- **规则与边界**：重新stat、身份核对、读取身份及完整EOF核对、逐条连续seq和最终through_seq检查全部通过才应用；任何一条不满足不发布部分投影。旧格式快照及无效游标使用已有索引/全量回退；已知替换或截断直接完整投影。版本不符始终完整重放。投影更新继续遵守copy-on-write，不修改已发布快照；用户、工具、终稿及reconcile提交的同步契约保留。新增stamp字段可选，旧快照兼容，无需改变事实或恢复检查点版本。
- **依据**：`SnapshotStore.stamp_event_log/project_after_append/_read_stamped_suffix`；`tests/runtime_v2/test_snapshot_suffix_cursor.py`覆盖旧格式、游标落在半行、序号/目标不符、源替换、未完成尾行及三类事实边界与全量投影一致；原`test_history_append_suffix.py`继续验证旧格式的索引回退契约。

### UC-8B11 在服务启动时初始化快照后台线程

- **触发**：WebUI服务启动，进入恢复runner和接收用户请求之前。
- **预期现象**：经to_thread调用幂等`SnapshotStore.start_checkpoint_workers()`，并发调用仍受原配置上限约束（默认2、范围1–8），预热不创建会话、事实或快照文件；首次提交直接复用已有线程。
- **规则与边界**：预热只前移线程创建，不提前提交事实。原异步开关、10ms可配置短等待、取消、后台排空和同步事实耐久语义保留；启动失败走原惰性重试，运行中提高worker配置仍可增建。没有将真实834ms发布包络全部归因Thread.start。
- **依据**：`webui._warm_runtime_checkpoint_workers/start_webui_lifecycle`、`SnapshotStore.start_checkpoint_workers`；`tests/test_checkpoint_warmup_and_local_phases.py`验证并发有界、无文件副作用、首事实无需再建快照线程、失败非致命和事实可恢复；[e046验收](../../performance/agent-session-8533-run-e046-2026-10-18.md)。

## 3. 边界

- 投影缓存失效规则由事件类型驱动（提交/替换/修剪等）；
- 快照是**加速器**而非事实：删除后系统仍能工作（只是慢）。

## 4. 依据映射

见上表。

## 5. 版本记录

- 2026-10-18 v8：新增UC-8B11，快照线程在服务启动时通过worker预建；保留失败惰性重试、配置上限和事实边界，补齐834ms发布包络的诊断。

- 2026-10-18 v7：新增UC-8B10，正常补尾改用盖章字节位置和可选成功回执；保留完整行、身份、连续seq、版本及全量回退。
- 2026-10-17 v6：补充UC-8B9，后台恢复检查点先冻结一致状态，再于journal锁外验证文件；保留完整哈希、取消及恢复格式。
- 2026-10-17 v5：补齐用户轮、终稿和结束 reconcile 的正常间隙补尾，子代理追加使用相同后缀校验；修复镜像/子代理相邻旧投影版本漏检。新增 UC-8B8，降低后台快照编码和完整 seq 解析 CPU，保留耐久、原子发布、取消和特殊数据回退。
- 2026-10-17 v4：增加 UC-8B7；明确独立事件夹入后的正常提交只补尾，并覆盖相邻旧版本、后缀断档和完整回退。
- 2026-09-30 v3：新增 UC-8B6，明确 Goal 一致读取只复制所需子状态、共享 view 只读与返回值隔离，保留完整快照 API 的原语义。
- 2026-09-14 v2：收紧一致性检查表述（现为修复/迁移校验入口）；版本线更新至 `d022831`。
- 2026-09-13 v1：拆分首版（承接 UC-803/804/807/808）。
