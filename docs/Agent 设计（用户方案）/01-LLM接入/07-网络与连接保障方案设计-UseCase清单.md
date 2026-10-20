# 网络与连接保障 · 功能方案设计（UseCase 清单）

- 版本：2026-10-19 v6（生成中途半开连接停滞检测与进度续接）
- 用途：逐条审查（四字段格式）。
- 适用实现：`app/agent_loop.py`（重连循环与消息到达预热）、`app/agent_harness.py`（离线检测、连接池、直连适配器与预热）、`app/agent_openai.py`（流传输观测）、`app/ssl_bypass.py`。
- 上级：`00-LLM接入整体设计.md`

---

## 1. 功能定位

把"本机断网 / 证书拦截"这类**环境级**问题从"模型错误"里独立出来，用等待/重连/直达策略应对。

## 2. UseCase

### UC-1G1 断网等待与重连（NET）
- **触发**：请求失败且判定为连通性问题；或本机已离线。
- **预期现象**：界面提示"网络连接失败，正在重连（第 n 次，x 秒后重试）…"；本机离线时进入**等待恢复**（不空转发请求）；恢复后自动续跑；上限 5 次后进入常规失败路径（错误卡 NET）。
- **规则与边界**：错误分类用 `LocalNetworkUnavailableError` 与 `machine_network_available()` 双重判定（避免把"模型 500"错当断网）；重连计数有界、可被用户中断打断。
- **依据**：`agent_loop.py`（NETWORK_RECONNECT_MAX_ATTEMPTS=5、`_wait_for_local_network_recovery`、reconnect 事件）。

### UC-1G2 SSL 直达
- **触发**：内网/公司代理环境，证书链不被系统信任。
- **预期现象**：默认不因证书校验失败而断联（请求可直达）；外网环境可用 `SSL_BYPASS_ENABLED=0` 关闭该行为。
- **规则与边界**：该补丁对 requests/httpx 全局生效——属"本地可信环境"假设；关闭开关即时生效（重启进程）。
- **依据**：`app/ssl_bypass.py`（main.py 导入即生效）。

### UC-1G3 流响应排空与连接复用
- **触发**：模型以 SSE/流式响应返回 `[DONE]`，随后同一端点继续发起请求。
- **预期现象**：客户端看到逻辑结束标记后继续把底层响应读到 EOF，使 httpx 能把连接放回 keepalive 池；连续热请求通常复用既有 TCP/TLS 连接。
- **规则与边界**：`OPENAI_KEEPALIVE_EXPIRY_SEC` 默认 300 秒；连接池默认最多保留 20 条 keepalive、总连接上限 100。逻辑流在 `[DONE]` 后不再产生内容事件，但必须完成 drain；超过保活期限仍允许正常新建连接。
- **依据**：`agent_harness.RequestResponseLogger`、SDK 流 `[DONE]` 分支、`OPENAI_KEEPALIVE_EXPIRY`。

### UC-1G4 首选候选直连与完整回退
- **触发**：候选链调用首选模型。
- **预期现象**：首选候选使用 Chat Completions 时默认通过 `_DirectStreamTransport` 进入本地 httpx 直连流；Anthropic Messages 与 Responses 保留原生 transport。直连失败时仍由原候选循环继续重试、熔断或回退。
- **规则与边界**：仅替换首选候选的 transport，不改变候选顺序、请求预算、模态投影、熔断和回退语义；不能把“直连优化”实现成绕过 facade 的单一路径。适配器必须逐一透传同一 chunk 的**全部流事件**（思考/正文/多路工具调用等，见 UC-1G6）。
- **依据**：`agent_harness._DirectStreamTransport`、`_FallbackCompletions` 候选循环。

