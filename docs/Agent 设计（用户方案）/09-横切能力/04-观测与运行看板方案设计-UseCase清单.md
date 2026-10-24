# 观测与运行看板 · 功能方案设计（UseCase 清单）

- 版本：2026-10-23 v30（grep 准入和放弃队列口径）
- 用途：逐条审查（四字段格式）。
- 适用实现：`app/runtime_observability.py`（record_usage L269 等）、`app/execution_metrics.py`（运行看板/心跳）、`agent_loop.py`（埋点调用）。
- 上级：`00-横切能力整体设计.md`

---

## 1. 功能定位

"运行时仪表盘"：用量、耗时、心跳、指标——供排查与成本意识，不与用户抢戏。

## 2. UseCase

### UC-9D1 用量记录
- **触发**：每次模型响应（含流式）。
- **预期现象**：token 用量入账（按会话/模型可查）；解析失败不报错（记日志）。
- **依据**：`record_usage`、`extract_usage_dict`。

### UC-9D2 运行看板与心跳
- **触发**：run 进行中。
- **预期现象**：看板维度（运行时长/步骤/状态）实时更新；心跳证明"活着"；运行结束以实际 status 与 reason 定格。全部 run 复用一个进程级心跳线程。
- **规则与边界**：观测线程/定时器创建失败时只降级观测，不得终止业务 run；结束收尾必须撤销该 run 的心跳注册。
- **依据**：`execution_metrics._heartbeat_pump/_ensure_heartbeat_thread/start_run/finish_run`。

### UC-9D3 阶段计时
- **触发**：每轮 pre-API 与流式阶段。
- **预期现象**：TTFT、服务端等待、请求体交接、模型输出、工具执行、轮间准备和总时长分别入日志/指标；`transport_breakdown/transport_final`、`stream_transport_select`、`stream_gap_probe`、token cache 站点标签、workflow/Todo lookup 和 tool registry revision 能直接定位 provider、工具或本地热路径。
- **规则与边界**：`pre_api.total_ms` 只累计互斥父区间；`build_messages / static_segments_build / before_round_callback / before_round_lookup / tool_registry_revision` 等诊断子区间保留明细但不得重复加总。上传/服务端分量使用语义可靠的 `server_wait_ms`，不能把过早触发的 `send_request_body.complete` 当成真实上传完成时间。
- **本批补充**：`context_tokens_emit / context_policy_decision / context_policy_run` 属于 `post_config_setup` 内层；`model_config_client / model_config_language / model_config_request_context / model_config_compaction` 属于 `resolve_model_config` 内层；`model_config_thread_cpu` 是 CPU 诊断值。它们都从互斥墙钟累计中排除，保留子段明细。
- **依据**：`_pre_api_timing_mark / _pre_api_timing_total / _llm_stream_timing_log / execution_metrics.record_phase`（../02/08）。

### UC-9D4 实时度量推送
- **触发**：运行中需要向界面推指标（如思考计时）。
- **预期现象**：轻量事件推送（不写重日志）；对聊天零干扰。
- **依据**：`_emit_live_metrics`。

### UC-9D5 数据可导出与保留
- **触发**：查看/导出指标。
- **预期现象**：指标持久化（刷盘策略明确）；导出格式可用；不会无限膨胀（轮转/清理策略存在）。
- **依据**：`execution_metrics` 刷盘段、runtime_observability 存储。

### UC-9D6 附件与独立识图指标

- **触发**：图片准入、远程下载、请求图转换、预算省略、模型识图或生命周期操作发生。
- **预期现象**：按阶段累计次数和总耗时；管理员可通过 `GET /api/vision/metrics` 读取 `counts` 与 `totalSeconds`，用于发现下载失败、缓存行为、能力省略和处理时延异常。
- **规则与边界**：指标不包含图片字节、base64、完整 URL、prompt、回答、设备凭证或附件路径。当前指标是进程内有界计数器，进程重启即清零，也不提供按用户或会话的长期账单语义。
- **依据**：`attachments.metrics.count/duration/measure/snapshot`、`vision_api.metrics`。

### UC-9D7 严格轮间性能口径

- **触发**：评估“一个工具完成后多久真正发出下一次模型请求”。
- **预期现象**：按 `(session_id, run_id, react_iter)` 配对上一工具轮的末次结果日志与下一次请求开始，优先统计两端真实时间戳差值；输出配对数、中位、P90、最大值和目标达标率。起点是工具 invoke 返回还是结果后处理完成，终点是 API 调用开始还是传输请求开始，必须随结果明示。
- **规则与边界**：阶段合成仅用于解释直接差值：本批报告使用 `tool_to_next_api + round_gap + next pre_api + pre_api_tail`；不同版本的 `tool_result_post`、`request_start` 必须先核对起止位置，不能在已经包含它们的直接差值上再加一次。缺失字段视为未知，不填 0；按逐轮求和后统计，不能相加各阶段中位数。首次请求无前一工具轮，不进入轮间样本；LLM 生成、工具 invoke、消费尾部另列，重叠区间不得重复归因。
- **依据**：新增 `local_request_timing` 按同一单调时钟关联工具核心返回（workspace 审查前）、结果提交、准备开始、worker 排队/进入、HTTP send 与 httpcore headers/body.started。流式候选及 hedge 线程传递同一请求上下文，重试记录最早端点；无 HTTP 观测不伪造发送。`local_ready` 另记录工具与前一模型 worker 都完成后的起点，原始工具差值仍保留。详见 [02/08 · UC-2H6](../02-ReAct运行时/08-标题生成与运行观测方案设计-UseCase清单.md)。09-29/30 旧直接与合成值对照见 [05 · §4.2](05-性能优化基线与已完成项方案设计-UseCase清单.md)。

