# 会话加载诊断日志

适用范围：会话首次打开/强制重载的历史读取、历史回放，以及会话列表加载、刷新和状态对账。部署包含前端构建和后端重启。代码安装本身不代表运行中的页面已启用。

## 关联一次加载

所有新增记录以 `ui_loading ` 开头，后跟单行 JSON。正常启动器会将后端 stderr 写入 `logs/agent_terminal.log`，不依赖 `webui` logger 的 INFO 级别。

- `client_load_start/end`：浏览器的一次加载，`load_id` 相同，含 session_id、UTC 开始时间、端到端耗时、结果、失败原因，以及 fetch/hydrate/images/layout/scroll 各阶段耗时。初始历史预取与消费共用一次 load_id。
- `client_request_start/end`：该加载下的每次 HTTP 请求，具有独立 request_id、attempt、接口类型、超时阈值、HTTP 状态。重试和回退各记一条。区分 headers 等待和 body 消费；后者包含 JSON 解析与主线程调度。
- `server_start/end`：请求进入 ASGI 中间件至响应发送结束。回显 `X-Request-ID`，读取 `X-UI-Load-ID`；客户端会在 URL 附加 `ui_request_id`，便于与访问日志和 Resource Timing 对齐。成功、HTTP 错误、异常和取消都记录结尾。
- `server_end.backend_timing`：历史快照原有的 worker 排队、setup、read_page、count、user_turns、context_tokens、todo_plan、execution_recovery、prepare_response、serialize、total。异常时保留已完成阶段，phase 标示停在哪一步。
- `server_loop_lag`：每两秒检查一次事件循环，只在超过 500 ms 延迟时记录 expected_at、lag_ms。用于发现请求进入 ASGI 之前就已发生的主循环停顿；不能仅靠它区分同步 I/O、CPU/GIL 或系统调度。

失败原因区分 `timeout`、`cancelled`、`network`、`http`、`json_parse`、`invalid_payload` 和 `render`。主动切走会话记 cancelled；超时仍保留 AbortError，不再与主动取消混为一谈。原有超时阈值未调整。

浏览器提供 Resource Timing 时，还记录 queue_ms、ttfb_ms、network_body_ms、after_network_ms。queue_ms 是 fetchStart 到 requestStart，可能含连接建立等准备，不能等同纯排队；after_network_ms 是 responseEnd 到 JSON 消费完成，包含解析与调度，不能等同纯 JSON CPU。取消请求的网络阶段可能缺失，缺失值不补成零。

server_end.response_complete 仅表示 ASGI send 已结束，不保证浏览器已经消费响应；disconnect_observed 仅表示应用读到了断连消息。单靠后端 HTTP 200 不能证明页面加载成功。

## 查阅

```powershell
rg 'ui_loading' logs/agent_terminal.log
rg '目标会话ID|目标load_id|目标request_id|server_loop_lag' logs/agent_terminal.log
```

前端控制台同时输出 `ui_loading`。可在浏览器控制台导出：

```js
JSON.stringify(window.__MYAGENT_LOADING_DIAGNOSTICS__.snapshot(), null, 2)
```

浏览器 localStorage 的 `myagent-loading-diagnostics-v1` 最多保留 128 条，刷新页面后仍可查。上传为同源 `/api/ui-loading-diagnostics`，一秒合并一次，最多 32 条/32 KiB，独立三秒期限，不等待、不重试；后端拥堵或断网可能导致中心日志缺少客户端记录，此时查浏览器留存。旧后端返回 404 时停止上传，本地记录继续保留。后端日志队列最多 1024 条，满时丢弃并在随后记录 dropped_records。

只记录标识符、阶段、耗时、状态和异常类型；不采集消息正文、提示词、异常文本、Authorization、请求体或完整 URL。此改动用于取证，没有以提高超时或重复加载代替性能修复。

## 本机部署验证

2026-10-22 19:37，在 runtime-status 确认为零个运行任务后通过托盘 IPC 重启，未中断任务。新前端为 `main-BpWytjG9.js`；源码与构建产物一致性检查通过，相关 101 项回归通过。

实际浏览器打开已完成会话 2e5ab3de，页面显示 131 个 feed 行，无 loading/retry/历史加载错误；同一 load_id `0ae54719-045c-46fd-8e35-fef4770369a8` 和 request_id `03cba3d2-d4a1-4f08-978f-fa7f77a0b8d7` 的客户端开始/请求/结束、服务端开始/结束均落入终端日志。该次总耗时 9,375 ms，其中 fetch 2,759 ms、hydrate 548 ms、images 2,026 ms、layout 64 ms、scroll 3,978 ms，后端 handler 1,208 ms。此样本仅验证日志覆盖和关联，不是性能改进的前后对照。

实际验证了切换掉预取请求的 cancelled 记录，以及带指定 request_id 的参数校验错误 HTTP 422 记录。超时（包括读取 body 时超时）、网络/JSON 等分类由运行真实前端函数的故障注入回归验证。生产 lifespan 入口覆盖、监测器退出也有回归。

19:38:52.821 预期的事件循环 tick 延迟 6,697 ms，与同窗口一次列表状态请求耗时 7,466 ms 对齐，证明请求进入 handler 前的停顿能够被单独记录；该记录尚不能单独确定停顿的具体调用栈。

日志摘录：`.analysis/loading-logs-20261022/live-verification.json`。用户原先打开的页面需要重新加载前端后，才具备客户端完整计时；已启动的后端中间件会为旧页面请求生成服务端 request_id。
