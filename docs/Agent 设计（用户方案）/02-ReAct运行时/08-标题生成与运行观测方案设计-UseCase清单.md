# 标题生成与运行观测 · 功能方案设计（UseCase 清单）

- 版本：2026-09-13（覆盖至：HEAD `6acc6bf`）
- 用途：逐条审查（四字段格式）。
- 适用实现：`app/agent_loop.py`（标题 L8598–8900、计时 L1917–2110）、`app/runtime_observability.py`、`app/execution_metrics.py`。
- 上级：`00-ReAct运行时整体设计.md`

---

## 1. 功能定位

会话的"表面功夫"与"里子数据"：标题自动生成（后台、防脏）、运行埋点（快而不扰）。

## 2. UseCase

### UC-2H1 会话标题自动生成
- **触发**：新会话首条消息后。
- **预期现象**：列表里的标题在短时间后自动出现（几个字概括）；生成失败有兜底标题（截取首条消息）；不阻塞对话。
- **规则与边界**：脏内容防护——本地路径、思考标签样式的候选标题会被拒/清洗；会话被删则不生成；生成 worker 有队列。
- **依据**：`_session_title_worker / _generate_session_title_with_diagnostics / _fallback_session_title / _looks_like_local_path_title`。

### UC-2H2 pre-API 计时埋点
- **触发**：每轮请求前。
- **预期现象**：各准备阶段（历史装载、提示构建、压缩等待等）耗时被记录；对用户零打扰。
- **依据**：`_pre_api_timing_mark / _pre_api_timing_log / _pipeline_step_timing_log`。

### UC-2H3 流式与首包计时
- **触发**：模型流式响应。
- **预期现象**：首包/总时长记录（供看板与排查）；异常流有对应日志。
- **依据**：`_llm_stream_timing_log`。

### UC-2H4 实时度量与心跳
- **触发**：运行中。
- **预期现象**：运行看板的心跳/指标线程级更新；长任务无外界反馈时仍可看到"活着"。
- **依据**：`_emit_live_metrics`、`execution_metrics.py`。

## 3. 边界

- 用量数据来源见 ../01-LLM接入/08；告警呈现见 ../09-横切能力/03。
- 标题生成使用**执行端模型**（计入用量），非专用小模型——成本可忽略但要知道。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-2H1 | `agent_loop.py` L8598–8898 |
| UC-2H2/2H3 | L1917–2110 |
| UC-2H4 | L4145、`execution_metrics.py` |

## 5. 版本记录

- 2026-09-13 v1：拆分首版（承接 UC-212/213）。
