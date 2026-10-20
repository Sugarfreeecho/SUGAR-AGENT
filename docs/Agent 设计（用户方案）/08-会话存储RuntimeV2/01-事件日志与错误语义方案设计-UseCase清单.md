# 事件日志与错误语义 · 功能方案设计（UseCase 清单）

- 版本：2026-10-18 v11（追加路径复用与seq缓存身份守卫）
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
- **规则与边界**：ReAct 写入路径（`append_model_message` 等）上的 Busy 超时按 fail-closed 落地——记 `Runtime V2 model append failed` WARNING 与 `runtime_v2_transaction_timeout … stage=in_process_lock` 诊断，该次运行结算为 `run_failed`（终态带错误文本），仍在飞、未结算的工具执行标为 `unknown`；不静默继续、不自动降级。预算与调整见 UC-8A5；大日志侧的治本手段见 05·UC-8E7。
- **依据**：`RuntimeEventLogBusyError`、`agent_loop._runtime_v2_append_model_message`（告警后重抛）、`_RuntimeV2RunLifecycle`（终态唯一提交）。

### UC-8A4 损坏语义（Corruption）
- **触发**：日志文件被截断/串行错乱。
- **预期现象**：抛 CorruptionError 并**拒绝静默覆盖**；可交给修复服务（见 05）；受影响范围有提示。
- **依据**：`RuntimeEventLogCorruptionError`、`repair.py`。

### UC-8A5 运行时开关
- **触发**：部署环境差异（V2 主/严格模式、事务超时）。
- **预期现象**：`runtime_v2_primary/strict/enabled` 语义清晰；严格模式下不合规路径直接失败（而不是静默降级）。
- **规则与边界**：ReAct 事务预算由 `RUNTIME_V2_REACT_TRANSACTION_TIMEOUT_SECONDS`（兼容旧名 `RUNTIME_V2_TRANSACTION_TIMEOUT_SECONDS`）控制，默认 10 s，非正值视为无限等待（维护类调用默认无限，避免误杀大整理）；2026-10-05 维护把部署值调至 30 s。预算只是容忍度——超大会话应先压缩（05·UC-8E7），否则排队仍会逼近上限。
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
- **规则与边界**：原 Busy 超时与跨进程互斥保持；进程内RLock本来已按会话复用，最初的计时调整没有扩大持锁窗口。10-17追加的journal/UI短事务合并和同任务重入见UC-8A10、UC-8C7。无达到阈值的记录只表示未观测到相应慢事件，不能证明不存在更短等待。
- **依据**：`SessionEventLog._lock_for` 及事务锁/索引计时；[09/04 · UC-9D11](../09-横切能力/04-观测与运行看板方案设计-UseCase清单.md)。

### UC-8A8 派生加速器：UI 行段与执行恢复检查点（2026-10-07）

- **触发**：打开历史页/翻页/追加后扩展索引；执行日志终态事件提交后。
- **预期现象**：UI 索引可只引用行段位置（`row_locations` + `UI_ROW_PROJECTION_VERSION`），按偏移直读并逐段 sha256 校验；执行日志冷读优先加载检查点（`EXECUTION_RECOVERY_VERSION`），再从其封存的字节边界增量回放。
- **规则与边界**：全部为**可重建派生品**——版本不符、源被替换、校验失败、段损坏只丢弃并回到事实重放，绝不让持久追加失败化；发布前对事件源做双相封存（head/tail 廉价守卫 + 全量 sha256）；"等大小但 mtime 变化"按修复过的日志拒绝信任；跨进程写检查点复用快照存储的跨进程锁；**删除会话先取消待写检查点**；加载与逐出只影响速度，不影响事件语义与修复路径（UC-8A4）。
- **依据**：`ui_row_store.py`、`recovery_checkpoint.py`、`derived_cache.py`、`event_log.iter_from_offset`、`execution_journal.read/checkpoint_cached`；`tests/runtime_v2/test_ui_projection.py`、`tests/test_session_loading_performance.py`。