### UC-1G5 启动与空闲后连接预热
- **触发**：WebUI 启动约 3.5 秒后，或新消息到达且连接池已超过空闲阈值。
- **预期现象**：技能/环境提示构建以及 TCP/TLS 建连在后台提前发生，首条消息或长时间空闲后的首轮不承担全部冷启动成本。
- **规则与边界**：启动预热与按需预热均不得阻塞服务启动或消息接收；按需预热只在池子过冷时调度 worker。预热失败是非致命的，真实请求仍走正常重试与回退。
- **依据**：`agent_loop.warm_prompt_build_path`、`agent_harness.warm_llm_connections / warm_llm_connections_if_stale`、`webui.start_webui_lifecycle`。

### UC-1G6 直连适配器的事件保真
- **触发**：单个流式 chunk 同时携带多种增量——思考 + 正文 + 一路或多路工具调用（或另有 usage / finish 字段）。
- **预期现象**：该 chunk 的**全部事件逐一透传**：`reasoning_delta`、`content_delta`、每个 `tool_call_delta`（各自 `index` 原样保留）、`usage`、`finish` 一条不丢——不再"只发首个非空字段"，也不再"只取第一个工具调用"。
- **规则与边界**：事件顺序保持既有次序（usage 前置；思考 → 正文 → 工具调用 → 收尾）；多路工具调用的 `index` 必须原样保留，供上层按索引合并；该保真只约束直连适配器输出，不改变 facade 路径、候选循环与回退语义（见 UC-1G4）。
- **依据**：`agent_harness._DirectStreamTransport._to_events`（由单事件 `_to_event` 改为逐事件生成器）；回归 `tests/test_llm_transport.py::test_direct_stream_preserves_mixed_text_and_all_tool_calls`。

### UC-1G7 直连请求 JSON 快速编码

- **触发**：Chat Completions 直连流构造 HTTP 请求体。
- **预期现象**：对只含普通 JSON 值的 payload，使用项目既有 orjson 依赖一次编码为 bytes，再交给 httpx；headers、Content-Length、超时、取消、候选预算和回退均沿用原路径。记录 `wire_json_encode_ms` 与消息转换 `request_conversion_ms`，区分本地编码与服务器响应。
- **规则与边界**：只接受精确的 str/bool/int/有限 float/list/字符串键 dict/None，整数限定编码器支持范围；特殊类型、非有限数、非字符串键、过深结构或依赖缺失继续交给原 httpx 编码器，不能静默接受原先非法的值。保留自定义 Content-Type，未提供时补 application/json；编码失败回原编码器，不额外发送请求。只改变直连 Chat 请求体编码，不改 Responses/Anthropic transport、持久事件格式或权限决策。
- **依据**：`agent_openai._fast_wire_json / _http_stream_chat_completion`、`agent_request_timing`；`tests/test_wire_json_encoding.py` 实际 httpx 发送验证 Unicode、数字、嵌套值、headers、依赖回退和非法数不发送。

### UC-1G8 阻塞LLM请求的独立请求池

- **触发**：ReAct将阻塞LLM流、纯非流式请求或流式回退交给后台线程。
- **预期现象**：惰性进程级请求池复用线程，承接阻塞LLM流、纯非流及回退请求；不与事件循环的短文件I/O竞争默认executor槽位。固定占用12个通用worker、320ms释放的私有复现中，请求进入从约330ms缩至约0.1ms；不能直接外推真实313ms全部来自该队列。
- **规则与边界**：线程容量沿用Python3.10默认池上限`min(32,cpu_count+4)`，仍可能因池满或系统调度排队。ContextVar、异常、候选/transport/流事件保持；排队取消不执行，运行中取消沿用调用方原有路径。WebUI关闭在服务清理finally中取消排队请求，不等待阻塞网络线程；后续生命周期可重建。流/非流共享trace工厂，回退保留最早实际send，不能把后续尝试覆盖为首API。非流式成功后看板正确结束，不停在waiting_first_token；事实/权限检查不移出关键路径。
- **依据**：`agent_request_executor.run_request_worker/shutdown_request_executor`、`agent_loop`流任务派发及`webui.stop_webui_lifecycle`；`tests/test_agent_request_executor.py`。版本、真实失败和复现边界见[d68报告](../../performance/agent-session-8533-run-d68-2026-10-18.md)。

