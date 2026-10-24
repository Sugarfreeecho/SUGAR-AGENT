# 写路径与摘要持久化 · 功能方案设计（UseCase 清单）

- 版本：2026-10-23 v13（交互与工具状态提交等待边界、单事务替换）
- 用途：逐条审查（四字段格式）。
- 适用实现：`runtime_v2/history_ops.py`（1282 行）、`agent_loop.py`（提交调用点）。
- 上级：`00-会话存储RuntimeV2整体设计.md`

---

## 1. 功能定位

"写"的家族：用户轮、答复、模型消息、历史替换、摘要提交——事务化、可回滚、可审计。

## 2. UseCase

### UC-8C1 历史事务
- **触发**：提交用户轮/答复/消息。
- **预期现象**：原子提交（一条 event + 快照更新）；失败不产生半截；重放同一提交幂等（以 seq 判重）。
- **依据**：`RuntimeHistoryOps`（_append_and_snapshot 等）。

### UC-8C2 历史替换
- **触发**：压缩/编辑导致历史被替换。
- **预期现象**：以显式事件记录替换（含原因与快照）；投影/模型视图立即一致；旧消息可从事件回溯。
- **依据**：`_runtime_v2_replace_model_history`、history_ops 替换段。

### UC-8C3 摘要提交
- **触发**：压缩完成（自动/强制/手动）。
- **预期现象**：`context_summary_committed` 事件落库（`source_seq` 为**可选**关联：仅显式传参时写入，ReAct 主路径当前不传）；重启后摘要可用；UI 回放可见压缩过程。
- **依据**：`commit_context_summary`（L423）。

### UC-8C4 回滚与恢复语义
- **触发**：提交后事件写失败 / 需要还原。
- **预期现象**：按准备好的回滚路径还原（不留半状态）；恢复数据（restore_context_summary 等）可被修复服务使用。
- **依据**：history_ops 回滚段（L597 restore 数据）、`repair.py`。

### UC-8C5 未变化摘要的进程内提交去重
- **触发**：ReAct 每轮尝试持久化与上次已提交内容相同的 context summary。
- **预期现象**：命中 `_RUNTIME_V2_COMMITTED_SUMMARY` 后直接跳过磁盘快照读取和重复提交；首次未命中仍读取权威快照比较，避免覆盖其他写者。
- **规则与边界**：该缓存只证明本进程已成功提交的摘要；冷启动或未命中必须回到 Runtime V2 权威读取，不能仅凭内存假定磁盘状态。
- **依据**：`agent_loop._runtime_v2_commit_context_summary`、`_RUNTIME_V2_COMMITTED_SUMMARY`。
- **10-18补充**：primary模式中，通用persist先更新内存主对话并判断摘要是否变化；命中已提交摘要时没有事实要写，直接结束，不再为无写入动作读取所有权文件。未命中或摘要变化仍先重新检查运行所有权，再读权威快照/同步提交。模型消息和工具结果各自的事实提交继续重新检查所有权；legacy写入也保留原检查。工具检查点移除一次紧接着会被persist重复执行的主对话派生。

### UC-8C6 压缩原文独立归档
- **触发**：本地压缩进入模型摘要轮。
- **预期现象**：被压缩前缀按原消息结构写入会话目录下 `history_context_archives/<archive_id>.jsonl`，每条记录获得稳定 `history:` 引用；摘要、活跃摘录和检索工具可引用同一份原文。
- **规则与边界**：归档采用临时文件替换方式一次性发布，创建后不可变；它是 Runtime V2 事件流之外的检索副本，不改写 event，不承担事件序列或快照的权威语义；同一摘要轮的模型重试不重复归档。
- **依据**：`history_context.archive_messages / archive_ref / archive_item_ref`、`agent_memory._compress_summary_round`。

### UC-8C7 执行终稿/工具结果与UI镜像的短事务提交