### UC-8A9 运行作用域内复用会话路径

- **触发**：一次 ReAct 运行或单次主循环事件投递，或独立事实事务已取得进程内锁与跨进程锁后，重复访问同一会话路径。
- **预期现象**：第一次按原规则解析根目录、子代理索引和所有权，后续复用规范路径，避免每个派生访问重复执行 Windows 最终路径查询。
- **规则与边界**：每次命中仍以 lstat 核对根目录及其下每级目录的设备/文件身份、类型和链接属性；每次解析还检查全局子代理索引的设备、文件身份、mtime 和 size，包含其他管理器/进程写入的失效。变化即重新解析，解析期间索引变化则不发布缓存。未创建目录、reparse 路径、配置根路径非规范形式不缓存；容量最多 128 项。子代理索引本地写入也清空当前缓存；循环父索引按原规则拒绝。退出最外层运行/投递/事务清空并关闭作用域，复制到其他线程的旧上下文不能继续复用。独立事务和下一次 ReAct 重新解析；嵌套事务复用运行作用域但仍逐次核验，不延长原持锁窗口、不降低 fsync 或路径边界检查。
- **依据**：`agent_loop.react_node / _runtime_session_path_scope / astream_events / astream_events_continuation`、`SessionEventLog.session_transaction`、`SessionManager._session_path_resolution_scope / _resolve_session_path / _session_subagent_index_identity / _session_directory_identity / _save_subagent_index`；`tests/test_session_path_transaction_cache.py`。

### UC-8A10 事务内复用短读句柄与缓冲小后缀

