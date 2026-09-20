# 网络与连接保障 · 功能方案设计（UseCase 清单）

- 版本：2026-09-20 v2（覆盖至：当前工作区）
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
- **预期现象**：首选候选优先通过 `_DirectStreamTransport` 进入本地 httpx 直连流，减少 facade/线程转接开销；直连失败时仍由原候选循环继续重试、熔断或回退。
- **规则与边界**：仅替换首选候选的 transport，不改变候选顺序、请求预算、模态投影、熔断和回退语义；不能把“直连优化”实现成绕过 facade 的单一路径。
- **依据**：`agent_harness._DirectStreamTransport`、`_FallbackCompletions` 候选循环。

### UC-1G5 启动与空闲后连接预热
- **触发**：WebUI 启动约 3.5 秒后，或新消息到达且连接池已超过空闲阈值。
- **预期现象**：技能/环境提示构建以及 TCP/TLS 建连在后台提前发生，首条消息或长时间空闲后的首轮不承担全部冷启动成本。
- **规则与边界**：启动预热与按需预热均不得阻塞服务启动或消息接收；按需预热只在池子过冷时调度 worker。预热失败是非致命的，真实请求仍走正常重试与回退。
- **依据**：`agent_loop.warm_prompt_build_path`、`agent_harness.warm_llm_connections / warm_llm_connections_if_stale`、`webui.start_webui_lifecycle`。

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

## 5. 版本记录

- 2026-09-20 v2：补齐流响应 EOF drain、keepalive 连接池、首选候选直连适配器，以及启动/空闲后后台预热。
- 2026-09-13 v1：拆分首版（承接 UC-116/117）。