- **触发**：主会话chat/continuation在Runtime V2 primary且strict模式下，投递应持久化的tool_call、llm_reasoning或llm_response。10-21起task前后台子代理按02/10 UC-2J13复用此入口，默认manager进一步适用UC-8C9的一次追加。
- **预期现象**：一个工作线程内取得外层会话事务，先提交execution journal，再追加并投影对应UI事实；同线程/任务的内层提交复用外层文件锁和短读句柄。两者均成功后返回内部`_runtime_v2_committed`标记，主循环据此跳过第二次UI写入，然后发布公开事件。
- **规则与边界**：原模型助手/工具事实提交时机和用户、摘要、所有权事实边界保留。没有跨模型生成持锁，没有将事实提交移到后台；外层事务无await，读句柄在解锁前全部关闭。journal成功但UI失败仍保留已追加事实并传播失败，不返回已提交标记，不宣称两条追加具有崩溃回滚的原子性。内部标记在公开SSE前移除。非strict、非持久化事件及无合并能力的管理器沿原分离路径处理；子代理原未接线状态为10-19历史审查结果。
- **依据**：`SessionManager.commit_execution_ui_event`、`persist_execution_event(commit_ui=True)`、`astream_events / astream_continue_events`的emit实现；`tests/test_execution_ui_commit.py`、流式/续跑/子代理回归及UC-8A10的事务重入测试。

### UC-8C8 对已完成的只读工具结果合并事实追加

- **触发**：同一ReAct批次中多个只读工具已经完成；包括正常并行组已完成集合，以及提前执行队列中相邻且已完成的只读任务。
- **预期现象**：只收集已经返回的普通工具结果，仍为每个工具写独立`model_tool`事实；一份会话事务、一次文件追加/flush及一次投影发布完成该组提交。批次成功后才更新内存历史及已提交标记，随后沿原严格执行journal/UI交付路径逐项发布。关联日志记录批次项数与提交耗时。
- **规则与边界**：不为凑批等待尚未完成的工具；等待下一个未完成任务、处理steer或发送下一次API之前，已完成结果必须提交。单条、写工具、控制/压缩结果及不支持批次API的管理器保留原路径；取消/失败兄弟任务不阻止已成功完成结果先建立检查点。批次提交前重新检查所有权，失败传播且不标记成功；没有把模型事实、摘要或所有权边界移到后台。批次是一次追加多个事实，不宣称对文件系统写入失败具有跨事实崩溃回滚能力。UI事实仍按UC-8C7严格提交，全部完成后才继续API。
- **依据**：`RuntimeHistoryOps.append_model_tool_results`、`agent_loop._persist_completed_tool_batch/checkpoint_ready_tool_results`、`SessionEventLog._append_many_unlocked`；`tests/runtime_v2/test_completed_tool_batch.py`、`tests/test_runtime_noop_persistence.py`、工具steer/续跑及完整真实工具loopback基准。批量追加也可发布UC-8A12回执；超过256KiB的批次不为该缓存额外拼接完整编码缓冲。
- **严格UI交付补充**：同一已完成批次通过一次跨loop确认和一次工作线程调用提交execution/UI；每个工具的两类事实仍独立、顺序追加，整个批次成功后才逐项公开。事务内复用追加句柄见UC-8A13。桥内批次封套用私有对象键识别，不进入公开SSE；普通事件不能伪造该封套。取消通知传入工作线程，每项前及journal/UI之间检查；失败不公开成功结果，不发送后续API。非strict、子代理转发、不可持久化事件和不支持批次方法的管理器走原分离路径。工具计数按批次实际项数更新；纯文本工具结果不再逐字符遍历寻找附件块。

### UC-8C9 主/子代理完成事件一次追加与投影

