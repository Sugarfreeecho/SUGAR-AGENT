# 流式解析、思考字段与 DSML 救援 · 功能方案设计（UseCase 清单）

- 版本：2026-09-13（覆盖至：HEAD `d022831`）
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

## 3. 边界

- 其他"文本冒充工具"形态（非 DSML）不在救援面内——按普通文本处理（已知）。
- 思考字段矩阵以档案 `thinking_format` 为准；未知模型回退保守格式。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-1F1 | `agent_openai.py` L675–800、`agent_reasoning.py` |
| UC-1F2 | `agent_openai.py` L374–674、L1888 |

## 5. 版本记录

- 2026-09-13 v1：拆分首版（承接 UC-108/114）。
