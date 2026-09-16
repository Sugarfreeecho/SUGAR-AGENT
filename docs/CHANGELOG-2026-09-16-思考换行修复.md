# CHANGELOG — 2026-09-16 思考换行修复（思考与回复文本口径对齐）

## 现象

过程区"思考"行没有换行、文本粘连；同一轮回复正常。且同一主题在不同渠道表现不一（DeepSeek 系全部粘连；MiniMax / GLM 系列多数正常），换台电脑结果又不同。

## 根因

- 供应商按"分片（delta）"推流，DeepSeek 系渠道为逐词分片、空格与换行挂在词首/词尾（对 commandcode 与 api.deepseek.com 的本机实测均如此）。
- `app/agent_openai.py` 的流式采集对每段 reasoning delta 调用 `_coerce_text_or_none()`，其中 `.strip()` 剪掉每段首尾空白 → 逐词分片下空格与换行被全部剥掉，思考文本粘连。
- 回复（content）采集没有这一步、原样拼接，故换行完好；前端只是如实显示（`white-space: pre-wrap`），不是丢失点。
- 全量统计（333 个本地会话、18,221 条思考事件）：`deepseek/deepseek-v4.1-flash` 0% 含换行、100% 零空格；`MiniMax-M3` 74% 含换行。
- 本修复不追溯历史会话数据（旧会话中的思考仍是粘连文本）。

## 修复

`app/agent_openai.py`：

- `_coerce_text_or_none()` 新增 `keep_ws` 关键字参数：`keep_ws=True` 时原样保留流式分片（含纯空白分片，仅真正空串返回 `None`）；默认行为（首尾 strip）不变。
- `_extract_reasoning_text_and_field()` 透传 `keep_ws`。
- 流式思考捕获点改为 `keep_ws=True`；纯空白分片照常入队（用于重组换行），但 `first_delta` / `first_reasoning_seen` 指标判定改用 `strip()` 后的真值，指标语义不变。
- 最终整段拼接处的一次 `.strip()`（本文件 L2531–2533、`agent_loop.py` 拼接处）保持不变——即保持"仅最终整段清理一次"。

## 测试 / 验证

- 新增 `tests/test_reasoning_stream_whitespace.py`（4 例）：逐词分片重组还原原文、纯空白分片不丢弃、默认模式仍首尾清理。先红（TypeError）后绿。
- 相关回归全部通过：
  - `tests/test_reasoning_stream_whitespace.py`：4 passed
  - `tests/test_thinking_format_adaptation.py` + `test_dsml_tool_recovery.py` + `test_multimodal_content_text.py`：30 passed
  - `tests/test_llm_transport.py`：63 passed
  - `tests/test_agent_harness_executor_session.py` + `test_interrupt_stream_runtime.py` + `test_execution_trace_readability.py`：21 passed

## 影响范围

- 仅流式思考采集路径；非流式提取、回复路径、前端渲染与样式均未改动。
- 新会话生效；历史会话不回溯。
- 另一台电脑（或其他项目副本）需同步同一补丁后行为一致。
