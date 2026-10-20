# 写路径与摘要持久化 · 功能方案设计（UseCase 清单）

- 版本：2026-10-18 v7（已完成结果的模型事实和严格UI批次交付）
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

- **触发**：主会话chat/continuation在Runtime V2 primary且strict模式下，投递应持久化的tool_call、llm_reasoning或llm_response。
- **预期现象**：一个工作线程内取得外层会话事务，先提交execution journal，再追加并投影对应UI事实；同线程/任务的内层提交复用外层文件锁和短读句柄。两者均成功后返回内部`_runtime_v2_committed`标记，主循环据此跳过第二次UI写入，然后发布公开事件。
- **规则与边界**：原模型助手/工具事实提交时机和用户、摘要、所有权事实边界保留。没有跨模型生成持锁，没有将事实提交移到后台；外层事务无await，读句柄在解锁前全部关闭。journal成功但UI失败仍保留已追加事实并传播失败，不返回已提交标记，不宣称两条追加具有崩溃回滚的原子性。内部标记在公开SSE前移除。非strict、非持久化事件、子代理原调用及无合并能力的管理器沿原分离路径处理。
- **依据**：`SessionManager.commit_execution_ui_event`、`persist_execution_event(commit_ui=True)`、`astream_events / astream_continue_events`的emit实现；`tests/test_execution_ui_commit.py`、流式/续跑/子代理回归及UC-8A10的事务重入测试。

### UC-8C8 对已完成的只读工具结果合并事实追加

- **触发**：同一ReAct批次中多个只读工具已经完成；包括正常并行组已完成集合，以及提前执行队列中相邻且已完成的只读任务。
- **预期现象**：只收集已经返回的普通工具结果，仍为每个工具写独立`model_tool`事实；一份会话事务、一次文件追加/flush及一次投影发布完成该组提交。批次成功后才更新内存历史及已提交标记，随后沿原严格执行journal/UI交付路径逐项发布。关联日志记录批次项数与提交耗时。
- **规则与边界**：不为凑批等待尚未完成的工具；等待下一个未完成任务、处理steer或发送下一次API之前，已完成结果必须提交。单条、写工具、控制/压缩结果及不支持批次API的管理器保留原路径；取消/失败兄弟任务不阻止已成功完成结果先建立检查点。批次提交前重新检查所有权，失败传播且不标记成功；没有把模型事实、摘要或所有权边界移到后台。批次是一次追加多个事实，不宣称对文件系统写入失败具有跨事实崩溃回滚能力。UI事实仍按UC-8C7严格提交，全部完成后才继续API。
- **依据**：`RuntimeHistoryOps.append_model_tool_results`、`agent_loop._persist_completed_tool_batch/checkpoint_ready_tool_results`、`SessionEventLog._append_many_unlocked`；`tests/runtime_v2/test_completed_tool_batch.py`、`tests/test_runtime_noop_persistence.py`、工具steer/续跑及完整真实工具loopback基准。批量追加也可发布UC-8A12回执；超过256KiB的批次不为该缓存额外拼接完整编码缓冲。
- **严格UI交付补充**：同一已完成批次通过一次跨loop确认和一次工作线程调用提交execution/UI；每个工具的两类事实仍独立、顺序追加，整个批次成功后才逐项公开。事务内复用追加句柄见UC-8A13。桥内批次封套用私有对象键识别，不进入公开SSE；普通事件不能伪造该封套。取消通知传入工作线程，每项前及journal/UI之间检查；失败不公开成功结果，不发送后续API。非strict、子代理转发、不可持久化事件和不支持批次方法的管理器走原分离路径。工具计数按批次实际项数更新；纯文本工具结果不再逐字符遍历寻找附件块。

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

## 5. 版本记录

- 2026-10-18 v7：严格UI按已完成批次使用一次线程交付，保留逐项execution/UI事实及成功后公开屏障、取消、回退和私有封套；纯文本跳过附件块遍历。
- 2026-10-18 v6：新增UC-8C8，只对已完成只读结果合并model_tool追加；未变化摘要的无写入persist跳过多余所有权读取，实际事实写入的检查与关键路径保留。
- 2026-10-17 v5：新增UC-8C7，执行journal与对应UI事实在一个短事务中顺序提交，成功后防止重复镜像，保留失败与耐久事实边界。
- 2026-09-20 v4：补入本地压缩原文的不可变 JSONL 归档、稳定引用及其与 Runtime V2 权威事件流的边界。
- 2026-09-20 v3：补入未变化 context summary 的进程内提交去重及冷未命中权威读取边界。
- 2026-09-14 v2：澄清 `source_seq` 为可选关联；版本线更新至 `d022831`。
- 2026-09-13 v1：拆分首版（承接 UC-805/806）。