### UC-9D8 stale 判定与看门狗隔离

- **触发**：`runtime_observability` 中 `status=running` 的行超过心跳阈值。
- **预期现象**：先用 `(session_id, run_id)` 核对本地任务；仍活跃则保留，确认失联才标 stale，并只取消该 run。
- **规则与边界**：历史 stale/finished 行不进入下一轮扫描；心跳过期不是会话级取消依据，也不是运行总时长上限。观测历史可以保留用于诊断，但“是否活跃”只由当前 running 行与本地 exact run 事实共同决定。
- **依据**：`runtime_observability.scan_stale_runs/reconcile_orphaned_runs`、`main.runtime_watchdog`、`session_lifecycle.cancel_run_tasks_by_id`。

#### UC-9D8 补充：后台扫描与运行中心跳的锁边界

- 周期全目录枚举、观测JSON读取、live_checker和外部所有权回调在心跳全局锁外执行；扫描不先强制flush所有会话。锁内只捕获独立数据副本、检查会话版本/配置epoch并发布判定。
- 未刷盘的本进程数据优先。读盘期间有心跳/用量/终态更新，或检查期间版本已变化时，跳过该旧候选；扫描开始时存在待刷心跳，即使读取旧文件后timer已完成，也不能用旧文件覆盖它。stale/orphan真正确认后的强制持久化契约保留；不把此改动描述成所有观测写盘均已移出锁。
- `observability_scan_timing`记录扫描总时间、枚举时间和候选数；`tool_metrics_timing`拆分工具指标及观测心跳的等待。对被其他并发更新淘汰的候选，下次扫描重查，不依据旧扫描去中断新状态。
- 10-18补充：周期巡检与启动孤儿对账只枚举会话根的一级会话容器，以及递归的`subagents/<id>`容器；不进入任务文件/checkout/node_modules树，不跟随符号链接或Windows reparse容器。枚举仍在全局锁外；全扫描周期和活跃会话快速扫描不变。真实工作区定向枚举与旧rglob均发现276个观测文件，没有遗漏；当次比较约63/233ms，历史真实run中旧枚举最高14767ms，不能把这些不同环境的数字当作严格A/B倍率。
- 扫描中的目录、读盘和所有权检查被阻塞时，心跳仍可继续；并发测试及受控800ms阻塞A/B见[8533复核](../../performance/agent-session-8533-2026-10-17.md)。该机制已验证，不等于历史10秒空档已有完整因果归属。

#### UC-9D8 补充：观测刷盘失败保留与去抖重试

