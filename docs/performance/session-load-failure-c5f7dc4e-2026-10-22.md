# c5f7dc4e 会话本次加载失败

调查时间：2026-10-22 19:27–19:33，Asia/Shanghai。会话：`c5f7dc4e-7760-4b35-bbf0-28cf48c6dd5e`。只读检查用户现有 Edge 页面与后端日志，未刷新该页面、重启或中断任务。

## 本次证据

浏览器实际执行的旧脚本报错：

```text
加载会话消息失败: AbortError: signal is aborted without reason
    at eval (myagent-ui.js:23617:55)
```

此前已核实该行是 fetchWithTimeout 的到期 abort；历史请求期限是 30 秒。此次 Resource Timing 保留了对应 history_snapshot 请求：

- 开始：19:25:26.898。
- 结束：19:25:56.942。
- 时长：30,044.4 ms。
- requestStart/responseStart/transferSize 均为 0。取消请求可能缺失这些字段，不能据此断言请求未到达服务端或精确区分 headers/body；新诊断日志将单独记录这两阶段。
- 当前页面的 c5f7dc4e 只有 switch.prepare，未新增 history.fetch/hydrate/total 成功记录。错误发生在 fetch/JSON 消费阶段，未进入此次历史回放。

同一时间并非只有历史慢：

| 请求 | 开始（北京时间） | 耗时 |
|---|---|---:|
| 9a002b3e/subagents | 19:25:25.065 | 50,992 ms |
| c5f7dc4e/unread-result/clear | 19:25:26.721 | 46,159 ms |
| c5f7dc4e/steer | 19:25:26.787 | 45,959 ms |
| c5f7dc4e/model_profile | 19:25:26.787 | 46,615 ms |
| c5f7dc4e/interactions | 19:25:26.787 | 46,922 ms |
| c5f7dc4e/permissions | 19:25:26.738 | 47,258 ms |
| api/model_profiles | 19:25:26.787 | 30,005 ms，取消 |
| api/extensions/session-ui | 19:25:26.899 | 30,069 ms，取消 |

19:25:28、38、48、58 的 runtime-status 心跳也分别约五秒失败。多个成功请求直到 19:26:12–16 才集中收到响应。

## 已定位的放大路径

后端 `local_operation_timing` 于 **19:26:11.878** 记录了同一会话 `context_summary_progress` 事件：

- 总耗时 **47,881.998 ms**，monotonic 332367.3547409–332415.2367386，折算约 19:25:23.996–19:26:11.878。
- ui_append 47,880 ms，其中进入 mirror 前约 25.27 秒。
- ui_mirror 22,609 ms；transaction_lock_lookup 6,225 ms、transaction_directory 9,583 ms、transaction_file_open 2,923 ms、fact_append 3,815 ms。
- transaction_os_lock 只有 12 ms；不能把全部延迟归咎于会话文件锁。
- ui_append 的 thread CPU 仅 31.25 ms，多数时间不是 Python 计算。具体造成路径/文件系统操作突然变慢的底层原因尚无证据确认。

源码链路：`StreamEventBridge._drain()` 在它绑定的调用者事件循环 await `emit`；`agent_loop` 的正常会话和 continuation 两个 `emit_event`，对非 tool_call 且需要持久化的事件都直接调用同步 `session_manager.append_ui_event(...)`，随后才 await 发布事件。`context_summary_progress` 属于这条路径，最终调用同步 RuntimeMirror.append、session_transaction 和文件写入。复核更正：普通 `/chat` 在专用 chat-stream 线程运行自己的循环，不能称为 HTTP 主事件循环；`/continue` 和部分后台恢复入口则直接 await continuation，可能占用 HTTP 循环。

因此，同步慢文件操作至少会阻塞所属运行循环，HTTP 循环中的恢复入口还会影响其他请求。浏览器的 30 秒期限落在此次 47.88 秒窗口内，其余轻量接口也集体等待 46–51 秒，说明存在并发退化；但现有记录没有将该 run 的循环归属与 HTTP 主线程一一对应，也没有该历史请求的 ASGI 开始时间。不能据此断定这一个 append 独自造成所有 HTTP 延迟，或精确分摊浏览器连接等待与服务端等待。

这是本次明确的后端阻塞问题，历史切片、DOM 渲染或上下文 token label 不是这次失败的位置。也不能用本次证据覆盖此前 9a002b3e 冷检查点恢复慢的独立问题。

后续修复该路径应把持久化移出调用者事件循环，仍然等待落盘后再发布事件，并验证取消、事件先后顺序、正常会话与 continuation 两个入口。仅加长前端超时不会消除其他接口一起卡住的问题。本次按“先补齐日志”的范围，补上关联 ID、失败记录和 server_loop_lag，未在诊断改动中重写持久化流程。

后续进展：同日进入会话打开 P90 < 15 秒 Goal 后，已将上述两个 emitter 的非工具 UI 持久化移到后台并等待完成，相关取消与先后顺序回归已通过。部署、48 个不同会话的首次打开和真实模型并发生成数据见 [P90 优化与验收记录](session-open-p90-2026-10-22.md)。
