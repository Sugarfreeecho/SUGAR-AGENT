# 标题生成与运行观测 · 功能方案设计（UseCase 清单）

- 版本：2026-10-27 v6（final投递与等待式收尾隔离）
- 用途：逐条审查（四字段格式）。
- 适用实现：`app/agent_loop.py`（标题 ≈L8694–8918、计时 L1917–2110）、`app/runtime_observability.py`、`app/execution_metrics.py`。
- 上级：`00-ReAct运行时整体设计.md`

---

## 1. 功能定位

会话的"表面功夫"与"里子数据"：标题自动生成（后台、防脏）、运行埋点（快而不扰）。

## 2. UseCase

### UC-2H1 会话标题自动生成
- **触发**：新会话首条消息后。
- **预期现象**：列表里的标题在短时间后自动出现（几个字概括）；生成失败有兜底标题（截取首条消息）；不阻塞对话。
- **规则与边界**：脏内容防护——本地路径、思考标签样式的候选标题会被拒/清洗；会话被删则不生成；生成 worker 有队列。
- **依据**：`_session_title_worker / _generate_session_title_with_diagnostics / _fallback_session_title / _looks_like_local_path_title`。

### UC-2H2 pre-API 计时埋点
- **触发**：每轮请求前。
- **预期现象**：各准备阶段（历史装载、提示构建、压缩等待等）耗时被记录；对用户零打扰。
- **依据**：`_pre_api_timing_mark / _pre_api_timing_log / _pipeline_step_timing_log`。

### UC-2H3 流式与首包计时
- **触发**：模型流式响应。
- **预期现象**：首包/总时长记录（供看板与排查）；异常流有对应日志。
- **依据**：`_llm_stream_timing_log`。

### UC-2H4 实时度量与心跳
- **触发**：运行中。
- **预期现象**：运行看板的心跳/指标实时更新；长任务无外界反馈时仍可看到"活着"。全部 run 共用一个进程级心跳线程，不再按 run 创建线程。
- **规则与边界**：心跳、刷盘线程或定时器创建失败时只降级诊断，不得让业务 run 启动失败。执行指标使用初始化时启动的共享刷盘 worker，业务更新只登记合并截止时间并唤醒 worker，不在持有业务指标锁时启动 Timer；worker 不可用会保留待刷状态，由终态/显式 flush 在全局锁外补刷。`runtime_observability` 的降级路径另按原契约执行。看门狗还需用 exact run 本地活性复核，不能只凭过期时间取消。
- **依据**：`_emit_live_metrics`、`execution_metrics._heartbeat_pump/_ensure_heartbeat_thread`、`runtime_observability._schedule_write`。

### UC-2H5 指标刷盘和本地热点诊断

- **触发**：后台或终态刷新执行指标，或定位工具结果后、流式消费及运行结束的延迟。
- **预期现象**：指标快照在全局锁内复制，JSON 序列化和原子文件写入在锁外执行；按会话 I/O 锁串行刷新，防止旧快照覆盖新快照。配置组合段、通知领取、文件锁、流式投递和收尾均有单独计时。
- **规则与边界**：快照复制仍持全局锁，不能宣称指标完全无锁；诊断子段与线程 CPU 不进入互斥墙钟总计。详细刷盘契约及字段见 [09/04 · UC-9D9~9D11](../09-横切能力/04-观测与运行看板方案设计-UseCase清单.md)。
- **依据**：`execution_metrics.py::_flush_session / finish_run`、`agent_loop.py` 本地消费及边界计时；`tests/test_execution_metrics.py`。

### UC-2H6 真实工具返回到 HTTP 发送的轮间计时