- 触发：后台Timer原子替换被Windows读句柄暂时拒绝，或Timer启动及同步降级写失败。最新内存状态保持为待刷债务，扫描将其视为本进程新状态，不能以旧盘数据覆盖。
- Timer回调仅消费自身仍为当前timer的记录；取消的旧回调或旧配置不得消费新回调。WinError5/32/33及EINTR/EAGAIN/EBUSY按已有去抖周期重试，永久I/O错误保留债务且不循环重试。显式flush/终态强制刷盘仍报错，全局flush覆盖未完成timer及失败债务。
- 本次仅修复失败恢复；`runtime_observability._write`仍在原全局锁内，不冒充下述执行指标的锁外写盘方案。重试不在锁内sleep，不吞掉显式边界错误，不保证进程崩溃后保留尚未刷盘的内存。
- 依据：`runtime_observability._flush_locked / _flush_timer_fired / _arm_flush_timer_locked / _scan_states`，新增4项失败、旧回调及扫描竞态测试；最终相关组合219 passed、1系统符号链接跳过。真实重启后采集未复现刷盘异常，不等价于生产注入失败已验证。详见[10-21报告§8.4](../../performance/agent-subagent-interround-2026-10-21.md#84-后台刷盘错误与失败证据保留)。

### UC-9D9 指标序列化和写盘移出全局锁

- **触发**：后台定时 flush、显式 flush 或 `finish_run` 刷新指标。
- **预期现象**：先取得按会话的 I/O 锁，再在全局 `_lock` 内捕获稳定的请求根对象、复制运行头和外层列表并处理待刷状态；释放全局锁后执行 JSON 序列化和原子写入。请求已发布时，下一次更新只复制被修改的单条请求；未修改的历史请求不重复深复制。写入期间的新修改安排下一次合并刷新；会话 I/O 锁避免旧的慢刷新覆盖新的数据。
- **规则与边界**：初始化启动一个进程共享刷盘线程；业务更新只登记会话 deadline 并唤醒，不在全局锁内反复创建/启动 Timer。线程启动失败保留待刷标记，`finish_run`/显式 flush 在锁外补刷；全局 flush 同时等待已被后台领取的写入。请求修改统一经过 `_request`，调用方传入的嵌套字段先复制以防外部修改共享对象；公开 snapshot 仍返回独立副本，稳定根只用于内部只读序列化，不建立常驻的整份请求副本缓存。运行头的扩展字段及被修改单条请求仍需复制，其成本不宣称为零。该调整针对执行指标，不改变 Runtime V2 事实提交和 `runtime_observability` 的原降级逻辑。
- **依据**：`execution_metrics.py::_capture_snapshot / _request / _flush_pump / _ensure_flush_worker / _flush_session / _save / flush / finish_run`、`tests/test_execution_metrics.py`、`tests/test_execution_metrics_snapshot_roots.py`。`execution_metrics_timing` 分别记录 `io_wait_ms / lock_wait_ms / lock_held_ms / io_write_ms`；兼容旧字段名 `timer_flush` 表示后台合并刷新，`sync_flush` 表示显式刷新。真实会话的证据与局部复制收益见[bc12复核](../../performance/agent-session-bc12-2026-10-17.md)，不把局部收益当作整条 Agent 已达标。

### UC-9D10 消费结束与实际投递分开计时

- **触发**：工作线程完成、Agent 消费完成、主循环投递队列排空或最终答复结束。
- **预期现象**：工作线程在完成时保存单调时钟时间，`llm_local_consumer` 记录 `worker_done_to_consumed_ms`、usage 记录、Steer 探测次数/累计/最大耗时、桥接发送次数/累计/最大耗时。`llm_stream_delivery / stream_bridge_delivery_timing` 另记录主循环 `main_emit_total_ms / main_emit_max_ms / main_emit_cpu_ms / queue_age_max_ms / main_emit_calls / pending_events`；单次投递/排队 ≥100 ms 有 `stream_event_delivery_detail`。
- **规则与边界**：启用异步增量后，旧 `bridge_emit_*` 衡量生产者发送调用时间，须同时读取 `bridge_queued_deltas / bridge_pending_events`；它不等于实际 UI 投递时间。主循环线程 CPU 跨 await 取差值时可能含该线程其他任务的 CPU，不作为单个 emit 的独占 CPU。Steer/桥接累计跨整个消费过程，部分早于 worker 结束；早启动工具也可能与消费尾部重叠。
- **依据**：`agent_loop.py` 的 worker 完成取时与消费记录、`StreamEventBridge.snapshot / _drain`；[05/03 · UC-5C8](../05-WebUI对话界面/03-SSE管道与断线续看方案设计-UseCase清单.md)。最终 `final_pipeline_timing` 分开记录 loop_finished、校验/校验事件、final 发送、yield、finish；完整收尾仍须以 worker/consumer/耐久终态或指标终态的实际边界复核，注明所用终点。

### UC-9D11 墙钟、CPU、锁和调度的证据边界

- **触发**：pre-API、轮间或收尾出现无法解释的本地尖峰。
- **预期现象**：配置组合段细分 client、语言、请求上下文、压缩标记和线程 CPU；`context_tokens_emit_detail` 细分 fence/emit/CPU；registry 分来源及 host 排序/动态回调；pending 读取/claim、结果后处理/轮次边界指标、索引/事务锁分别记录。详见 [03/01 · UC-3A5](../03-工具系统/01-注册表与描述符方案设计-UseCase清单.md)、[08/01 · UC-8A7](../08-会话存储RuntimeV2/01-事件日志与错误语义方案设计-UseCase清单.md)。
- **规则与边界**：事件循环停顿改为测量入队回调实际运行的 `loop_callback_delay_ms`；`perf_counter` 与 `loop.time` 都会在阻塞期间推进，两者差值不能检测停顿。回调延迟可能包含同步 pre-API 工作，不能再作为独立空等加总。GC 计数、同窗口指标锁占用、墙钟/CPU 差异只是线索，不直接认定原因；需要相同时间窗口的调用栈佐证。
- **依据**：`_PRE_API_NESTED_TIMINGS`、`_loop_callback_probe`、相关 detail 日志；09-30 独立 py-spy 采样抓到 `GoalManager.get → read_consistent → deepcopy` 完整链，修复见 [02/09 · UC-2I12](../02-ReAct运行时/09-运行生命周期与Goal续跑防风暴方案设计-UseCase清单.md)。非阻塞栈可能不完整，持 GIL 样本占比不是墙钟占比。

### UC-9D12 改动审查耗时分解

- **触发**：`change-review` 的工具前、工具后、批次补扫或重启恢复执行。
- **预期现象**：`change_review_timing` 记录 `session/stage/elapsed_ms` 和下表字段；不用上下文长度或服务器响应解释这一段本地等待。
- **规则与边界**：工具工作本身不计入 before/after，审查发生在本地。已有义务在外部工具前补扫时单独记录 batch_flush，随后 before 重新起钟。批次收益以全部 before + after + batch_flush 比较，不能仅看变快的单个 after，把等待转移到扫尾。首次 baseline 和热路径分别统计；后台负载、冷缓存、文件数和并发条件需注明。
- **依据**：`plugins/change-review/runtime.py::log_timing`、`store.py::_measure`；[06/08 UC-116~119、506](../06-能力扩展加载/08-内置插件-改动审查方案设计-UseCase清单.md)，[05 §4.6](05-性能优化基线与已完成项方案设计-UseCase清单.md)。

| 字段 | 口径 |
|---|---|
| `stage` | `before`、`after`、`batch_flush`；恢复也用 batch_flush |
| `inventory_ms` | Git 文件清单子进程及路径处理 |
| `signature_ms` | sweep 的完整签名检查及变化文件读取后二次验证 |
| `read_hash_ms` | 声明路径、失效候选和清单消失路径的内容读取/状态计算 |
| `blob_io_ms` | before/after 内容块及基线字节读取、校验、内容块写入；不含索引 |
| `diff_ms` | 差分构建 |
| `index_read_ms/index_write_ms` | 本阶段 store 索引读/原子写；补扫确认的索引 I/O 也累计 |
| `lock_wait_ms` | 本阶段采集/补扫取得 store RLock 的等待 |
| `baseline_ms` | 首次工作区基线或已有基线查询；父区间含 inventory 与并行读取，禁止与其子区间相加 |
| `maintenance_ms` | before 内旧轮基线清理；包含其内部索引/GC 工作，不再重复列入该阶段其他子项 |
| `ui_commit_ms` | 补充 UI 事件的耐久提交；批次 elapsed 同时包含待交付确认 |
| `files/cache_hits/changed_count` | 本阶段实际枚举文件数 / 完整签名命中 / 失效候选（不等于有净差异文件数）；未扫阶段均 0 |
| `inventory_calls/sweep_count/sweep_deferred` | 本阶段枚举尝试数 / workspace 扫尾尝试数 / 是否保存延后义务 |
| `changes/scan_workers/coverage/file_limit` | 输出记录数 / 实际签名线程数 / 可用观测面 / 生效上限（有该行为时记录） |

各子项用于归因，不保证正好等于 elapsed；路径解析、Python 合并等未单独取时。阶段中位不能相加代替逐批总耗时。`baseline_ms` 的并行文件处理仅记录父墙钟，不能把线程耗时相加；`changed_count` 与 `changes` 不可混用。

### UC-9D13 结果交付与终态收尾的单调时钟子段

- **触发**：主循环事件交付/排队≥100ms，或运行进入公共终态清理。
- **预期现象**：`local_operation_timing`以session/run/react_iter关联同一perf_counter时钟。交付记录队列入队/开始、journal排队/worker进入/事务取得、journal状态与record、事实append、UI append/mirror/projection、snapshot发布和event publish；终态记录power guard关闭、工作流记账边界、待续跑清理、终态事实提交、未读状态、事件发布、指标finish和流关闭。
- **规则与边界**：仅写内部日志，收集元数据和时间，不写消息、工具参数、结果或公开SSE。单个操作最多64个span，超出记录丢弃数；快交付不逐事件写日志，终态每run写一次。ContextVar随to_thread传递、退出复原；失效日志处理不改变原异常/取消和交付顺序。父子span嵌套不能直接相加，跨await的线程CPU差值不是独占CPU。该日志使用agent_harness logger，避免会话日志处理器切换后丢失其他模块的细分计时。
- **依据**：`agent_local_timing.py`、`StreamEventBridge`、`persist_execution_event`、SessionManager与RuntimeV2相关装饰器、`_finalize_agent_run_lifecycle`；`tests/test_local_operation_timing.py`及流式/终态回归。首次本地定位已确认只读open成本与约250ms监测器关闭等待，实测和修复边界见[性能报告§9](../../performance/agent-interround-2026-10-17.md#9-结果交付路径的继续定位与修改)。

#### UC-9D13 补充：Hook、工具指标与目录构建漏计

- 慢Hook使用同一session/run/react_iter关联，记录plugin资源、runtime hook定义、manager和执行；从位置参数state提取身份，日志不含payload。journal新增`journal_source_boundary`，工具指标区分执行指标本体与观测心跳。
- pre_api的`tool_registry_total`为嵌套包络，`tool_registry_unattributed`为旧定义回调未覆盖的互斥部分；总计只加后者，避免将包络与子段重复累计。真实8533第2轮准备4.4秒、旧pre_api374ms的差异必须保留为漏计，补探针后再归因。

#### UC-9D13 补充：pre_api之前的轮入口与后台任务状态

- `round_entry`覆盖原有顺序：所有权检查、review补扫、子代理通知、后台执行通知；暂停/取消仍在原边界生效。它位于`preparation_started`之前，不再把这段工作误记成pre_api中的0ms。react_iter沿用入口时的当前轮，端点与相邻下一请求按单调时钟关联。
- 通知细分`job_notice_poll`、`job_notice_model_commit`和`job_notice_ack`，模型通知提交失败不得ack。后台`extension_write`≥50ms记录独立操作及`extension_snapshot`、事实追加等子段；后台服务只保有session身份时，不伪造run ID，按session与同一时钟关联。
- 不记录通知文本/任务payload，不改变服务跨线程时清空授权ContextVar的规则；只将独立计时ContextVar随实际to_thread写入传递。包络、CPU和文件锁获取不能互换称呼。
- **依据**：`_prepare_react_iteration`、`execution_services.integration.consume_notices`、`ExecutionService.persist`；`tests/test_round_entry_timing.py`覆盖入口顺序、取消/暂停与失败不确认。88def真实54轮间仍49次超标，后续扩展补修尚待生产加载，见[复核报告](../../performance/agent-session-8533-run-88def-2026-10-18.md)。

#### UC-9D13 补充：Hook外层包络

- `hook_session_metadata`覆盖原会话元数据读取；`hook_workspace_prepare`覆盖工作区路径和安全根准备；`hook_workspace_before/after`覆盖原to_thread审计采集。原顺序、条件、失败、取消和授权语义保持。
- c004实跑PostToolUse472.527ms中，已有插件/定义/manager/执行span仅约74ms，约398ms处于外层；新增细分用于验证该缺口。不能把未覆盖部分叫作脚本执行或纯锁等待，也不将PreToolUse重算为core返回后的轮间。
- 仅在既有内部慢操作日志中收集元数据，不增加公开SSE、消息内容或事实字段；父子span不重复加总。详见[c004复核](../../performance/agent-session-8533-run-c004-2026-10-18.md)。

#### UC-9D13 补充：请求worker安排、派发和提交

- 原`worker_scheduled→worker_entered / worker_queue_ms`保持为可同比包络；新增`worker_dispatch_entered`和`worker_submitted`，输出安排→async派发、派发→提交、提交→worker的互斥子段。
- 流式、纯非流式及回退共用`new_request_trace`工厂，只配对紧邻上一工具轮；非流实际HTTP发送同样进入trace。回退保留最早发送端点，成功非流请求记录completed和完整duration，不把完整响应时长冒充首token。
- d68真实安排→worker313.067ms尚不能细分为默认executor排队与事件循环延迟；独立320ms占位复现支持隔离共享池的机制，不冒充生产根因完整证明。新探针随请求trace跨线程，保留最早端点，元数据无payload，不新增公开SSE。
- **依据**：`agent_request_executor`、`RequestPreparationTrace.snapshot`；隔离/并行/取消与trace测试及[d68报告](../../performance/agent-session-8533-run-d68-2026-10-18.md)。

#### UC-9D13 补充：模型提交、事务和发布的内部等待

- `model_commit / model_commit_batch`覆盖同步事实提交并按state关联session/run/iter；同步和异步装饰器都保留原返回值、异常与外层ContextVar，不携带消息内容。
- 事务叶子区分锁查找、线程锁、目录/身份准备、锁文件open及OS锁；快照发布区分路径、取消守卫、文件签名、内存发布、due检查、安排及inline wait。锁查找、目录、路径仍是复合包络，不能全部称作纯锁等待。
- 插件manager区分lock、默认路径/迁移检查、canonical解析和构造；registry_revision只有session身份时按session和时间关联，不伪造run ID。检查、读取及错误语义保持原样。
- 新叶子仅≥5ms保留，原span计量保持，上限仍64条且保留dropped；未出现不等价于耗时0或未执行。父包络与嵌套子段不能重复相加。e046的834ms发布和407ms模型提交需要这些子段继续核验，未将其预设为fsync或锁竞争。
- 10-21 UC-6A8将manager路径检查/构造移到发布锁外、LRU只锁内存；同名`plugin_manager_lock`现在计发布锁获取，冷构造/配置重试可能获取多次，不能把新旧子段数量当同一锁范围。路径检查仍在调用线程同步执行，受控第二调用变快不证明首次检查免除。细节见06/01及[本批报告§10](../../performance/agent-subagent-interround-2026-10-21.md#10-插件manager发布锁隔离补修)。
- **依据**：`agent_local_timing.local_operation/local_step`、`SessionEventLog.session_transaction`、`SnapshotStore.write_checkpointed`、`plugins.manager.get_plugin_manager`；专项注入慢签名/OS锁并验证耐久事实，完整证据见[e046报告](../../performance/agent-session-8533-run-e046-2026-10-18.md)。

#### UC-9D13 补充：外层重试保持首次实际发送

- 0a79同一iter56的外层重试重建trace，metrics原记5262.563ms；原日志首次发送证明严格工具轮间为531.299ms，仍超标。原记录和还原结果并存，不删样本，不把重试等待记成本地首次发送前处理。
- ReAct调用栈仅保留一个trace引用；session/run/iter/上一工具返回端点相同才复用。换轮、换run或工具端点变化即新建；最早准备/发送端点保留，无发送端点仍缺失。引用不进入State或持久化，不增加发送路径日志写盘，重试策略和事实提交语义保持。
- 多会话按已核验进程/版本分组，运行中样本标明采集截面。只有session身份的span按session+时间关联，不伪造run ID；失败工具没有core端点时不以0ms补齐。
- **依据**：`agent_request_timing.new_request_trace(previous_trace=...)`、`agent_loop._react_node_once`、`tests/test_agent_request_timing.py`；本次194配对17超标，首次发送P50 178.057ms/P95 591.584ms，原计时与还原证据见[2026-10-19报告](../../performance/agent-current-sessions-2026-10-19.md)。

#### UC-9D13 补充：task子代理的真实运行身份

- `task`入口将已预约的`_subagent_run_id`同时设置为共同循环使用的`_runtime_v2_run_id`，指标start/finish按该真实ID区分新建/续跑；不生成另一个观测ID，也不以父run ID代替。旧空ID记录保留，不能据它统计独立历史运行的达标率。
- 前后台实际执行Task各自管理指标注册/清理，结束在输出/pending协议之后；注册部分失败及取消也要清理心跳。旧同步心跳和普通UI写改为线程中执行后仍等待，并在取消时收敛已开始的写，避免晚到的running覆盖中断终态。
- `event_delivery`记录子agent本地交付及child_heartbeat子段，UI批次仍分别公开原事件；`subagent_finalize_before_metrics_ms`是ReAct退出到指标结束开始前的收尾包络，另有`subagent_metrics_finish`。这些不是主入口的完整run_finalize；startup失败、没有发送等情况不造0ms端点。
- 依据：02/10 UC-2J13、`agent_subagent._finish_subagent_metrics`、[10-21报告](../../performance/agent-subagent-interround-2026-10-21.md)。前台/后台实际loopback请求已验证非空ID、完整工具事实和终态；功能回归不代替轻/重负载性能验收。

### UC-9D14 grep 逐调用阶段与队列关联

队列补修新增 `admission_ms`（开始至获准进入有界池）和 `queue_outcome`（waiting_capacity / started / finished / abandoned_before_start / direct）。未进入worker的搜索 `worker_queue_ms=null`，不能填零；其等待包含在 `elapsed_ms`。`admission_ms` 是包含于worker队列包络的锚点，不能相加。放弃后的占位项排空不再进入搜索或修改已交付的该次计时。停止原因首次确定后保留，超时唤醒清理线程不能改记取消；见[队列补修](../../performance/grep-queue-and-tool-preparation-2026-10-23.md)。

- **触发**：内置 grep 调用完成、失败、超时或取消。
- **预期现象**：`grep_timing` 包含 session/run/iteration/tool_call_id、worker_queue_ms、backend、fallback_reason、first_hit_ms、结果和候选数量；每个自有进程单列 spawn、首个输出、read、cleanup、stderr 总字节、cap 和停止原因。主代理与子代理使用同一实现，ContextVar 隔离并发身份；直接函数调用缺少身份时留空，不伪造关联。
- **规则与边界**：read_ms 从启动计时，包含前面的 spawn 与首输出等待；first_hit_ms 是相对调用提交的锚点，不能再当独立区间累加。原宽口径工具计时和 invoke 不变；线程排队之外的授权、pending 交付及结果提交须按原计时另核对，不能用 grep 内层分位数相减推算。日志不含查询文本、路径、正文或 stderr 诊断内容，计时日志失败不改变搜索结果。默认预算未改成 500ms；小夹具首输出测试和热缓存回放不能作为全工作区冷扫描或完整轮间验收。
- **依据**：`grep_runtime.SearchRun / run_process / invoke`、`_GrepOutput`、`agent_loop._invoke_plain_tool`；[报告](../../performance/grep-optimization-2026-10-23.md)。

#### UC-9D14 历史分析兼容口径

回读历史时须同时识别 `payload.duration_ms`、`tool_status.duration_ms` 和旧 `status.duration_ms`，并核对 producer 的计时起止。旧导入记录可在 `tool_started` 下保存完整结果与最终时长，不能只按事件名筛终态；无时长草稿也不能填0或视为长执行。按 session/run/call_id 合并重复事件和备份，递归覆盖子代理；日志起始日期仅表示日志保留边界。宽口径以请求开始日、执行事实以完成日分组，分别统计；仅一对一调用或明确ID可作差，不用最近时间强行配对。现存251个长执行段逐条原事件校验及CSV见[历史复核](../../performance/grep-history-review-2026-10-23.md)。这描述分析方法，不新增生产计时字段。

## 3. 历史生产基线（2026-09-19 会话 `8278fdd4`）

| 指标 | 结果 |
|---|---:|
| ReAct 轮次 / 工具调用 | 37 / 76 |
| 上下文范围 | 12.4k → 124.2k tokens |
| 严格轮间中位 / p90 / 最大 | **37 / 129 / 887 ms** |
| 严格轮间 `≤100 ms` | **32/36（88.9%）** |
| `pre_api` 中位 | **28 ms** |
| `token_estimate` 中位 | **14 ms** |
| 总耗时归因 | LLM 71.3% / 工具 28.1% / 本地框架约 1.2% |

该样本验证了 150k 以下热路径，但**不能代替 300k+ 上下文回归**。工具长尾中，仓库根 grep 曾
30.2 s 超时、225 文件目录 ls 曾约 9 s；2026-09-20 改动后同参数开发机复测分别约 439 ms、49 ms，
仍需重启后的生产会话确认。

09-29/30 的本地延迟复测已另列于 [05 · §4.2](05-性能优化基线与已完成项方案设计-UseCase清单.md)。上述历史样本不得作为该批修改已达标的证据，也不用于把新观察到的本地空档归因到上下文长度或服务器响应。

## 4. 边界

- 界面上的"上下文占比"提示来自分词估算（../02/02），逻辑上属观测读数；
- 告警是观测的"阈值出口"（见 03）。
- 独立识图结果、错误码和图像状态的业务语义见 [02-识图与多模态投影](02-识图与多模态投影方案设计-UseCase清单.md)。

## 5. 依据映射

见上表。

### 完成事件合批内部计时（UC-9D13补充）

`execution_ui_batch`记录同步操作包络；内部`ui_batch_prepare / ui_batch_append / ui_batch_project / ui_batch_journal_refresh`区分私有预演、事实追加、投影发布和journal增量刷新。主/子代理共用该操作，按既有session/run及单调时钟关联。子段属于父包络，不重复累加；显式flush计数只能证明减少写调用，不能推断纯锁等待、os.fsync或磁盘物理耐久时长。正式基准默认关闭额外diagnostics；诊断span与验收数据分开。

### 发送前尾段和线程内叶子（UC-9D13补充）

- 先前ad iter8尾段1107ms未细分。请求指标保留`pre_api_tail_ms`，新增`pre_api_tail_events`七个互斥墙钟子段：timing_log、metrics_prepare、thinking_status_emit、strip_reasoning、runtime_policy、pressure_emit_and_metrics、request_scope_and_setup。流式、纯非流式及task子入口共用；不加入pre_api原分项总和，不新增公开SSE或请求body字段。
- 两个时间戳间含当前线程的其他任务/调度，状态投递包含await；整数取整会留下少量差额。尾段指标自身最后一次record_request不计入自身包络，严格tool→HTTP端点仍覆盖它；不通过自测自写的循环造“完全归因”。未发送/取消不补造HTTP端点。
- `journal_lock_key / journal_cache_key / journal_seq_cursor / journal_source_stat`分别包住原共享锁名解析、缓存键解析、seq游标与源stat，仅≥5ms保留，仍受原64条span上限影响。文件检查和异常语义不改；未记录不表示没有执行。
- `hook_runtime_definitions_worker`与原await包络嵌套，正常to_thread入口可区分执行线程工作与外部等待；仅靠差额不能区分executor队列与事件循环延迟。受控单线程占位验证传播、开始顺序及原返回值；完整519项门禁和实际前后台非流式请求验证尾段字段完整。详见[本批报告§11](../../performance/agent-subagent-interround-2026-10-21.md#11-完成事件预演及发送前尾段补修)。

### 真实运行配对的补充口径（UC-9D13补充）

- 严格工具core返回→下一轮首次HTTP send若遇到早启动工具，可能包括上一模型worker的剩余时间。保留严格值，并另外使用已有`local_ready=max(tool_returned, previous_model_worker_done)`端点；worker结束不等于全部本地流消费完成。14:42重启后的508配对有7个此类重叠，严格355次超标，ready口径仍352次；不能以删掉7个样本处理。
- Hook新增worker叶子的开始/结束可将外层await拆成开始前、worker函数及结束后恢复三个窗口。本次81个成对样本最大worker2.020ms，最大结束后恢复3077.557ms；差额可以定位返回/恢复窗口，但缺future-ready与loop线程标识时，不能证明具体是谁占用了loop，或把它全部称为executor队列。
- `request_conversion_completed→http_send_entered`只代表转换后的本地区间，包含provider/SDK构建和调度等未细分路径；本批最大8062.877ms，转换本身18.652ms。不得将该间隔命名成纯JSON编码，也不得用此次请求的服务器响应解释发送前等待。
- `change_review_timing`以墙钟时间+payload去重，而非文件名归属；全局logger多handler和跨会话文件不能使同一条数据计数两次。缺run/单调锚点的review文本只作旁证，不能直接累加到严格轮间。源版本须分别记录启动时刻、加载字段证据和磁盘mtime/哈希；未采到子run指标不能写成已验收。
- 本次生产数据、运行中范围、父子span/阈值限制、首请求和收尾独立口径见[报告§12](../../performance/agent-subagent-interround-2026-10-21.md#12-1442重启后的新增真实会话1742只读截面)。本段是分析口径与结果补充，没有追加生产计时代码。

### 等待式事实提交与发送线程细分（UC-9D13补充）

- 新`fact_commit_await`根操作关联session/run/iter，≥50ms保留。submitted→worker_entered→worker_finished→resumed及线程标识定位排队、同步工作及回到loop的等待；内存回执单独计时。cancel_requested记录首次取消请求；已选定的已完成事实即使还在排队，也先等待原写函数和成功内存回执再传播取消，写函数仍可按实时所有权拒绝。异常/不完整端点不补零。原model_commit/model_commit_batch是内层，不重复相加。
- Hook改为一次整组后台准备后，新增hook_prepare_await及四个同类端点。旧hook_runtime_definitions已是同一worker内的定义区间，不能继续与修改前“await to_thread往返”直接同比。`LocalOperationTrace.mark_threads`保留标记所在的线程身份；async包络的thread CPU仍不等于worker CPU。
- 同步目录加载本体增加`plugin_catalog_sync_load`，与外层`hook_load_plugins`嵌套；后者还含manager准备、缓存和扫描锁等待，不能把两者相加。23:22初版样本只有外层11.195秒，不能据此分别分配锁/扫描成本；目录SWR补修后的样本需另按加载时间分组，见报告§14。
- 第二次重启出现model_commit根8554.134ms、旧内层追加日志365ms，差额定位到前置检查范围，不能直接命名为8.189秒锁等待。新增`write_fence_local_lock / write_fence_session_path / write_fence_disk_read`及`steer_fence_register_io`；保留原≥5ms/有界规则，分清本session检查与其他session注册的锁放大。捕获期间发现再次重启时按run/请求时间重新分组，保留错误current_process标签的原文件并更正，不能把累积13配对归入新进程。见报告§15。
- 请求新增send_paths：request_worker以及primary/hedge分别记录线程调度/进入、流路由、流对象和迭代、facade候选准备、provider入口、raw请求准备、快速JSON分支、HTTP构造、send调用和实际transport委托等有序端点。一次逻辑请求最多16条路径，每条96点，超限显式计数；只记固定阶段名/单调时钟/线程ID，不记录请求body或凭据。
- 一条路径可经过多个provider，重复点保留顺序，不用不同物理尝试的最早起止拼成假分段；路径数不是物理请求计数。原逻辑trace首次HTTP send端点保留，未发送的失败没有伪造发送；stream路径、SDK和direct分支及普通非流式HTTP均有覆盖。snapshot按时间排序并复制点，读侧不能修改原记录。
- HTTP客户端接受`headers=None`，与httpx可选header语义一致；请求/响应和body不因计时改变。测试验证两个真实SDK/direct流分支、非流式HTTP、并发关联、上下文、失败边界和有界快照。见[报告§13](../../performance/agent-subagent-interround-2026-10-21.md#13-事实提交与hook准备的事件循环隔离补修)。

### ask_user卡片准备计时（UC-9D13补充）

`ask_user_card_prepare`关联session/run/iter，仅覆盖问题创建、waiter登记、状态重查和emit确认，日志在等答案前结束。`ask_question_create_await / ask_question_status_recheck / ask_question_card_emit`拆三个等待；线程内`interaction_snapshot_prepare / interaction_fact_append / interaction_projection / interaction_checkpoint / interaction_pending_counts`另列，原`fact_commit_await`记录线程往返。没有emit不标记`ask_question_card_emitted`，emit完成不等于客户端收到或绘制。日志仅记录标识和时间，不存问题、选项或答案；嵌套包络不相加。

实际样本通过35个不重复arguments片段复原完整JSON，以seq27429为参数完成边界，至卡片journal锚点约3545ms；这是服务端关联证据。不能把工具总时长中的用户回答等待算进出卡耗时。真实前缀对照仅衡量后端准备，生产SSE/绘制仍需另测，见[专项报告](../../performance/ask-user-card-latency-2026-10-23.md)。

## 6. 版本记录

- 2026-10-23 v30：grep新增准入锚点、队列结局和未进入worker的空值语义；明确包含关系、放弃后不可迟到更新及超时/取消原因保持。

- 2026-10-23 v29：补录旧status耗时、旧tool_started终态、子代理与备份去重；明确保留边界、缺失值、不同时间锚点和严格配对规则。

- 2026-10-23 v28：补充 grep 逐调用 ID、worker 排队和后端进程分段；明确嵌套时长与锚点不可相加、日志不存正文及冷扫描验收边界。

- 2026-10-23 v27：补齐ask_user创建、状态重查、emit确认及线程内投影计时，区分参数完整、服务端交付和屏幕绘制，排除用户回答等待。

- 2026-10-21 v26：增加写栅栏锁/路径/磁盘及注册分段，修正第二次自然重启的分组，不把旧内层计时之外的差额全部当锁等待。

- 2026-10-21 v25：增加同步目录加载本体计时，按自然重启和SWR补修前后分组，保留外层与锁/扫描未分解限制。

- 2026-10-21 v24：补齐事实提交与整组Hook的线程往返端点，新增有界send_paths及线程身份；保持首次发送/重试关联，明确旧定义计时口径变化及未发送样本规则。

- 2026-10-21 v23：以522个新增请求验证计时加载；补充早启动工具重叠、worker完成后恢复、转换后发送及重复review文本的解释规则，保留未定位等待和源码并发边界。

- 2026-10-21 v22：新增七段pre_api_tail_events，覆盖流式/非流式/子入口；补充Hook执行线程与journal键/游标/stat叶子计时，保留包络、阈值和未覆盖部分，519项回归通过。

- 2026-10-21 v21：说明manager发布锁隔离后的同名计时范围和可能多次获取，区分同步路径I/O与锁连带等待，完整持续负载失败保留于专项报告。

- 2026-10-21 v20：补录观测Timer失败债务、瞬态去抖重试与永久错误边界；重启后3个真实run、50配对27次超标，包络/锁/span及未覆盖尾段分别保留，目标未完成。

- 2026-10-21 v19：task子代理接入真实run指标及交付/收尾观测，保留旧空ID数据和主/子包络差异，补齐取消时线程写与指标注册的收敛。

- 2026-10-19 v18：修复外层同轮重试覆盖最早请求trace；保留原记录/首次发送还原及未配对失败，区分当前进程和更早会话，既有500ms目标未达成。

- 2026-10-18 v17：补齐同步模型事实提交、事务准备/锁、快照发布与插件manager内部等待；新叶子≥5ms、总条数仍64，支持同步异常和嵌套ContextVar恢复，保留真实e046的3/14失败。

- 2026-10-18 v16：请求worker包络细分事件循环派发、提交和executor排队；保留旧严格端点及包络，不将313ms未经验证直接归为纯线程池等待。

- 2026-10-18 v15：补齐Hook外层metadata、工作区准备及前后审计span；记录c004的约398ms未覆盖包络，不冒充已验证根因。

- 2026-10-18 v14：补齐pre_api开始前的round_entry及通知poll/模型提交/ack；后台扩展写入关联实际投影子段，保留失败和取消语义，不把获取包络等同纯锁等待。
- 2026-10-18 v13：严格结果批次使用event_delivery/tool_result_batch关联交付子段；私有封套不进入公开SSE，子段仍有64条上限，重复journal/UI子段不与包络相加。完整实测保留重载四工具5/32超标。
- 2026-10-18 v12：巡检按会话/子代理存储结构定向枚举；增加journal_owned_suffix和snapshot_suffix_read关联子段，保留新run仍43/70超标的真实验收结果。
- 2026-10-17 v11：根据8533重启后未达标样本，将后台扫描读盘/所有权检查移出心跳锁，补充版本/待刷/配置代的竞态保护；增加工具指标、慢Hook及registry漏计口径。
- 2026-10-17 v10：新增UC-9D13，交付慢事件与终态按同一单调时钟补齐内部子段，日志有界、不携带消息内容并保持异常和取消行为。
- 2026-10-17 v9：依据重启后 bc12 真实会话补全 UC-9D9：指标快照发布稳定请求根、修改单条请求时复制、调用方输入隔离及公开快照脱离共享状态；保留每会话写序和终态排空。
- 2026-10-17 v8：UC-9D7 接入真正工具返回至 HTTP headers/body.started 的关联计时；UC-9D9 改为初始化共享刷盘线程，避免业务锁内 Timer.start，并补齐全局 flush 等待后台已领取写入的边界。
- 2026-10-05 v7：增加 UC-9D12，规定 change-review 的阶段/子项/计数、基线嵌套与扫尾等待口径，关联批次优化和独立 A/B。
- 2026-10-05 v6：补齐本会话 09-29/30 已完成的指标锁外写盘、消费/实际投递拆分、配置/host/通知/索引/锁诊断；修正直接轮间口径和回调延迟探针解释，历史基线保留日期。
- 2026-09-20 v5：补齐 transport 选择/分解、流间隙、token 命中站点、workflow/Todo 和 registry revision 性能探针及其口径边界。
- 2026-09-20 v4：共享心跳线程与非致命降级写入验收口径；新增 UC-9D8，明确 stale 只扫描 running 行并按 exact run 取消。
- 2026-09-20 v3：补齐严格轮间配对口径、互斥计时规则和最新生产基线；记录 grep/ls 优化前后开发机复测。
- 2026-09-14 v2：加入附件阶段与独立识图的无载荷指标。
- 2026-09-13 v1：拆分首版（原 UC-912）。
