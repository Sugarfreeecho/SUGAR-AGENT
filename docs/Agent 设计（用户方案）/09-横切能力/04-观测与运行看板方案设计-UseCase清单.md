# 观测与运行看板 · 功能方案设计（UseCase 清单）

- 版本：2026-09-20 v5（覆盖至：当前工作区）
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
- **预期现象**：按相邻轮次配对统计 `tool_result_post + tool_to_next_api + round_gap + next pre_api + pre_api_tail + request_start`，输出中位、p90、最大值和 `≤100 ms` 达标率。
- **规则与边界**：不能把各阶段中位数相加代替逐轮配对；诊断父子区间不能重复累计；首次请求没有前一工具轮，不进入该口径。LLM 生成和工具自身执行时间另列，不混入轮间 SLO。
- **依据**：`execution_metrics.json` 的 request phase/event 字段、`_pre_api_timing_total`。

### UC-9D8 stale 判定与看门狗隔离

- **触发**：`runtime_observability` 中 `status=running` 的行超过心跳阈值。
- **预期现象**：先用 `(session_id, run_id)` 核对本地任务；仍活跃则保留，确认失联才标 stale，并只取消该 run。
- **规则与边界**：历史 stale/finished 行不进入下一轮扫描；心跳过期不是会话级取消依据，也不是运行总时长上限。观测历史可以保留用于诊断，但“是否活跃”只由当前 running 行与本地 exact run 事实共同决定。
- **依据**：`runtime_observability.scan_stale_runs/reconcile_orphaned_runs`、`main.runtime_watchdog`、`session_lifecycle.cancel_run_tasks_by_id`。

## 3. 当前生产基线（2026-09-19 会话 `8278fdd4`）

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

## 4. 边界

- 界面上的"上下文占比"提示来自分词估算（../02/02），逻辑上属观测读数；
- 告警是观测的"阈值出口"（见 03）。
- 独立识图结果、错误码和图像状态的业务语义见 [02-识图与多模态投影](02-识图与多模态投影方案设计-UseCase清单.md)。

## 5. 依据映射

见上表。

## 6. 版本记录

- 2026-09-20 v5：补齐 transport 选择/分解、流间隙、token 命中站点、workflow/Todo 和 registry revision 性能探针及其口径边界。
- 2026-09-20 v4：共享心跳线程与非致命降级写入验收口径；新增 UC-9D8，明确 stale 只扫描 running 行并按 exact run 取消。
- 2026-09-20 v3：补齐严格轮间配对口径、互斥计时规则和最新生产基线；记录 grep/ls 优化前后开发机复测。
- 2026-09-14 v2：加入附件阶段与独立识图的无载荷指标。
- 2026-09-13 v1：拆分首版（原 UC-912）。