- **触发**：Windows上，执行journal/UI合并交付的短事务显式启用读复用，期间head/tail、稀疏seq锚点和小后缀验证反复读取相同日志。
- **预期现象**：持有跨进程事务锁期间，每个源文件复用一个只读句柄；作用域最多32个，超额逐出。每次借用重新核对路径与句柄的文件身份、重新读取校验字节，结束即丢弃读前缓冲。物化后缀和 journal 有界追尾在≤256KiB时先读成局部字节缓冲，释放共享句柄后再解析/yield；大后缀、全量和普通流式迭代仍使用独立流。
- **规则与边界**：所有复用句柄在合并交付事务解锁前关闭；普通事务、修复、压缩、迁移和事务外读取均不保留读句柄，避免同一维护事务稍后替换自身源文件时被阻挡，不能常驻或跨独立提交保留。Windows实验中的常驻方案会令跨进程os.replace/压缩失败，已放弃。没有缓存字节、hash或验证通过结果，head/tail、完整封存、mtime/size、同大小恢复mtime的修改、文件替换仍重新检查。嵌套事务只对同一目录身份、同一线程及同一异步任务的活跃租约重入；子线程/子任务或关闭后复制的上下文必须重新取得锁。取消、异常、逐出与目录删除均释放句柄；Busy预算及其他进程互斥保留。
- **依据**：`read_probe.py`、`SessionEventLog.session_transaction / _event_read_stream / read_after_seq`、`derived_cache.source_boundary`、`ExecutionJournal._state`；`tests/runtime_v2/test_read_probe.py`、事务跨进程超时、日志压缩及执行恢复测试。真实前缀隔离交付297→160ms的对照见[性能报告§9](../../performance/agent-interround-2026-10-17.md#9-结果交付路径的继续定位与修改)，不外推成全链路倍率。

### UC-8A11 已知成功追加的执行日志边界增量计算

- **触发**：执行journal在已持有会话事务/进程间写锁及journal锁时追加`execution_recorded`。
- **预期现象**：事实仍按原写入/flush契约同步提交；私有append receipt记录写入句柄的前后身份/长度/mtime及实际UTF-8行字节。与上次已验证的边界完全匹配时，用这些已写入字节更新head/tail哈希，避免追加后为计算派生校验边界再次open日志。
- **规则与边界**：每个journal状态只保留最多4096字节head和4096字节tail，纳入现有内存预算；不在事件、公开SSE或恢复检查点中持久化。外部追加、替换、字节数/mtime/先前guard不匹配、身份不可用或缺少回执时按原方法读盘重建。普通`source_matches`仍读取实际字节，检查点封存/加载仍核对完整前缀哈希；本优化不是跨次读取时复用校验结论。UI、模型消息、压缩/摘要、所有权转交的事实边界不延后。
- **依据**：`event_log._append_unlocked(append_receipt=...)`、`derived_cache.SourceWindow/source_boundary_window/extend_source_window`、`ExecutionJournal._state/_append`；`tests/runtime_v2/test_incremental_source_boundary.py`覆盖UTF-8窗口边界、外部写入/替换、恢复mtime后的独立验证、检查点恢复与回执不落盘。

### UC-8A12 同进程成功追加回执衔接

- **触发**：模型事实、执行草稿和UI事实交错追加；下一次journal追尾或投影更新需要读取刚提交的事实。
- **预期现象**：`_append_unlocked/_append_many_unlocked`完成写入、flush及原有追加收尾之后，发布不可变的实际UTF-8字节及写入句柄前后stat。按路径保留最多32次追加回执、256KiB，最多64个路径（原始字节总上限16MiB，另有小量对象开销）。前一回执的after与下一条before必须在设备、文件身份、长度、mtime四项连续；超大追加、断档或逐出只失去加速。
- **规则与边界**：调用方先重新stat实际命名文件；缓存尾端与当前文件、缓存首端与既有source须逐项相同。journal还须通过UC-8A11原始窗口/guard核对，才从已成功写入的字节回放并推导新边界。原始写入失败不发布成功回执；外部进程写入、未覆盖的批量写路径、替换、截断、mtime失配或缓存缺失均回到实际文件。该缓存没有文件句柄，不把读取校验结论跨提交复用；独立`source_matches`、检查点封存及加载仍读取真实文件和完整前缀哈希。四类发API前的事实边界继续同步。
- **依据**：`SessionEventLog._remember_owned_append/recent_owned_append`、`ExecutionJournal._state`、`SnapshotStore._read_stamped_suffix`；`tests/runtime_v2/test_owned_append_tail.py`覆盖交错追加、缓存缺失/超限、外部追加、替换、mtime变更、追加收尾失败及冷恢复。真实样本及验证见[10-18报告](../../performance/agent-session-8533-run-8298-2026-10-18.md)。

### UC-8A13 已完成结果交付批次内复用追加句柄

- **触发**：主会话strict交付一组已经完成的工具结果，已取得会话跨进程事务锁，且批次同步执行、无await。
- **预期现象**：`batch_append_scope`只为该会话的一个events.jsonl保留追加句柄，execution/UI仍逐项写入并逐次flush及发布真实字节回执；减少重复open/close。每次借用重新核对命名文件与句柄身份，身份不可用走普通打开路径。
- **规则与边界**：仅显式交付批次启用，普通追加/维护不留句柄。写句柄在外层事务解锁前关闭；异常、取消、复制到其他线程/任务、失效租约都不能延用。没有跨API/工具执行持锁，也没有推迟事实flush。文件被替换则拒绝混写；关闭后仍支持跨进程替换和删除。多条追加不宣称具有崩溃回滚原子性。
- **依据**：`runtime_v2/write_probe.py`、`SessionManager.commit_execution_ui_events`；`test_batch_append_scope.py`、`test_execution_ui_commit.py`覆盖逐项可读、解锁前关闭、异常、过期/跨线程上下文、取消后不写后续项及最终源签名一致。

### UC-8A14 seq缓存键与本次实际路径绑定

- **触发**：读取或更新事件尾部seq缓存，路径resolver可能在两次调用之间切换命名空间。
- **预期现象**：缓存键使用本次已解析并stat的同一事件路径；不能取得A路径的mtime/size/seq后，再次解析出B路径作为键。正常四工具交付批次少20次重复路径解析/60次metadata查询，墙钟整体收益单独待验。
- **规则与边界**：不增加跨次路径缓存，不省略实际文件stat；外部追加、截断、路径切换继续失效重读。维护修复仍可通过同样规范形式的`_cache_scope_for`删除缓存。
- **依据**：`SessionEventLog._cached_last_seq/_update_seq_cache`；`tests/runtime_v2/test_seq_cache_path_identity.py`覆盖同size/mtime的A/B切换、单次解析、不同root和外部追加。实测见[88def复核](../../performance/agent-session-8533-run-88def-2026-10-18.md)。

### UC-8A15 追加内绑定路径与seq游标源身份

- **触发**：单条、批次或外部RuntimeEvent追加；或冷观察者读取尾部时路径映射/文件发生变化。
- **预期现象**：同一次追加的seq查找、事实写入和seq缓存更新使用一次解析得到的事件路径；省去重复resolver和冗余exists查询。下一次操作重新解析路径，无跨次句柄。
- **规则与边界**：缓存命中必须同时匹配device、非零inode、size、mtime_ns；未知身份及旧三字段缓存回事实读取。冷读前后源stat不一致不得发布缓存；写入缓存还核对flush后writer的fstat，防止把原文件seq挂到替换文件上。实际事实write/flush、事务锁和所有权边界保持同步；派生缓存失败不改变成功事实的返回。
- **依据**：`SessionEventLog.next_seq/_cached_last_seq/_update_seq_cache`及三种追加入口；`tests/runtime_v2/test_seq_cache_append_binding.py`共11项，覆盖保留size/mtime的替换、resolver切换、观察者与追加交错、未知身份、旧缓存及三种入口的flush后替换。性能与证据边界见[c004实跑与补修](../../performance/agent-session-8533-run-c004-2026-10-18.md)。

## 3. 边界

- 事件类型清单由 `event_schema.py` 白名单管理（新增类型需要登记）；
- 日志压缩见 05（不改变语义）。

## 4. 依据映射

见上表（全为 runtime_v2 文件）。

## 5. 版本记录

- 2026-10-18 v11：新增UC-8A15；同次追加绑定一次路径，seq缓存以实际源身份及读取/flush后的stat发布，未知或变化来源回退事实。

- 2026-10-18 v10：新增UC-8A14；seq游标与同一次stat的路径绑定，保留实时文件校验，修复二次解析切换命名空间时的错误缓存键。
- 2026-10-18 v9：新增UC-8A13，仅在已完成结果的同步短事务中复用一个追加句柄，逐项flush、逐次身份核对、解锁前关闭。
- 2026-10-18 v8：新增UC-8A12；成功追加回执有界衔接，省去同进程已写事实的重复打开/读取，未知来源与独立完整性验证保留读盘。
- 2026-10-17 v7：新增UC-8A11，只对已知成功追加推导派生边界，保存有界窗口、逐条件失效；事实和恢复检查点的独立校验契约保留。
- 2026-10-17 v6：新增UC-8A10，记录仅在事务持锁内复用读句柄、有界物化后缀和关闭租约保护；明确常驻句柄方案因跨进程替换失败被放弃。
- 2026-10-17 v5：新增 UC-8A9，运行/事务作用域复用规范路径，逐次核对目录和跨进程索引身份，补充下次运行重查和已关闭上下文拒绝复用。
- 2026-10-07 v4：新增 UC-8A8（UI 行段与执行恢复检查点；派生失败只降级、双相封存、删除会话取消语义）。
- 2026-10-05 v3：补充 Busy 在 ReAct 写入路径的 fail-closed 落地链路（WARNING → `run_failed` → 在飞执行标 `unknown`）与事务预算实践（默认 10 s、部署 30 s）；交叉引用 05·UC-8E7。
- 2026-09-30 v2：新增 UC-8A6/8A7，记录稀疏索引无变化跳过、读侧尾部/重建正确性、52 项专项回归，以及索引与两类锁获取诊断；事实日志提交保持原契约。
- 2026-09-13 v1：拆分首版（承接 UC-801/802）。
