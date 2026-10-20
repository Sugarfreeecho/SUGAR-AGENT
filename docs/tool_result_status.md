# 工具执行状态

工具执行状态与结果正文分开处理。通用响应层只信任 `ToolOutcome`，不再扫描任意工具的
JSON 字段或错误关键词来覆盖明确的调用状态。

| 来源 | 状态依据 |
| --- | --- |
| 宿主服务 | `ToolOutcome.completed/failed`，失败时保留错误码 |
| MCP | 原始 `isError` 协议标记；连接、重连或调用异常返回明确失败 |
| 代码插件 | worker 的调用状态：正常返回为完成，抛异常为失败；返回值是业务数据 |
| 内置 Shell | 进程状态回执优先，保留真实退出码；中断、状态未知与失败分开 |
| 旧式内置工具 | 仅按已知工具的返回契约进行兼容判断 |

`tool_result_status.py` 集中实现旧式适配：文件工具识别自身的 `Error:`、
`Failed to read/write/edit file:` 等诊断；目录、glob、grep 识别自身的失败回执。
读取到的文件正文、搜索无匹配、插件业务 JSON 不作为通用失败证据。
网页工具只读取宿主封装的状态字段，不扫描网页正文。

`run_shell` 的文本退出码/超时诊断仅作没有进程回执时的兼容路径。
`terminal_send` 的 `timeout/inferred_idle` 表示观察等待结束，不证明命令失败或退出；
`job_output` 继续保留现有语义：任务明确失败或带非零进程退出码时计失败，
任务仍在运行或等待超时不计失败。

执行事件的 `status` 保留 `ok`、`timed_out`、`truncated`、退出码和耗时，同时增加
`source` 与失败 `code`；执行记录保存同一份 `tool_status`，历史回放保留判定依据。
MCP 的旧文本/附件返回 API 默认不变，Agent 执行路径通过 `return_outcome=True` 取得明确状态。

这些规则作用于新执行，不自动重判或改写已持久化的旧失败记录。

验证：`tests/test_tool_result_status_regressions.py`、`tests/test_mcp_result_status.py`、
`tests/test_tool_search.py`、`tests/test_execution_recovery.py`。