- **触发**：工具执行后进入下一模型请求。
- **预期现象**：使用同一 `perf_counter` 时钟和 session/run/react_iter 记录 `execute_one_core` 返回、工具事实提交、下一轮准备、worker 排队/进入、HTTP send 入口、请求头和 body 开始。`local_request_timing` 保存到该请求指标，同时写诊断日志。发送路径只记录内存时间戳，完整指标在流式收尾时发布。
- **本地子段**：`request_conversion_ms` 记录流式消息映射；`wire_json_encode_ms` 仅在直连快速 JSON 编码实际执行成功时出现。它们位于 worker→send 内，不重复加入总间隔，也不以缺失填 0；其他协议/原编码回退路径不伪造该字段。
- **规则与边界**：工具返回锚点位于后置 workspace audit 之前，所有 native/plugin/MCP/host 后端共用，core 内部审查包含在工具执行中；API 前审计、事实提交和准备仍计入间隔。仅关联紧接上一轮的工具。若工具在上一响应尚未结束时提前执行，另记 `local_ready_to_http_send_ms`，但保留用户感知的完整 `tool_return_to_headers_ms`，不扣掉超标样本。ContextVar 随主模型与非流式竞速线程显式复制，避免不同请求/候选串号。未观测 HTTP 时明确 `http_send_observed=false`，不能用 worker 启动冒充发送。
- **依据**：`agent_request_timing.RequestPreparationTrace`、`agent_loop._run_stream_worker_logged`、`RequestResponseLogger.send`、`agent_openai` 竞速线程；`tests/test_agent_request_timing.py`。

### UC-2H7 final投递期间的标题检查和历史收尾

- **触发**：普通聊天或continuation已提交并发布final，进入标题入队检查和finish。
- **预期现象**：标题检查、调用记录打印及历史收尾通过共享线程入口执行，协调循环能够继续转发final；`post_final_processing`记录标题/历史子段，原final_pipeline补充`title_check_after_final`和`post_final_dispatch_overhead`，不再漏计标题检查。
- **规则与边界**：复用`run_fact_commit`等待选定写入，取消/重复取消也先等线程收敛；不提前领取下一用户轮、结束run或跳过耐久事实。原`finish_after_final`保持finish本体口径。final事实时间戳、publish、TCP收帧与浏览器绘制分开记录，不能相互冒充或累加嵌套包络。普通入口和continuation共用实现，不将无生产样本的子代理宣称已验收。
- **依据**：`agent_loop._finish_after_final_off_loop/_finish_after_final_sync`、`tests/test_final_card_delivery.py`；[分析和TCP对照](../../performance/final-card-delivery-2026-10-27.md)。

## 3. 边界

- 用量数据来源见 ../01-LLM接入/08；告警呈现见 ../09-横切能力/03。
- 标题生成使用**执行端模型**（计入用量），非专用小模型——成本可忽略但要知道。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-2H1 | `agent_loop.py` ≈L8694–8918 |
| UC-2H2/2H3 | L1917–2110 |
| UC-2H4 | L4145、`execution_metrics.py` |
| UC-2H5 | `_flush_session / finish_run`；09/04 阶段计时契约 |
| UC-2H6 | `agent_request_timing.py`、HTTP send/trace 与请求指标 `local_request_timing` |
| UC-2H7 | `_finish_after_final_off_loop/_finish_after_final_sync`、`run_fact_commit`、`post_final_processing` |

## 5. 版本记录

- 2026-10-27 v6：补齐标题检查漏计和final后共享循环阻塞；普通/续跑共用等待式线程收尾，保留取消、事实及终态顺序和浏览器未测边界。
- 2026-10-17 v5：新增 UC-2H6，定义真实端点、工具后审计范围、提前执行重叠、竞速线程隔离及未观测状态。
- 2026-09-30 v4：补录执行指标序列化/写盘移出全局锁及按会话防覆盖；修正定时器失败兜底描述，链接本地分段观测。
- 2026-09-20 v3：心跳改为进程级共享线程；明确诊断线程耗尽时非致命降级，并与 exact run 看门狗活性复核衔接。
- 2026-09-14 v2：修正标题段行号（≈L8694–8918）；版本线更新至 `d022831`。
- 2026-09-13 v1：拆分首版（承接 UC-212/213）。
