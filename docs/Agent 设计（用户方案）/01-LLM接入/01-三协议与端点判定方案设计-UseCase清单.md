# 三协议与端点判定 · 功能方案设计（UseCase 清单）

- 版本：2026-09-13（覆盖至：HEAD `6acc6bf`）
- 用途：**逐条审查功能与现象是否符合需求**。每条用例给出「触发 → 预期现象 → 规则与边界 → 依据」。审查时按编号逐条勾选；如有不符，反馈编号即可。
- 适用实现：`app/llm/transport.py`、`app/llm/provider_registry.py`、`app/model_profiles.py`（URL/probe）。
- 上级：`00-LLM接入整体设计.md`

---

## 0. 阅读指南

| 字段 | 含义 |
|---|---|
| **触发** | 谁做了什么操作（用户 / 模型 / 系统） |
| **预期现象** | 界面上应该看到什么（这是审查验收的核心） |
| **规则与边界** | 为什么是这个现象；什么情况下会不同 |
| **依据** | 代码位置（可复核） |

---

## 1. 功能定位

一条模型档案（base_url + model + key）进来，系统**自动决定**走哪条线协议、生成对应端点 URL，无需用户理解协议差异。

## 2. UseCase

### UC-1A1 三协议自动判别（auto）
- **触发**：任一模型档案发起对话。
- **预期现象**：官方 OpenAI host → Responses；官方 Anthropic host → Messages；其余端点一律 → Chat Completions 兼容；用户无感。
- **规则与边界**：`auto` 规则**故意保守**——只有官方 host 走原生协议，代理/镜像/第三方一律兼容线（避免误判）；如需强制可设 `EXECUTOR_LLM_TYPE=openai`（可让 Responses 代理走原生线）。
- **依据**：`transport.py::detect_provider / resolve_provider / resolve_profile_provider`。

### UC-1A2 端点 URL 构造
- **触发**：发起请求。
- **预期现象**：不同档案的 base_url（含带路径前缀的代理）都能拼出正确端点；`/models` 列表端点同样可用。
- **规则与边界**：URL 规范化（去尾斜杠、折叠重复斜杠、路径保留）；错误 base_url 给出明确报错而不是怪响应。
- **依据**：`model_profiles.py::chat_completions_url_for_base / responses_url_for_base / anthropic_messages_url_for_base / models_url_for_base`。

### UC-1A3 wire 协议探测（诊断）
- **触发**：配置新档案后点击探测/诊断。
- **预期现象**：系统按端点试探可用协议（payload + headers 组合、路由缺失判定），给出结论；失败时告知原因。
- **规则与边界**：探测不发正式对话内容（有专用探针 payload）；探测结果只作建议，不自动改写档案。
- **依据**：`model_profiles.py::detect_wire_protocol / _wire_probe_payload / _wire_probe_headers / _wire_route_missing`。

## 3. 边界

- 华为云等特殊域名有专门分支（`is_huawei_api_domain`），属兼容处理而非独立协议。
- 协议判定与"模型能力"无关；能力另由档案/探测决定（见 UC-1A1 延伸与 ../01-LLM接入/08）。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-1A1 | `transport.py` L49–200（LLMProvider 枚举、归一与解析） |
| UC-1A2 | `model_profiles.py` L619–661 |
| UC-1A3 | `model_profiles.py` L663–776 |

## 5. 版本记录

- 2026-09-13 v1：拆分为专项设计（承接原《全模块 UseCase 清单》UC-101/118 段内容）。
