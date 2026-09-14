# 网络与连接保障 · 功能方案设计（UseCase 清单）

- 版本：2026-09-13（覆盖至：HEAD `d022831` + 未提交网络恢复改动）
- 用途：逐条审查（四字段格式）。
- 适用实现：`app/agent_loop.py`（重连循环）、`app/agent_harness.py`（离线检测）、`app/ssl_bypass.py`。
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

## 3. 边界

- 流观察者重连（前端 SSE 续看）是**另一条通道**，见 ../05-WebUI对话界面/03。
- 代理支持：Web 工具与模型请求均可走代理配置（`_httpx_proxy` 等），与本节独立。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-1G1 | `agent_loop.py` L181/3344/7496+；`agent_harness.py` L901/987 |
| UC-1G2 | `app/ssl_bypass.py` |

## 5. 版本记录

- 2026-09-13 v1：拆分首版（承接 UC-116/117）。
