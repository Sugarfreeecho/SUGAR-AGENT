**日志只留索引，不落正文（2026-11-02）**

日志从"内容留痕"改成"可定位的索引"：模型正文、思考、工具参数值、工具结果、用户输入、系统提示词不再写入 `logs/`，改为记录长度、哈希、结构、状态与耗时。需要正文时回到 `sessions/<id>/events.jsonl` 与 `TempOutput/tool-results/`。

**起因是三条实测数据。** 单条 `write_file` 日志最长 63,213 字符（整份文件内容）；`finish()` 每次 LLM 调用都把整段请求链逐条写进日志；单个 88.8 MiB 的会话日志里 83.8 MiB 是 43,370 条 `event_delivery` 计时行。611 个日志文件累计 669 MiB，没有轮转也没有清理。

**正文改为指纹。** 新增 `app/log_safety.py`：`digest()` 输出 `len=… sha=…`，`shape()` 输出 `{path:str#92, contents:str#63213}` 这样的结构，都不含内容。三种模式：

| `LOG_PAYLOAD_MODE` | 行为 |
|---|---|
| `off`（默认） | 只写元数据，正文完全不出现 |
| `digest` | 额外写每段正文首行 80 字符 |
| `full` | 恢复完整正文（仅临时排障，首行告警） |

`LLM_FULL_CALL_TRACE=1` 现在必须配合 `full` 才生效，避免调试开关绕过策略。

**逐点改造。** 工具调用行改为 `tool_call name=… args={…} args_sha=… status=… result=(len=… sha=…) call_id=…`；模型回合合并成一行 `llm_turn`；`finish()` 的 `>>> Agent to LLM` 全量 dump 只在 `full` 模式保留，默认每个调用一行 `llm_call`；MCP 结果改为 `blocks/text_chars/media` 计数；流式分片与损坏参数不再打印前 200 字符；日志文件名改为 `{session8}.log`，用户输入不再进文件名（新增 `logs/session_index.jsonl` 保留 session 映射）。

**兜底与体积。** `PayloadSafeFormatter` 在格式化阶段把超长行与多行消息压成摘要（异常堆栈保留首尾），即使新增代码漏改也写不进整段正文。日志改用 `RotatingFileHandler`（默认 8 MiB × 2）；启动时按 `LOG_RETENTION_DAYS` / `LOG_TOTAL_MAX_MB` 盘点，默认 `LOG_PRUNE_MODE=report` 只报告不删除。`event_delivery` 计时改为按 run 聚合，`AGENT_LOG_TIMING=detail` 可回全量。

**顺带修的两处。** `setup_logging` 现在显式设置 logger 级别为 INFO，不再受宿主 root 级别（uvicorn / pytest 可能停在 WARNING）影响；重复调用时先关闭旧 handler，避免 Windows 上文件句柄泄漏。

**验证。** 新增 4 组测试（`test_log_safety.py`、`test_log_payload_policy.py`、`test_setup_logging_metadata_only.py`、`test_local_timing_summary.py`，共 14 项），其中静态检查扫描 `app/`，禁止 `工具调用:` 拼接参数、`str(res['tool_args'])`、`raw_args[:N]` 等写法。原有 `test_local_operation_timing.py`、`test_round_entry_timing.py`、MCP 相关测试保持通过。

**升级提示。** `LOG_TRUNCATE_KEEP_CHARS` 只在 `full` 模式下生效；历史日志不会被自动改写，`python scripts/prune_agent_logs.py` 可先 dry-run 盘点。

主要文件：`app/log_safety.py`（新增）、`app/agent_harness.py`（`setup_logging`、轮转、盘点）、`app/agent_loop.py`（`llm_turn`、`tool_call`、`finish`）、`app/agent_mcp.py`、`app/agent_openai.py`、`app/agent_local_timing.py`、`app/agent_subagent.py`、`scripts/prune_agent_logs.py`（新增）。
