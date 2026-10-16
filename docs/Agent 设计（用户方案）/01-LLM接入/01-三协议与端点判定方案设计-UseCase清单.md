# 三协议与端点判定 · 功能方案设计（UseCase 清单）

- 版本：2026-10-15（显式协议选择，移除 auto 档位与协议探测）
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

用户为模型档案明确选择 Chat Completions、Responses 或 Anthropic Messages，系统按照所选协议生成对应端点 URL。保存档案时不发送协议探测请求。

## 2. UseCase

### UC-1A1 三协议显式选择
- **触发**：首次配置或编辑模型档案。
- **预期现象**：API 类型提供 `openai-compatible`、`openai-responses`、`anthropic` 三项；运行时始终使用档案指定的协议。
- **规则与边界**：未提供类型的新档案默认 Chat Completions；编辑时省略类型保留原选择。旧别名 `openai` 归一为 `openai-compatible`。新提交的 `auto` 或未知类型直接报错，不根据 URL 或模型名称猜协议。
- **依据**：`transport.py::normalize_provider / resolve_profile_provider`；`model_profiles.py::upsert_profile`。

### UC-1A2 端点 URL 构造
- **触发**：发起请求。
- **预期现象**：不同档案的 base_url（含带路径前缀的代理）都能拼出正确端点；`/models` 列表端点同样可用。
- **规则与边界**：URL 规范化（去尾斜杠、折叠重复斜杠、路径保留）；错误 base_url 给出明确报错而不是怪响应。
- **依据**：`model_profiles.py::chat_completions_url_for_base / responses_url_for_base / anthropic_messages_url_for_base / models_url_for_base`。

### UC-1A3 旧 auto 档案迁移
- **触发**：读取包含旧 `auto` 类型的模型档案存储。
- **预期现象**：按旧版本的官方域名映射迁移一次并落盘为明确协议；自定义网关保持旧版 Chat Completions 默认值。
- **规则与边界**：迁移不发网络请求，已有明确协议的档案不改写。协议探测函数已删除；用户主动点击的上下文窗口探测继续使用所选协议。
- **依据**：`model_profiles.py::_migrate_legacy_auto_protocol / load_store / probe_model_context`。

## 3. 边界

- 华为云等特殊域名有专门分支（`is_huawei_api_domain`），属兼容处理而非独立协议。
- 协议判定与"模型能力"无关；能力另由档案/探测决定（见 UC-1A1 延伸与 ../01-LLM接入/08）。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-1A1 | `transport.py::LLMProvider / normalize_provider / resolve_profile_provider` |
| UC-1A2 | `model_profiles.py::*_url_for_base` |
| UC-1A3 | `model_profiles.py::_migrate_legacy_auto_protocol / load_store` |

## 5. 版本记录

- 2026-10-15 v2：移除协议 auto 档位、URL 自动判定和网络协议探测；明确三种协议、旧数据一次性迁移和保存时校验。
- 2026-09-13 v1：拆分为专项设计（承接原《全模块 UseCase 清单》UC-101/118 段内容）。
