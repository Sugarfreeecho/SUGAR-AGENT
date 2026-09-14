# Responses 状态模式与原生压缩 · 功能方案设计（UseCase 清单）

- 版本：2026-09-13（覆盖至：HEAD `d022831`）
- 用途：逐条审查（同上级格式）。
- 适用实现：`app/llm/responses/state.py`、`compact.py`、`capabilities.py`、`app/agent_openai.py`、`app/agent_loop.py`（commit）。
- 上级：`00-LLM接入整体设计.md`

---

## 1. 功能定位

在 OpenAI Responses 线上管理**会话状态续接**（stateful / stateless）与**服务端原生压缩**（checkpoint），并在不支持时安全降级。

## 2. UseCase

### UC-1B1 状态模式判定与续接
- **触发**：使用官方 OpenAI（或强制 Responses）对话。
- **预期现象**：默认 `auto` 判定；stateful 时用 previous_response_id 续接；无法续接时自动切 stateless 重放，对话不中断、不重复上屏。
- **规则与边界**：切换发生在**请求构造层**，用户感知仅为"偶尔慢一点"；续接锚点失效不会导致历史错位。
- **依据**：`state.py::RequestShape / ContinuationAnchor / evaluate_continuation`。

### UC-1B2 原生压缩检查点
- **触发**：长会话在原生线上达到压缩点。
- **预期现象**：走服务端压缩（checkpoint）替代/减少本地压缩；检查点可续接，重启不丢。
- **规则与边界**：本地压缩（见 ../09-横切能力/01）仍是兜底；两条路径互斥闩由会话锁保护。
- **依据**：`compact.py::CompactionMatch / ResponsesCompactionCheckpoint`、`agent_openai.compact_responses_history`、`agent_loop._runtime_v2_commit_responses_compaction`。

### UC-1B3 错误分类与能力缓存
- **触发**：Responses 线返回结构化错误（invalid_previous / unsupported_state / encrypted_reasoning / unsupported_compact / rate_limit / transient）。
- **预期现象**：对应自愈动作（重放、降级、重试）；重复踩同一坑被能力缓存记住，后续请求不再尝试不支持特性。
- **依据**：`capabilities.py::classify_responses_error / ResponsesErrorKind`（+ 缓存）。

## 3. 边界

- 加密推理块被拒 → 走重放路径；极端情况下多一次完整重发（表现为略慢，属预期）。
- 新端点"声称 Responses 兼容但不支持 compact"→ 探测/缓存后自动放弃原生压缩 🟡（能力缓存覆盖）。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-1B1 | `llm/responses/state.py`（全 230 行） |
| UC-1B2 | `llm/responses/compact.py`、`agent_openai.py` L43 |
| UC-1B3 | `llm/responses/capabilities.py` |

## 5. 版本记录

- 2026-09-13 v1：拆分首版（承接 UC-102/103 与错误分类条目）。
