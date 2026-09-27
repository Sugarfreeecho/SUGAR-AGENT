# 流式解析、思考字段与 DSML 救援 · 功能方案设计（UseCase 清单）

- 版本：2026-09-27 v2（覆盖至：当前工作区；含工具调用保真与非法调用拦截）
- 用途：逐条审查（四字段格式）。
- 适用实现：`app/agent_openai.py`（流解析 + 救援）、`app/agent_reasoning.py`、`app/llm/transport.py`。
- 上级：`00-LLM接入整体设计.md`

---

## 1. 功能定位

把各家千奇百怪的流式输出**归一**成统一回合对象（AssistantTurn），并把"思考字段差异"与"工具调用写在文本里"两类现实问题就地化解。

## 2. UseCase

### UC-1F1 思考字段矩阵与回合归一
- **触发**：模型返回 reasoning / thinking 内容（deepseek=reasoning_content、reasoning、think_blocks 等不同格式）。
- **预期现象**：思考内容按目标模型格式**正确转换**并多轮回传（DeepSeek 多轮要求 reasoning_content 回传时不丢）；工具调用增量跨 chunk 合并为完整调用（工具名不碎片）。
- **规则与边界**：思考内容与正文分离展示；格式不支持时降级为普通文本、不报错。
- **依据**：`agent_reasoning.py::build_assistant_additional_kwargs`、`agent_openai.messages_to_openai_params`、`transport.merge_streamed_tool_name`。

### UC-1F2 首 token 判定与 DSML 救援
- **触发**：①统计"首 token 何时到达"；②模型把工具调用写成文本（DeepSeek DSML 形态）。
- **预期现象**：①首 token 判定用于对冲/计时（不误判工具增量）；②DSML 被解析/修复成正规工具调用并执行，流式场景有专门过滤器防漏；界面上表现为**正常的一次工具调用**。
- **规则与边界**：DSML 救援仅针对可识别的 DSML 文本；代码块内的伪 DSML 不误伤；修复失败保留原文（不吞内容）。
- **依据**：`agent_openai._stream_chunk_has_first_token`、`_parse_dsml_invokes / _repair_dsml_turn / _DsmlStreamFilter`。

### UC-1F3 工具调用保真与非法调用拦截
- **触发**：流式组装工具调用增量（`tool_call_delta`）时出现缺少工具名/ID 的残片，或整段全空增量。
- **预期现象**：残片**不被静默丢弃**——保留为可判定的畸形调用（名称/ID 为空），交由主循环统一处理（见 02/01·UC-2A6）；需要把工具调用发回 API 时（多轮回传），缺名称或 ID 的调用被**显式拒绝**（`ValueError`），不发出非法请求，也不会让流式文本被误当最终答案。
- **规则与边界**：合法增量仍按"跨 chunk 合并为完整调用"处理（UC-1F1）；拒绝只取决于"缺名称/ID"这一硬条件——参数为空仍是合法调用。
- **依据**：`agent_openai._tool_acc_to_parsed_list`（保留空 delta）、`agent_openai.format_tool_calls_for_openai_api`（缺名称/ID raise）；回归 `tests/test_llm_transport.py::test_stream_worker_preserves_malformed_tool_deltas_for_agent_rejection`。

## 3. 边界

- 其他"文本冒充工具"形态（非 DSML）不在救援面内——按普通文本处理（已知）。
- 思考字段矩阵以档案 `thinking_format` 为准；未知模型回退保守格式。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-1F1 | `agent_openai.py` L675–800、`agent_reasoning.py` |
| UC-1F2 | `agent_openai.py` L374–674、L1888 |

## 5. 版本记录

- 2026-09-27 v2：新增 UC-1F3——工具调用增量的保真（全空/缺名缺 ID 的增量保留为可判定畸形，不静默丢弃）与发回 API 前的非法调用拦截（缺名称/ID 显式拒绝，交主循环清洗或受控重试）。
- 2026-09-13 v1：拆分首版（承接 UC-108/114）。
