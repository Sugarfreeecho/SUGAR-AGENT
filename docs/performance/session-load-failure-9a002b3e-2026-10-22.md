# 9a002b3e 会话历史加载失败定位

调查时间：2026-10-22，Asia/Shanghai。目标会话：`9a002b3e-3bc4-4ba5-b9bc-8f140cb1d87e`。

## 已确认的直接原因

从用户正在使用的 Edge 页面读取到控制台异常：

```text
加载会话消息失败: AbortError: signal is aborted without reason
    at eval (myagent-ui.js:23617:55)
```

通过该页面实际执行的脚本核对，23617 行为：

```js
const timer = setTimeout(function () { controller.abort(); }, ms);
```

调用链是 `fetchSessionHistoryJSON → fetchWithTimeout(..., 30000, consumeJSON)`。因此直接失败是历史请求的 30 秒期限触发 AbortController；失败在历史响应读取阶段，尚未进入消息回放。截图中“41s”属于执行过程容器的显示，不能当作请求的精确网络耗时。

浏览器工具返回的 console timestamp 是抓取缓冲日志时的时间，不能拿它冒充异常发生时间。后端慢请求的相邻日志时间在 **17:31:13.257–17:31:13.456**，重试在 **17:32:20.500–17:32:20.726**；慢请求本身未带墙钟时间，用相邻日志限定时间。

## 后端慢在哪里

`logs/agent_terminal.log:12037` 与 `:14103` 记录了两次同参数的历史读取：

| 阶段 | 首次慢请求 | 随后重试 |
|---|---:|---:|
| 后端总耗时 | 18,580 ms | 706 ms |
| 进入 worker 的排队 | 77 ms | 21 ms |
| 初始化 | 3,084 ms | 184 ms |
| 读取 200 条可见事件 | 5,624 ms | 327 ms |
| 用户消息目录 | 685 ms | 44 ms |
| 执行记录恢复 | 9,073 ms | 89 ms |
| 其中检查点载入及校验 | 7,925 ms | 内存命中 |
| JSON 序列化 | 34 ms | 39 ms |

首请求执行记录的来源是 `checkpoint`，恢复完整的 **3,643 条执行记录**后才筛到首屏所需的 **112 条**。恢复后的增量仅 275 个事件、293,920 字节；增量读取/解析约 296 ms，应用约 3 ms。主要代价在完整检查点载入和校验，不在增量重放或最终复制。

真实文件规模：

- `events.jsonl`：136,933,621 字节。
- `snapshots/execution_recovery.chk`：19,629,624 字节。
- 检查点要求完整校验的事件前缀：136,639,701 字节。

`RecoveryCheckpoint.load()` 先读取完整检查点，校验其 SHA256，再通过 `source_matches(..., full=True)` 扫描并校验上述事件前缀，随后 JSON 解码、结构校验、内存大小遍历。`ExecutionJournal.read()` 在 `_state()` 恢复完成之后才按 `min_runtime_seq` 筛选记录。前端限制为 200 事件/约 1.11 MB，并没有限制这部分后台恢复成本。

本次未发现目标历史接口的 500/投影解析异常。随后重试返回 HTTP 200 且使用内存缓存。我额外进行的一次同参数只读请求也返回 200：客户端总计 208 ms、后端 156 ms。暖缓存快不能证明首次读取问题已经修复。

## 浏览器还有额外等待

实际页面保留的这次成功重试计时：

| 阶段 | 耗时 |
|---|---:|
| history.fetch，含请求及 JSON 消费 | 6,538 ms |
| 对应后端处理 | 706 ms |
| history.hydrate | 657 ms |
| history.images | 490 ms |
| history.scroll | 2,035 ms |
| history.total | 9,768 ms |

请求阶段比后端计时多约 5.83 秒。这部分可能包含浏览器连接排队、后端事件循环开始 handler 之前的等待、收包/JSON 消费和主线程调度，现有计时不足以进一步分摊。不能把它全部说成网络延迟或前端渲染。

原页面 Resource Timing 缓冲已到 250 项，没有保留目标失败请求的条目。没有为取证刷新页面或重启后端。首次后端 18.58 秒和客户端 30 秒超时并不矛盾，二者计时范围不同，但缺少原始网络条目，不能精确还原首次额外等待。

## 当前已有的计时与缺口

- 后端 `open_session_timing`、`open_session_loading_details`、`/history_snapshot slow` 记录各处理阶段，并在响应带回 `timing`、`loading_diagnostics`、`Server-Timing`。当前运行日志级别下，慢请求 warning 可见，普通成功请求的 info 汇总未必写入。
- 前端 `window.__MYAGENT_UI_PERF__.snapshot()` 保存 `history.fetch / hydrate / images / scroll / total` 等分阶段数据，存储键是 `myagent-ui-performance-v1`，位于浏览器 localStorage，不自动上传后端。
- 失败分支仅打印通用异常，缺少 session_id、request_id、经过时间、阶段和明确的 timeout/cancel/http/body 错误分类；未成功收到历史响应的尝试也没有完整 history 总耗时记录。
- 前后端没有共同 request_id；后端 worker queue 不包含浏览器请求排队，也不包含 handler 开始之前的事件循环延迟。

后续修复应让首屏的执行记录恢复成本受可见范围约束，保留必要的数据边界校验；同时记录失败请求的关联 ID、端到端计时和超时原因，并将会话切换的滚动动画从内容就绪判定中移开。调整超时数值只能改变何时显示失败，无法消除本次确认的首次恢复成本。

证据摘录：`.analysis/session-load-failure-9a002b3e-20261022/backend-evidence.json`。本轮只做日志、现有页面和只读接口取证，未修改运行代码、会话消息或上下文计算。
