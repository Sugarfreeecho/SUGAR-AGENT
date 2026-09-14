# 缓存、用量与隐私 · 功能方案设计（UseCase 清单）

- 版本：2026-09-13（覆盖至：HEAD `6acc6bf`）
- 用途：逐条审查（四字段格式）。
- 适用实现：`app/llm/types.py`、`app/runtime_observability.py`、`app/model_profiles.py`（responses_store_disabled）、`app/agent_openai.py`（脱敏）。
- 上级：`00-LLM接入整体设计.md`

---

## 1. 功能定位

三类"看不见但重要"的承诺：**前缀缓存命中**（快 + 省）、**用量可观测**、**隐私最小暴露**。

## 2. UseCase

### UC-1H1 前缀缓存与会话身份
- **触发**：多轮对话（同一会话）。
- **预期现象**：会话级 prompt_cache_key 稳定 —— 命中时响应更快、计费更省；不同**用途**（main/title/summary/…）的请求互不污染缓存键。
- **规则与边界**：键 = hash(scope=lineage、purpose、issuer、model)；无会话 ID 时不生成键（回退默认行为）。
- **依据**：`llm/types.py::prompt_cache_key`。

### UC-1H2 token 用量采集
- **触发**：每次模型响应（含流式）。
- **预期现象**：用量进入运行看板/执行指标；对对话与界面零打扰。
- **规则与边界**：流式下 usage 若在末包才给，也在流结束时补齐；解析失败不报错（记日志）。
- **依据**：`agent_openai.extract_usage_dict`、`runtime_observability.record_usage`。

### UC-1H3 隐私旗标与脱敏
- **触发**：①档案开启"禁用服务端存储"；②日志/状态文案包含密钥类信息。
- **预期现象**：①Responses 线不带服务端存储（server_storage_allowed=false 语义）；②密钥/敏感串在日志与状态文案中被统一打码。
- **规则与边界**：脱敏覆盖运行时日志、状态文本与工具输出（`_redact_runtime_log_text` / `redact_sensitive_tool_text` 双通道）。
- **依据**：`responses_store_disabled`、`_redact_runtime_log_text`、`redact_sensitive_tool_text`。

## 3. 边界

- 请求用途（purpose）枚举：main / goal_judge / title / summary / security_review / diagnostic —— 具体触发方见各模块（如标题生成见 ../02-ReAct运行时/）。
- 前缀缓存是"尽力命中"，不保证 100%（供应商侧策略变化）。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-1H1 | `llm/types.py` L60–97 |
| UC-1H2 | `agent_openai.py` L183、`runtime_observability.py` L269 |
| UC-1H3 | `model_profiles.py` L88、`agent_openai.py` L129 |

## 5. 版本记录

- 2026-09-13 v1：拆分首版（承接原清单 §1/§7 相关条目）。
