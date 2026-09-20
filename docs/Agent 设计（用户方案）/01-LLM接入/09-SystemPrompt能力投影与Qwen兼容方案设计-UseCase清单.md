# System Prompt 能力投影与 Qwen 兼容 · 功能方案设计（UseCase 清单）

- 版本：2026-09-20 v2（覆盖至：当前工作区）
- 用途：定义模型请求组装阶段如何把 Core 中允许多条、允许后置的 `SystemMessage`，投影为目标模型接受的线协议形状。
- 适用实现：`app/agent_openai.py`、`app/agent_harness.py`、`app/model_profiles.py`、`app/templates/advance_config.html`。
- 上级：`00-LLM接入整体设计.md`
- 上游：`../02-ReAct运行时/02-提示装配与静态段缓存方案设计-UseCase清单.md`

---

## 1. 功能定位

Core 历史以语义和时序为准，允许静态提示、运行时上下文、hook、continuation、子代理通知和尾部提醒分别形成 system 消息；不同供应商对 system 的读取能力不同，因此在**实际候选模型已经确定、请求即将发送**时做能力投影。

Qwen Chat Completions 的安全下限是：system 若存在，必须位于消息开头且只能有一条。本设计不把该约束扩散到 Core 历史，也不无条件改写所有模型请求。

## 2. 设计原则与 dsh 取舍

参考 `D:\AI\AI Agent\Deepseek Harness\deepseek-harness`：

1. dsh 用模型能力声明决定是否允许 in-history system；缺省按单一首部 system 处理。
2. dsh 的 `llm-pi-ai/src/context.ts::splitSystemPrompt` 在只有一个 system 槽位时，让未占用槽位的后置 system 原位折叠为 user，以保留时序。
3. MyAgent 继续保留多来源 system 的 Core 表达，在请求适配边界采用同样的“**保位置优先于保角色**”策略。
4. MyAgent 增加工具事务保护：若降级为 user 会切断尚未闭合的 `assistant(tool_calls) → tool` 链，则保角色优先，将该 system 并入首部。

因此，本设计不是“全局拼接提示词”，而是“按候选模型能力进行无持久副作用的请求投影”。

## 3. 策略解析

模型档案字段 `system_prompt_mode` 支持：

| 配置值 | 请求时有效策略 | 说明 |
|---|---|---|
| `auto` | Qwen Chat Completions → `merge`；其他 → `preserve` | 默认值 |
| `merge` | Chat Completions → `merge` | 用于模型别名或兼容端点手动覆盖 |
| `preserve` | `preserve` | 显式关闭自动适配 |

`auto` 的 Qwen 判断为：

```text
resolve_profile_provider(profile) == openai-compatible
AND "qwen" in profile.model.lower()
```

边界：

- 匹配不区分大小写，覆盖 `qwen-plus`、`Qwen/Qwen3-32B`、`qwen3-vl-plus` 等。
- 不依据 `base_url` 或 DashScope 域名触发，避免同一兼容端点上的其他模型误合并。
- `qwq-*` 或供应商自定义别名不会自动命中；需要在档案中显式选 `merge`。
- Responses 与 Anthropic 不应用该字段；即使配置 `merge`，有效策略仍为 `preserve`，由各自 transport 的原生顶层 system/instructions 逻辑处理。
- 未知配置值在档案保存阶段拒绝，不静默回退；旧档案缺字段按 `auto` 读取。
- API 返回保存值 `system_prompt_mode` 和解析值 `effective_system_prompt_mode`，便于界面与诊断区分“配置”与“实际行为”。

## 4. UseCase

### UC-1I1 自动识别与显式覆盖

- **触发**：保存模型档案，或从候选链选择一个模型准备请求。
- **预期现象**：Qwen + Chat Completions 在 `auto` 下得到 `merge`；非 Qwen 得到 `preserve`；用户可用显式值覆盖模型名判断。
- **规则与边界**：先判线协议，再判显式配置/模型名；非 Chat Completions 始终不进入本投影。配置写入缓存键，修改后不会复用旧客户端策略。
- **依据**：`model_profiles.normalize_system_prompt_mode / profile_system_prompt_mode / profile_cache_key`。

### UC-1I2 首部 system 合并

- **触发**：有效策略为 `merge`，消息从 index 0 开始存在一条或多条连续 system。
- **预期现象**：所有非空首部 system 按原顺序以 `\n\n` 连接，输出为 index 0 的唯一 system；不去重、不改写文本。
- **规则与边界**：空白 system 丢弃；如果没有任何有效 system，则不凭空创建。转换不修改输入消息对象，重复执行结果相同。
- **依据**：`agent_openai._merge_system_prompt_for_single_system_model`。

### UC-1I3 中段与尾部 system 保序降级

- **触发**：有效策略为 `merge`，用户/助手历史之后出现 system（如 runtime context、continuation、尾部收敛提醒）。
- **预期现象**：该消息在原位置把 role 改为 user，内容与相对顺序不变；Qwen 最终只看到零条或一条首部 system。
- **规则与边界**：不把普通后置提示提前到首部，避免改变“此时才生效”的时序语义；尾部提示变化不会反复改写首部缓存前缀。空 system 直接删除。
- **依据**：`agent_openai._merge_system_prompt_for_single_system_model`。

### UC-1I4 工具事务邻接保护

- **触发**：system 出现在 assistant 已发出一个或多个 tool call、但相应 tool result 尚未全部返回的区间。
- **预期现象**：该 system 不转 user，而是追加进首部 system；assistant 与全部 tool result 仍保持合法事务顺序。
- **规则与边界**：按 `tool_call_id` 跟踪未闭合调用；无 ID 的调用使用计数兜底。无法确认时选择并入首部这一保守策略，宁可损失一次前缀缓存，也不构造必然被端点拒绝的工具历史。
- **依据**：`pending_tool_call_ids / pending_anonymous_tool_calls`，回归 `test_system_inside_tool_transaction_folds_into_leading_prompt`。