- **触发**：默认SessionManager在primary+strict模式提交已完成tool_call、llm_reasoning或llm_response，包含task前后台子代理的同一调用。
- **预期现象**：在现有会话事务及journal锁内，私有执行状态预演沿用原record的去重/流式归并规则，准备相同顺序的execution/UI事实；经源文件身份、尺寸、时间和next_seq重验后，一次`_append_many_unlocked`写入并flush，再一次发布快照，最后用普通增量读取刷新journal缓存。四工具保留八条事实与各自执行seq引用，将原八次显式flush合为一次；单条终稿的两条事实也合并。原EventLog路径未显式调用os.fsync，不将此收益描述为减少fsync。
- **规则与边界**：预演不发布缓存、快照或成功回执；源变化、未知文件身份、bootstrap、特殊事件及自定义manager协议采用失败或原路径。追加/投影失败传播，已落盘事实仍可重放恢复，不承诺文件写失败的跨事实原子回滚。取消在写前阻止提交、写后先保持派生视图一致再传播；整批成功才公开逐条结果。用户轮、模型消息、摘要及所有权仍在原API前事实边界完成。子代理复用本路径，但其后台loop仍不使用主入口StreamEventBridge。
- **10-21后续预演优化**：在外层真实journal锁内，只复制状态根和records映射；首次更新某条既有record时再深复制该条及嵌套值，其他record/根字段只读共享。私有预演明确只接收tool_call、llm_reasoning、llm_response，不能将本优化直接套用到会修改其他状态字段的中断/回滚协议。私有状态不用再次查找全局journal缓存锁，普通journal读写的锁保持；每条record沿用真实SessionEventLog事务/目录校验，最终文件/句柄/seq守卫及普通journal补尾全部保留。
- **验证**：原19项加3项覆盖预演失败时既有嵌套payload及事实不变、预演不解析共享缓存名且仍逐条进入真实事务、拒绝其他journal协议。存储/恢复、计时及实际主/前后台子入口相关组合519 passed、0线程异常警告、源码无漂移；200既有record/4更新的12组交替内存原型状态等价，带tracemalloc的P50 10.1745→0.4515ms，仅证明预演机制。完整轮间尚待新源码验收，详见[10-21报告§11](../../performance/agent-subagent-interround-2026-10-21.md#11-完成事件预演及发送前尾段补修)。
- **依据**：`runtime_v2/execution_ui_batch.py::commit_display_batch`、`SessionManager._commit_display_batch_if_supported`、`tests/test_native_execution_ui_batch.py`（19项含取消、源变化、流式归并、去重及恢复）。真实主/子矩阵、源码指纹和门禁见[10-21报告](../../performance/agent-subagent-interround-2026-10-21.md)。

### UC-8C10 普通ReAct事实提交离开事件循环并保持完成边界

- **触发**：普通助手中间消息、已完成工具的单条检查点、已有工具批次及其普通补偿路径需要写模型事实。
- **预期现象**：`run_fact_commit`在后台执行原同步函数，所属协程等待写入完成再发布内存回执/进行UI交付或下一API；主和task子代理共用ReAct调用点，其他协程可继续运行。没有减少事实、忽略flush、跳过身份/seq校验或改变工具事实顺序。
- **规则与边界**：进入此入口的已完成结果已经选定为待提交事实；即使取消发生在线程排队期间，也先等待原写函数处理，不能丢弃已完成工具结果。写函数仍以实时写栅栏拒绝失去所有权的写，未绕过原取消/交接规则。重复取消不留下脱离生命周期的writer。成功后在原loop同步发布内存历史、checkpoint集合及`_history_persisted`，之后才传播取消。写失败不发布成功回执。用future承载线程，避免取消包装Task时误判同步writer已经结束。控制结果替换、压缩摘要、初始用户提交与所有权转交仍保留原路径，不把本改动泛化为全部写入已异步化。
- **路径作用域**：会话路径缓存同时校验线程及async task所有者。复制上下文进入另一线程/task时重新解析，自己的事务内才能复用；退出不清空父作用域。原session索引、目录身份、别名/reparse及未知身份守卫保持。新增跨线程/跨task用例与原目录替换、索引变化、关闭租约测试共同验证。
- **观测**：每次写的`fact_commit_await`关联session/run/iter，≥50ms记录，含提交、worker进入/结束、loop恢复及内存回执子段；原`model_commit/model_commit_batch`仍是内层事实操作。包络不能相加，取消前未进入的任务没有伪造worker/写入端点。
- **依据**：`app/agent_fact_commit.py`、`agent_loop.py::checkpoint_completed_tool_result/checkpoint_ready_tool_results`、`SessionManager._session_path_resolution_scope`、`tests/test_agent_fact_commit.py`、`tests/test_session_path_scope_owner.py`。675项相关组合与收益限制见[报告§13](../../performance/agent-subagent-interround-2026-10-21.md#13-事实提交与hook准备的事件循环隔离补修)。

### UC-8C11 运行写栅栏的全局锁范围

- **触发**：其他session注册/恢复运行时，本session的事实写入、事件发布和取消仍需检查实时归属。
- **预期现象**：注册和清理使用进程内逐session注册锁及原OS事务；owner检查、临时fence写入与replace在全局map锁外。写入成功后才短暂取全局锁发布内存归属；同session串行顺序保持，其他线程/loop查归属及abort不等其文件I/O。
- **规则与边界**：不缓存token或跳过实时磁盘校验；其他活进程/未知owner仍拒绝，写失败不发布，旧清理不能删新fence。逐session锁进程内保留，不能回收有等待者的锁。此处保留原文件写入/replace协议，不将其等同于新增fsync保证；同一loop同步注册和自身文件检查仍有阻塞可能。四类事实与转交仍在原关键路径。
- **依据**：`_steer_fence_registration_lock / _register_steer_run_control / _clear_steer_run_control / _state_run_has_write_fence`；4项新增并发回归及主/前后台子/ownership等最终113项通过、源码无漂移。新锁/路径/读盘计时用于后续归因，当前进程未加载，见[报告§15](../../performance/agent-subagent-interround-2026-10-21.md#15-第二次重启后的写栅栏全局锁隔离)。

### UC-8C12 人机交互事实复用已校验快照

- **触发**：问题/审批的创建、决议、取消、过期或分析写入，执行journal可能已使发布快照落后。
- **预期现象**：同一次事务校验所得快照直接传入追加步骤，使用既有`project_after_append`连续补尾并更新已读来源边界；不再在校验和追加两处各重放一次全日志。
- **规则与边界**：投影版本、来源identity/size/mtime和连续seq校验保持，seq相等也不跳过源替换检查，缺失/损坏派生戳和异常源回退重建。公共get/list只深复制选中的交互记录，内部只读视图不能被外部调用者修改。事实、checkpoint和pending索引仍按原顺序完成后才推送请求；线程执行不改变等待边界，取消创建会先结算并清理问题。
- **依据**：`human_interaction/service.py::_snapshot_locked/_append_locked/_snapshot/get/list/wait_for_user_answers`；正常尾部0次全量读取、源替换/派生损坏、嵌套隔离与取消等13个新增用例，最终相关200项通过；见[专项报告](../../performance/ask-user-card-latency-2026-10-23.md)。

### UC-8C13 待办/Goal 工具提交与扩展状态替换
- **触发**：模型调用 `update_todo / create_goal / get_goal / update_goal`，或宿主调用扩展状态 `set_latest`。
- **预期现象**：模型工具的同步磁盘操作通过 `run_fact_commit` 在线程运行，事件循环可继续处理其他请求；成功提交之后才发布工具回执。待办使用私有 manager 会话缓存预演，成功内存回执在原循环发布，同一 manager/session 的工具更新按序完成。失败不替换原缓存，取消等待已选写入收敛，已成功事实仍发布内存回执。
- **规则与边界**：`set_latest` 是无条件替换，在一次 session 事务内读取最新修订、追加 extension_state_changed、更新投影与检查点，替代原先 get 后 CAS 的两个事务；显式 compare_and_set 的版本冲突规则保持。来源校验、锁和事实提交顺序保留。此处线程隔离针对模型工具 handler，未声称全部 Goal HTTP 控制入口都已迁移；主/子代理使用相同 handler 时共享优化。后台作业输出消费仅在游标/待交付结果/通知或保留缓冲边界变化时提交，实际消费确认仍等待完成。
- **依据**：`plugins/session-todo/host.py`、`plugins/agent-goal/host.py`、`agent_fact_commit.py`、`runtime_v2/extension_state.py`、`execution_services/jobs.py`；取消、并发次序与修订重放回归见 `tests/test_tool_efficiency.py`。

## 3. 边界

- 提交的**时机**属于 ReAct 写栅栏（../02-ReAct运行时/05）；
- 压缩算法本体见 ../09-横切能力/01。
- 归档搜索同时覆盖 `history_context_archives/*.jsonl` 与 `events.jsonl`；默认只返回清洗后的语义内容，显式设置 `include_source=true` 时才附 `source_file`，且始终不会修改两者。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-8C1 | `history_ops.py` L38+ |
| UC-8C2 | `agent_loop.py` L2352–2379 |
| UC-8C3 | `history_ops.py` L423；`agent_loop.py` L2379–2404 |
| UC-8C4 | `history_ops.py` L597 |
| UC-8C5 | `_runtime_v2_commit_context_summary`、`_RUNTIME_V2_COMMITTED_SUMMARY` |
| UC-8C6 | `history_context.archive_messages`、`agent_memory._compress_summary_round` |
| UC-8C13 | `run_fact_commit`、Todo/Goal host handler、`SessionExtensionStateStore.set_latest`、`ExecutionService.output` |

## 5. 版本记录

- 2026-10-23 v13：待办/Goal 模型工具状态提交离开事件循环，待办按序预演并在事实成功后发布缓存；set_latest 合并为单事务，job_output 跳过无变化持久化。

- 2026-10-23 v12：人机交互事务复用校验快照、严格增量补尾，读取只复制交互记录；保留异常来源重建与等待式提交/取消，记录200项定向验收。

- 2026-10-21 v11：按第二次重启的新证据，缩短运行注册的全局map锁；保留逐session串行、OS归属事务及实时token，增加4项并发回归和分段，最终相关113项通过，真实收益未验。

- 2026-10-21 v10：新增UC-8C10，普通助手/完成工具事实在线程执行但保持等待边界，取消先收敛并发布成功内存回执；路径作用域增加线程/task所有者，外层提交与worker计时分开。

- 2026-10-21 v9：私有完成事件预演按记录延迟复制，减少共享锁名称重复解析；保留真实事务/目录与最终源守卫，限制预演事件协议，补充519项门禁及局部内存原型范围。

- 2026-10-21 v8：新增UC-8C9，主/子代理完成事件私有预演后一次追加/投影，保留源守卫、取消收敛和事实可恢复性；明确flush与fsync的区别。UC-8C7中的子代理原调用限制为历史范围，当前task已按02/10 UC-2J13接通。

- 2026-10-18 v7：严格UI按已完成批次使用一次线程交付，保留逐项execution/UI事实及成功后公开屏障、取消、回退和私有封套；纯文本跳过附件块遍历。
- 2026-10-18 v6：新增UC-8C8，只对已完成只读结果合并model_tool追加；未变化摘要的无写入persist跳过多余所有权读取，实际事实写入的检查与关键路径保留。
- 2026-10-17 v5：新增UC-8C7，执行journal与对应UI事实在一个短事务中顺序提交，成功后防止重复镜像，保留失败与耐久事实边界。
- 2026-09-20 v4：补入本地压缩原文的不可变 JSONL 归档、稳定引用及其与 Runtime V2 权威事件流的边界。
- 2026-09-20 v3：补入未变化 context summary 的进程内提交去重及冷未命中权威读取边界。
- 2026-09-14 v2：澄清 `source_seq` 为可选关联；版本线更新至 `d022831`。
- 2026-09-13 v1：拆分首版（承接 UC-805/806）。
