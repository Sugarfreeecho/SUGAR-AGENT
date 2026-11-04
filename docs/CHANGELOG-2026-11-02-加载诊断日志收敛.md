**加载诊断日志收敛：一次加载一条、传输指标不再双写（2026-11-02）**

`ui_loading` 这类结构化诊断日志本身不含正文，但同一次页面加载会写 7 行左右，字段高度重复。这次在不改前端的前提下，于服务端把同一批客户端记录压成一条摘要，并去掉一处传输指标的重复输出。

**问题有多明显。** `agent_terminal.log` 里 7,779 条 `ui_loading`：1,070 条 `client_load_start` + 1,083 条 `client_request_start` + 1,089 条 `client_request_end` + 1,076 条 `client_load_end`，另有 1,063 对 `server_start/server_end` 和 1,335 条 `server_loop_lag`。同一次加载的 4 条客户端记录重复了 `session_id`、`load_id`、`kind`、`started_at`，`logged_at` 在整批里完全相同。

**合并规则。** 客户端仍按原样上报 4 条记录，`/api/ui-loading-diagnostics` 在写入前按 `load_id` 合并：

| 原记录 | 去向 |
|---|---|
| `client_load_start` / `client_load_end` | 合并为一条 `client_load`，保留 `status/phase/elapsed_ms/fetch_ms/各阶段 _ms` |
| `client_request_start` | 丢弃（`load_end` 的 `elapsed_ms/fetch_ms` 已覆盖） |
| `client_request_end` | 进入 `requests[]`：`request_id/route/status/status_code/ms/headers_ms/body_ms/server_ms`，失败时额外保留 `phase/reason` |

只有批次里出现 `client_load_end` 才合并，落单的请求记录原样保留；`requests[]` 最多 6 条，避免异常页面把数组撑大。

用你贴的那组记录实测：4 行 1,033 字符 → 1 行 415 字符（行数 −75%，字节 −60%）：

```
ui_loading {"event":"client_load","load_id":"c7e48d0e-…","kind":"session_list","started_at":"2026-11-02T03:32:52.016Z","status":"success","phase":"layout","elapsed_ms":29,"fetch_ms":25.2,"layout_ms":3.6,"requests":[{"request_id":"bfa30245-…","route":"state","status":"success","status_code":200,"elapsed_ms":25,"headers_ms":23.6,"body_ms":1.2,"server_ms":8,"phase":"body"}]}
```

**顺带两处。** `server_loop_lag` 从"每次卡顿一条"改为最多每 30s 一条，带 `count` 与 `max_lag_ms`（1,335 条 → 几十条）；空字段（`session_id=""`、`error_name=""`）不再序列化。

**去掉一处重复。** `http_transport_timing` 的 12 个字段与 `llm_stream_timing` 里的 `transport_breakdown` 步骤完全一致，前者不再单独输出（`execution_metrics.record_phase` 保留）。历史日志里这一项约 21,000 行、10 MB。

**还没动的候选**（同类问题，改动面更大）：

| 家族 | 现状 |
|---|---|
| 每次 LLM 调用 | `pre_api_timing` + `llm_stream_timing` + `local_request_timing` + `llm_local_consumer_timing` + worker started/completed/consumed，约 7 行/次 |
| 每次写入 | `runtime_v2_write_started` + `runtime_v2_write_timing`，各 48,000 行 |
| 每次工具 | `tool_execution_timing` + `tool_result_post_timing` + `tool_to_next_api_timing`，3 行/次 |

验证：`tests/test_loading_diagnostics.py` 12 项通过（新增合并、失败明细、落单透传、卡顿聚合），`test_llm_transport_timing.py` / `test_agent_request_timing.py` 共 35 项通过。

主要文件：`app/ui_loading_diagnostics.py`（`compact_client_records`、`sanitize_client_record`、`monitor_event_loop`）、`app/agent_loop.py`（移除 `http_transport_timing`）、`tests/test_loading_diagnostics.py`、`SPEC.md` §16。