### UC-1I5 候选级适配与 fallback

- **触发**：主候选失败，fallback 链切换到另一模型；或一次性文本请求、压缩请求选择具体候选。
- **预期现象**：请求只按**实际发送候选**的策略转换。例如 DeepSeek 主候选保持多 system；切到 Qwen 备用候选后才合并。
- **规则与边界**：`ExecutorLLMClient` 的规范序列化阶段固定为 `preserve`；有 transport 时在流式逐候选发送前投影；任一候选缺 transport 时，`_FallbackCompletions.create` 的 SDK facade 循环也必须在 reasoning remap 后投影。裸 profile client、`complete_text` 与 `compact_history` 读取同一解析结果，不能形成旁路。
- **依据**：`agent_harness.create_openai_client_for_profile / ExecutorLLMClient / _profile_candidate`。

### UC-1I6 三协议边界

- **触发**：同一 Core 历史分别发送到 Chat Completions、Responses 或 Anthropic。
- **预期现象**：Chat Completions 仅在策略为 `merge` 时使用本投影；Responses 继续把 system/developer 汇入单条 `instructions`；Anthropic 继续汇入顶层 `system`。
- **规则与边界**：本功能不修改 `OpenAIResponsesTransport`、`chat_messages_to_anthropic`，也不改变非 Qwen Chat 请求的序列化结果。
- **依据**：`agent_openai._messages_to_params_for_client`、`llm/transport.py::_responses_instructions / chat_messages_to_anthropic`。

### UC-1I7 档案界面与诊断

- **触发**：用户在高级设置新增或编辑模型档案。
- **预期现象**：高级配置显示 “SYSTEM PROMPT 兼容”选择器，可选 `auto / merge / preserve`；保存后立即进入客户端与候选缓存键。
- **规则与边界**：默认 `auto`；该设置只描述 Chat Completions 的消息形状，不代表 Core 会话历史被重写。
- **依据**：`app/templates/advance_config.html`、模型档案 API、`model_profiles.public_profile`。

### UC-1I8 媒体失败重建仍保持 system 形状

- **触发**：bare client 首次发送含图片/音频/视频的请求，端点在 create 或惰性流迭代阶段返回“不支持媒体”，运行时从原始 Core 消息重建纯文本请求。
- **预期现象**：重建请求去除媒体、保留路径/占位文本，同时再次应用当前客户端的 system 策略；Qwen 重试仍只有开头一条 system。
- **规则与边界**：不能假设首次序列化结果可复用，因为媒体回退刻意从原始消息重建；因此重建完成后必须重新执行投影。重复投影依赖幂等不变量，不会重复拼接内容。
- **依据**：`agent_openai.run_chat_completion_stream_worker` 的 media fallback 分支、`_messages_to_text_only_params`、`_merge_system_prompt_for_single_system_model`。

## 5. 转换示例

| 输入历史 | Qwen wire 输出 |
|---|---|
| `S(A), S(B), U(Q)` | `S(A\n\nB), U(Q)` |
| `S(A), U(Q), S(Tail)` | `S(A), U(Q), U(Tail)` |
| `U(Q), S(Runtime)` | `U(Q), U(Runtime)`（允许零条 system） |
| `S(A), A(tool_calls=[1,2]), T(1), S(X), T(2)` | `S(A\n\nX), A(...), T(1), T(2)` |
| `S(空白), U(Q)` | `U(Q)` |

其中 `S/U/A/T` 分别表示 system/user/assistant/tool。

## 6. 请求不变式

启用 `merge` 后必须同时满足：

1. system 数量 `<= 1`；
2. system 若存在，只能位于 index 0；
3. 非 system 消息的相对顺序保持不变；
4. 未闭合工具事务中不插入 user/assistant；
5. 文本不去重，非空内容不静默丢失；
6. 转换幂等；
7. Core 历史与落盘数据不被反写。

## 7. 验收与回归

| 验收项 | 测试依据 |
|---|---|
| 多首部合并、顺序与分隔符 | `tests/test_system_prompt_adaptation.py::test_leading_system_messages_merge_and_late_system_keeps_position_as_user` |
| 空 system、无首部 system | 同文件 empty / late-system 用例 |
| 工具链邻接 | `test_system_inside_tool_transaction_folds_into_leading_prompt` |
| 非 Qwen/无配置保持不变 | `test_client_mode_gates_projection_without_changing_other_clients` |
| Qwen 名称矩阵、协议边界、显式覆盖 | `test_auto_mode_detects_qwen_chat_profiles` 等 |
| 档案持久化与非法值拒绝 | `test_profile_persists_mode_and_rejects_unknown_values` |
| 无 transport facade 出口 | `test_non_transport_fallback_facade_projects_selected_qwen_candidate` |
| 媒体失败重建出口 | `tests/test_multimodal_fallback.py::test_stream_media_fallback_reapplies_single_system_projection` |

全量回归基线：`1682 passed, 4 skipped, 9 subtests passed`。

## 8. 版本记录

- 2026-09-20 v2：补齐两处发送支路：任一候选缺 transport 时的 `_FallbackCompletions.create` SDK facade，以及 bare client 媒体失败后的纯文本重建重试；新增出口级回归。
- 2026-09-20 v1：新增 Qwen 首部唯一 system 能力投影；采用 dsh 的后置 system 保序降级策略，并加入未闭合工具事务保护、候选级 fallback 适配和档案显式配置。