### UC-1G9 生成中途半开连接恢复

- **触发**：模型已开始返回内容、思考或工具分片，切换网络后旧 HTTP 连接保持打开但不再返回分片。
- **预期现象**：默认连续 60 秒没有模型分片时提示正在保存进度并恢复连接，随后进入 UC-1G1 的离线等待或有界重连；收到的正文继续参与回复，已经开始执行的工具沿用实际执行结果。
- **规则与边界**：`STREAM_WORKER_IDLE_TIMEOUT_SEC` 与首 token 竞速、HTTP 超时独立；页面心跳不延长模型等待。模型实际分片会刷新计时，缓冲输出模式也刷新；正常持续输出不受总时长限制。旧线程等待退出有界，队列、取消信号、完成信号与日志参数绑定原请求，迟到输出不能污染后续请求。网络错误按异常类型和传输消息识别，含空消息 ReadError、对端关闭、TLS EOF 与本地化套接字错误；持续失败按现有重连上限结束。仅靠静默超时无法判断模型是否仍在计算，长时间静默输出的模型可适当调大阈值，修改后重启后端。
- **依据**：`agent_loop._StreamActivityWatchdog`、`agent_openai.run_chat_completion_stream_worker(on_stream_activity)`、`agent_harness._is_network_connectivity_error`；`tests/test_stream_network_recovery.py` 以本地 HTTP 服务复现半段停滞、候选门面、工具只执行一次、缓冲持续输出与重连耗尽。测试未切换操作系统的真实网络。

## 3. 边界

- 流观察者重连（前端 SSE 续看）是**另一条通道**，见 ../05-WebUI对话界面/03。
- 代理支持：Web 工具与模型请求均可走代理配置（`_httpx_proxy` 等），与本节独立。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-1G1 | `agent_loop.py` L181/3344/7496+；`agent_harness.py` L901/987 |
| UC-1G2 | `app/ssl_bypass.py` |
| UC-1G3 | `RequestResponseLogger`、SDK 流 EOF drain、httpx limits |
| UC-1G4 | `_DirectStreamTransport`、`_FallbackCompletions` |
| UC-1G5 | `warm_prompt_build_path`、`warm_llm_connections*`、WebUI lifecycle |
| UC-1G6 | `agent_harness._DirectStreamTransport._to_events`、`tests/test_llm_transport.py` |
| UC-1G7 | `agent_openai._fast_wire_json / _http_stream_chat_completion`、`tests/test_wire_json_encoding.py` |
| UC-1G8 | `agent_request_executor`、`agent_loop`流式/非流式/回退派发、`webui.stop_webui_lifecycle` |
| UC-1G9 | `_StreamActivityWatchdog`、模型分片活动回调、`tests/test_stream_network_recovery.py` |

## 5. 版本记录

- 2026-10-19 v6：新增 UC-1G9；补齐生成后半开连接检测、传输错误分类及已执行工具恢复分支的 `AssistantTurn` 导入，保留旧请求退出边界和进度续接。

- 2026-10-18 v5：新增UC-1G8；将阻塞LLM流式/非流式/回退请求从通用默认executor隔离，保留上下文/取消/异常和服务关闭语义；修复既有非流分支未初始化变量及成功后看板状态，不把原worker包络误称纯线程池排队。

- 2026-10-17 v4：新增 UC-1G7，普通 JSON 使用已安装依赖快速编码，特殊类型及错误保留原编码路径；新增消息转换和 wire 编码单调时钟子段。
- 2026-09-28 v3：新增 UC-1G6《直连适配器的事件保真》——同一 chunk 的 reasoning/content/多路 tool-call 增量逐一发出（此前只返回首个非空字段、只取第一个工具调用）；回归含"混合文本 + 双工具调用"用例；UC-1G4 补交叉引用。
- 2026-09-20 v2：补齐流响应 EOF drain、keepalive 连接池、首选候选直连适配器，以及启动/空闲后后台预热。
- 2026-09-13 v1：拆分首版（承接 UC-116/117）。
