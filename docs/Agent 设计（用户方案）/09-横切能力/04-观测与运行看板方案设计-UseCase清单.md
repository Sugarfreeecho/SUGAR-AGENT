# 观测与运行看板 · 功能方案设计（UseCase 清单）

- 版本：2026-10-05 v7（覆盖至：当前工作区；增加改动审查分段与批次口径）
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
- **依据**：会话日志中的末次工具结果、请求开始及 `execution_metrics.json`；`_pre_api_timing_total`。09-29/30 直接与合成值对照见 [05 · §4.2](05-性能优化基线与已完成项方案设计-UseCase清单.md)。

### UC-9D8 stale 判定与看门狗隔离

- **触发**：`runtime_observability` 中 `status=running` 的行超过心跳阈值。
- **预期现象**：先用 `(session_id, run_id)` 核对本地任务；仍活跃则保留，确认失联才标 stale，并只取消该 run。
- **规则与边界**：历史 stale/finished 行不进入下一轮扫描；心跳过期不是会话级取消依据，也不是运行总时长上限。观测历史可以保留用于诊断，但“是否活跃”只由当前 running 行与本地 exact run 事实共同决定。
- **依据**：`runtime_observability.scan_stale_runs/reconcile_orphaned_runs`、`main.runtime_watchdog`、`session_lifecycle.cancel_run_tasks_by_id`。

### UC-9D9 指标序列化和写盘移出全局锁

- **触发**：后台定时 flush、显式 flush 或 `finish_run` 刷新指标。
- **预期现象**：先取得按会话的 I/O 锁，再在全局 `_lock` 内复制快照并处理待刷状态；释放全局锁后执行 JSON 序列化和原子写入。写入期间的新修改安排下一次合并刷新；会话 I/O 锁避免旧的慢刷新覆盖新的数据。
- **规则与边界**：`copy.deepcopy` 仍持全局锁，需单独观察其成本。定时器启动失败保留待刷标记，不在业务方持全局锁时同步写盘；`finish_run`/显式 flush 在锁外补刷。该调整针对执行指标，不改变 Runtime V2 事实提交和 `runtime_observability` 的原降级逻辑。
- **依据**：`execution_metrics.py::_flush_session / _save / flush / finish_run`、`tests/test_execution_metrics.py`。`execution_metrics_timing` 分别记录 `io_wait_ms / lock_wait_ms / lock_held_ms / io_write_ms`，区分 `timer_flush / sync_flush` 及 record 操作。

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

## 6. 版本记录

- 2026-10-05 v7：增加 UC-9D12，规定 change-review 的阶段/子项/计数、基线嵌套与扫尾等待口径，关联批次优化和独立 A/B。
- 2026-10-05 v6：补齐本会话 09-29/30 已完成的指标锁外写盘、消费/实际投递拆分、配置/host/通知/索引/锁诊断；修正直接轮间口径和回调延迟探针解释，历史基线保留日期。
- 2026-09-20 v5：补齐 transport 选择/分解、流间隙、token 命中站点、workflow/Todo 和 registry revision 性能探针及其口径边界。
- 2026-09-20 v4：共享心跳线程与非致命降级写入验收口径；新增 UC-9D8，明确 stale 只扫描 running 行并按 exact run 取消。
- 2026-09-20 v3：补齐严格轮间配对口径、互斥计时规则和最新生产基线；记录 grep/ls 优化前后开发机复测。
- 2026-09-14 v2：加入附件阶段与独立识图的无载荷指标。
- 2026-09-13 v1：拆分首版（原 UC-912）。
