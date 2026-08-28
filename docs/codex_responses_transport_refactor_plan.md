# Codex 风格 Responses 传输层重构方案

状态：已完成（2026-08-25；全量回归 `1327 passed, 4 skipped`）  
范围：`app/llm/`、Responses 状态落盘、上下文变更联动、官方压缩接口  
不在本方案内：重做 Agent 主循环、重做 Goal Judge 判定逻辑、重做前端视觉

实施结果：Provider Registry 和三协议兼容入口保持稳定；canonical item、严格 anchor、
issuer capability、Runtime V2 generation/branch invalidation、官方 compact checkpoint、
本地 fallback、稳定 prompt cache、旧状态迁移和隐私 UI 已落地。Goal Judge 仅增加传输用途
隔离，没有修改其 verdict 业务规则。

## 1. 结论

本次重构以 Codex 的状态管理原则为主：

1. 当前本地有效历史是唯一事实来源；服务端 `response_id` 只是可丢弃的传输优化。
2. 系统必须始终能从本地历史构造一份完整、原生、可独立执行的 Responses 请求。
3. 只有当前历史严格延长了已确认的上一轮上下文，且请求属性完全一致时，才允许发送
   `previous_response_id + 新增 items`。
4. 任何改写、删除、回退、分支、压缩、模型或工具配置变化都会使旧 continuation anchor
   失效；系统自动完整回放，不要求用户选择 stateful/stateless。
5. `previous_response_id` 过期或服务端丢失时，只清除当前 anchor 并完整重试一次；不得向后
   扫描并重试更老的 response ID。
6. 官方 OpenAI 优先使用 `/responses/compact` 产生 opaque compaction item；不支持该接口的
   Responses 代理才使用本地摘要 checkpoint。

目标不是把服务端会话当数据库，而是在不牺牲正确性的前提下，自动减少普通追加对话的重复输入。

## 2. 与重构前实现的主要差异

重构前 `_matching_previous_response()` 从历史尾部向前寻找同 issuer 的任意 stateful
`response_id`，找到后便省略它之前的消息。这个判断缺少历史前缀校验，会在以下场景错误续链：

- 用户改写或删除旧消息；
- 会话回退后旧 assistant state 仍残留；
- 分支复制了带 response ID 的 assistant message；
- 压缩替换了旧上下文，但旧 `_myagent_responses` 仍在；
- instructions、tools、reasoning 或 text 配置发生变化；
- 当前 response ID 失效后再次扫描到相同或更老的锚点。

重构后不再“查找一个能用的旧 ID”，而是只维护一个与当前 canonical history head 对应的
`ContinuationAnchor`。无法证明它有效，就不用它。

## 3. 核心不变量

### 3.1 Canonical history

模型历史必须保存 Responses 原生语义，而不只是扁平的 chat message：

- user/developer input item；
- assistant message output item，包括 `phase`、`status` 和 content parts；
- reasoning item，包括可回放的 `encrypted_content`；
- `function_call`，保留函数名、`call_id` 和 arguments；
- `function_call_output`，与 `call_id` 稳定配对；
- compaction item；
-未来新增的 provider output item，在不理解时也能无损落盘。

内部可以继续把这些数据附在 `AssistantMessage.additional_kwargs`，但传输层必须先投影为统一的
`CanonicalResponseItem` 序列，再决定如何上行。

### 3.2 完整回放永远可用

任何一轮请求都必须能走以下基线路径：

```text
canonical history
    -> Responses wire serializer
    -> store=false
    -> include reasoning.encrypted_content
    -> 完整 input
    -> 稳定 prompt_cache_key
```

`store=false` 回放时，序列化器保留 provider 返回的原生 item、语义字段和 `call_id`；
它们只允许在相同 issuer 内回放，不能跨凭据/端点发送。
加密 reasoning 按 issuer 隔离；不同 Base URL、provider 或模型签发的 blob 不得跨端点发送。

### 3.3 增量必须可证明

增量请求不是配置偏好，而是一次纯算法判断：

```text
anchor.covered_items + anchor.response_output_items
        必须严格等于
current_canonical_items 的前缀
```

同时 `RequestShape` 必须完全相同。参与比较的字段至少包括：

- issuer、model；
- instructions；
- tools、tool choice、parallel tool calls；
- reasoning 配置及 include；
- text/structured-output 配置；
- store、service tier、prompt cache key；
- 会影响模型上下文或输出协议的其他请求字段。

流式传递专用字段和 tracing metadata 可以不参与上下文比较，但必须有明确白名单，不能默认忽略新字段。

## 4. 目标架构

在保留现有 `ProviderRegistry` 扩展边界的前提下，落地为以下边界。为维持既有 import 和
第三方 provider factory 兼容，`transport.py` 仍是 adapter/factory facade；纯状态算法已从
facade 中移出：

```text
app/llm/
  __init__.py                 对外稳定导出
  types.py                    TransportEvent、LLMRequestContext、LLMRequestPurpose
  provider_registry.py        现有 provider factory/dialect/version/capability 扩展点
  transport.py                provider 选择兼容 facade、三种线协议 adapter/factory
  responses/
    items.py                  chat/history <-> canonical Responses items
    state.py                  anchor、request shape、前缀校验
    capabilities.py           结构化错误分类与 issuer 能力 TTL
    compact.py                官方 compact checkpoint
```

`agent_openai.py` 只消费 `TransportEvent` 和最终 `provider_state`，不再知道 Responses SSE
事件名、stateful fallback 或原生 item 结构。`agent_loop.py` 只负责把完成的 provider state
随 assistant turn 一起原子落盘。

Chat Completions 和 Anthropic 保持独立 adapter，不为追求抽象统一而强行模拟 `response_id`。

`LLMProvider` 枚举只表示内建 provider ID，不得成为 provider 扩展的封闭事实源。
手动和自动选择最终都解析为 registry ID；受信扩展可以通过 registry 注册新
provider，而不需要修改主循环。

## 5. 数据模型

### 5.1 RequestShape

```python
@dataclass(frozen=True)
class RequestShape:
    issuer: str
    model: str
    instructions_hash: str
    tools_hash: str
    tool_choice_hash: str
    reasoning_hash: str
    text_hash: str
    include_hash: str
    service_tier: str
    prompt_cache_key: str
    store: bool
```

对象先做稳定 JSON 规范化再计算 SHA-256。比较时 hash 用于快速拒绝；调试/测试构建可保留规范化对象，
避免字段遗漏长期不可见。

### 5.2 ContinuationAnchor

```python
@dataclass(frozen=True)
class ContinuationAnchor:
    schema_version: int
    issuer: str
    model: str
    response_id: str
    history_revision: int
    request_shape_hash: str
    covered_item_count: int
    covered_prefix_hash: str
    response_output_items: tuple[CanonicalResponseItem, ...]
    completed: bool
    server_stored: bool
    created_at: str
```

约束：

- 只保存最后一次完整完成或明确 incomplete 的响应；failed/cancelled 流不能安装 anchor。
- anchor 覆盖范围包括产生该 response 的 request input 和 response output。
- hash 相同后仍进行规范化 item 的结构比较，hash 不是唯一正确性依据。
- session 只有一个 head anchor；新成功响应原子替换旧 anchor。
- `_myagent_responses` 中旧 schema 没有前缀信息，只能作为 stateless replay material，不能直接续链。

建议的新落盘结构：

```json
{
  "schema_version": 2,
  "api": "responses",
  "issuer": "...",
  "canonical_output_items": [],
  "continuation_anchor": {
    "response_id": "resp_...",
    "history_revision": 7,
    "request_shape_hash": "...",
    "covered_item_count": 18,
    "covered_prefix_hash": "...",
    "server_stored": true
  }
}
```

完整 `canonical_output_items` 属于事实历史；`continuation_anchor` 属于可丢弃缓存，两者不得混为一体。

### 5.3 ProviderCapabilities

能力按 issuer 缓存：

```text
responses
previous_response_id
store
encrypted_reasoning_replay
compact
responses_websocket
```

只有明确的 schema/unsupported 错误才能降低能力；timeout、限流、5xx 不得永久标记“不支持”。能力缓存
需要版本和 TTL，配置修改后失效。

## 6. 自动请求算法

### 6.1 普通一轮

```text
1. 从当前有效本地历史生成 canonical_items
2. 每轮重新生成 instructions
3. 生成 RequestShape 和 session prompt_cache_key
4. 读取唯一 head anchor
5. 验证：
   - anchor schema/issuer/model/revision 一致
   - request shape 一致
   - anchor 标记 server_stored
   - canonical_items 与 anchor 覆盖前缀结构一致
6. 全部通过：发送 previous_response_id + suffix items
7. 任一失败：发送完整 canonical_items
8. 聚合流，保存完整原生 output items
9. response.completed 后原子安装新 head anchor
```

每轮都发送 instructions，因为 `previous_response_id` 不继承上一轮 instructions。

### 6.2 官方 OpenAI

HTTP/SSE 基线使用标准 Responses：

- 无可用 anchor：完整回放并使用 `store=true` 建立新 anchor；
- 有严格匹配 anchor：`previous_response_id + suffix`；
- anchor 失效：清除 anchor，完整回放一次并建立新 anchor；
- 用户或组织要求 ZDR/禁用存储：固定走 `store=false` 完整原生回放。

可选 Responses WebSocket 已作为独立传输适配器实现：只对官方 OpenAI 域名自动启用，复用相同
canonical 状态模型、`previous_response_id` 和 request body。自定义代理不做 WebSocket 盲探测；
握手/请求在无可见输出时只降级一次到 HTTP/SSE。WebSocket 是优化插件，不改变 canonical
history、落盘 schema、compact checkpoint 或 HTTP fallback。

### 6.3 自定义 Responses 代理

默认 `store=false` 完整回放，当前版本不对代理盲探测 stored continuation。未来若 provider 扩展
开启 HTTP continuation，也必须先获得端点明确的 stored-response 成功证明。代理拒绝 `store`、
`previous_response_id`、`include` 或 compact 时分别降级，不能因为一个字段失败就把整个端点
误判为 Chat Completions。

### 6.4 错误恢复

错误分类必须结构化，不以大段字符串模糊匹配为主：

| 错误 | 行为 |
| --- | --- |
| previous response not found/expired/deleted | 清除当前 anchor，完整重试一次 |
| invalid encrypted content | 丢弃当前 issuer 不可用的加密 reasoning，完整重试一次 |
| store/previous_response_id unsupported | 标记对应能力不支持，改为 stateless 完整回放 |
| compact unsupported | 使用本地摘要 fallback |
| timeout/429/5xx | 走普通退避/候选模型故障切换，不修改能力 |
| 已产生可见 token 后失败 | 不切换模型、不拼接第二份回答，直接报告流失败 |

每次逻辑请求最多允许一次“清 anchor 后完整回放”。重试上下文携带
`continuation_recovery_attempted=True`，从代码结构上阻止循环。

## 7. 上下文变动语义

引入单调递增的 `history_revision`。普通尾部追加不增加 revision；任何非 append 变更都增加 revision
并清除 head anchor。

| 操作 | canonical history | anchor | 下一请求 |
| --- | --- | --- | --- |
| 新 user 消息 | 尾部追加 | 保留并校验 | 通常 delta |
| tool result | 尾部追加 | 保留并校验 | 通常 delta |
| 改写旧 user 消息 | 重建有效历史，revision +1 | 清除 | 完整回放 |
| 删除/截断/回退 | 重建有效前缀，revision +1 | 清除 | 完整回放 |
| 创建分支 | 复制 canonical 前缀到新 session | 不复制 anchor | 子分支首次完整回放 |
| 切 provider/Base URL/model | 历史保留；过滤不兼容原生 item | 清除 | 对新 issuer 完整回放 |
| tools/instructions/reasoning 变化 | 历史不变 | shape 校验失败 | 完整回放 |
| 本地摘要压缩 | 用 summary checkpoint 替换旧范围，revision +1 | 清除 | 完整回放 |
| 官方 compact | 安装绑定当前 generation/前缀的 transport checkpoint | 不复用旧 anchor | 首次发送压缩后历史，成功后建立新 anchor |

分支即使复制了 assistant 的 `canonical_output_items`，也不得复制 server continuation anchor。这样子分支仍能
无状态回放准确历史，但不会连接到父分支的服务端未来。

现有 Runtime V2 操作应由 `RuntimeProjector` 根据事件语义派生单调的
`model_history_generation`，不由页面、handler 或传输层手工删除
`_myagent_responses`。只有模型可见历史的非追加变化才递增 generation；普通尾部追加以及不改变
模型输入的统计/摘要元数据事件不递增。anchor 通过 generation 不匹配自然失效。

Responses 原生 output item 随 `assistant_final_committed` 事件原子落盘，属于事实；
head anchor 存在于可重建 snapshot，属于可丢弃缓存。分支投影复制 canonical output，
但必须剔除父会话 anchor、response ID 和能力探测结论。

## 8. Compaction 设计

### 8.1 官方 OpenAI compact

当能力表确认 `/responses/compact` 可用时：

1. 以当前完整 canonical input、instructions、model、prompt cache key 调用 compact；
2. 验证返回 object 和 output item 结构；
3. 要求返回可用的 compaction item；
4. 将 compact output 作为新的 canonical history checkpoint；
5. 保留必要的当前 user/tool 尾部，边界不得切断 function call/result 对；
6. checkpoint 绑定源 generation 和 canonical 前缀；逻辑历史不被改写，因此不人为增加 generation；
7. 下一次发送压缩后的 canonical items，成功后建立新 anchor；任意后续非追加历史变化会清除 checkpoint。

官方接口返回的是用户消息加 opaque compaction item，不应把 `encrypted_content` 转成普通文字，也不应让
UI 编辑它。

### 8.2 本地 fallback

代理不支持 compact 时，继续使用现有本地摘要/截尾策略，并统一通过 Runtime V2
`model_history_replaced` 表达：

- 保存 summary 文本和替换后的模型历史；
- 不保留被改写 assistant message 上已经过时的 provider replay metadata；
- 压缩边界必须保持 tool call/result 配对；
- 操作失败时不修改历史；
- 成功后 revision +1 并清 anchor。

本地摘要不伪装成官方 `compaction` item，避免发送代理无法理解的虚假协议对象。

## 9. Prompt cache

采用 Codex 的 session-scoped 思路：主会话使用稳定的 session ID 或 lineage cache ID 作为
`prompt_cache_key`，不要按每轮完整内容重新计算导致 key 抖动。

- 普通对话整个 session 稳定；
- 分支可以继承 lineage cache ID，以复用共同前缀缓存；
- provider/model/静态工具前缀发生根本变化时生成新命名空间；
- Judge、标题、摘要等一次性请求使用独立用途前缀，不能污染主对话 continuation state。

是否真正命中缓存只通过 usage 中 cached token 观测，不把缓存命中与正确性绑定。

## 10. Provider 选择与配置

`EXECUTOR_LLM_TYPE` 继续只决定线协议：

| 值 | 协议 |
| --- | --- |
| `auto` | 官方 OpenAI -> Responses；官方 Anthropic -> Messages；其他 -> OpenAI-compatible |
| `openai` / `@ai-sdk/openai` | Responses |
| `openai-compatible` / `@ai-sdk/openai-compatible` | Chat Completions |
| `anthropic` / `@ai-sdk/anthropic` | Anthropic Messages |

Responses continuation 不再作为同级用户配置。现有 `responses_state_mode` 的迁移策略：

- `auto` 或空值：使用新自动算法；
- `stateless`：过渡期映射为“禁止服务端存储”，作为隐私/诊断选项；
- `stateful`：迁移为新自动算法，不再具有强制语义；
- 前端删除普通用户的 stateful/stateless 选择，只保留需要时的“禁止服务端存储”隐私开关；
- 后端暂时接受旧字段以完成迁移，但不会让它绕过安全校验。

Goal Judge、标题、摘要等单次调用固定不创建或修改主会话 anchor。它们仍通过同一个 provider adapter，
但使用独立 `LLMRequestPurpose` 和 stateless 请求。

## 11. 流式事件约束

状态重构不能破坏现有工具流修复。`responses/stream.py` 继续采用“增量优先、完成快照补全”：

- `response.output_item.added` 可先建立 tool item；
- arguments delta 可以早于或晚于函数名和 `call_id`；
- `response.output_item.done` 和 `response.completed.output` 必须补全元数据；
- 首 token 状态不得阻止完整 item 元数据落盘；
- 相同 snapshot 只补缺失后缀，不重复正文或 arguments；
- 只有 `response.completed/incomplete` 后才能发出最终 provider state；
- failed/cancelled 流保留诊断数据，但不安装 continuation anchor。

流聚合器只负责恢复完整 output items；是否续链由 `responses/state.py` 决定，二者不得相互读取临时布尔状态。

## 12. 可观测性

每轮记录但不向模型暴露：

- `responses_mode`: `full_store`、`previous_id_delta`、`stateless_replay`、后续的 `websocket_delta`；
- `full_replay_reason`: `no_anchor`、`revision_changed`、`prefix_mismatch`、
  `request_shape_changed`、`issuer_changed`、`anchor_expired`、`storage_disabled`；
- request item count、suffix item count、request bytes；
- response ID 是否安装为 anchor；
- cached input tokens；
- continuation recovery 次数；
- compact implementation：`openai` 或 `local_summary`。

日志禁止记录 encrypted reasoning、API key 和完整用户正文。调试 hash 使用截断摘要。

## 13. 测试矩阵

### 13.1 状态算法单元测试

- 首轮无 anchor，完整请求并建立 anchor；
- 普通第二轮只发送新增 user item；
- 工具调用后只发送 function result 和后续新增项；
- instructions/tools/reasoning/text 任一变化均完整回放；
- 历史中间内容、role、call ID 或 item 顺序变化均完整回放；
- 相同 hash 但结构不同时拒绝续链；
- 旧 schema response ID 不参与 continuation；
- provider/model/Base URL 改变时不复用 ID 或 encrypted reasoning；
- expired ID 只重试一次且不会选中更老 ID；
- incomplete/failed/cancelled 响应的 anchor 安装规则正确。

### 13.2 上下文操作集成测试

- 改写、删除、截断、回退后 revision 增加并完整回放；
- 分支复制有效历史但没有父 anchor；
- 分支首次完整回放后建立自己的 anchor；
- 官方 compact 安装 opaque item 并清 anchor；
- 本地 compact 不保留被替换消息的陈旧 provider metadata；
- 压缩和回退都不拆散 function call/result；
- 会话重启后：有效 stored anchor 可继续，失效 anchor 自动完整恢复；
- 周一到周五的服务端状态过期模拟不会形成重试循环。

### 13.3 流协议回归测试

- 参数 delta 先到、函数名和 call ID 后到；
- 只有 output item done，没有 added；
- 只有 response.completed 快照；
- added/delta/done/completed 全部出现但不重复；
- 多个并行工具调用乱序到达；
- 首个可见 token 后工具元数据仍完整；
- provider failover 只发生在任何可见输出之前。

### 13.4 三 provider 合同测试

- `@ai-sdk/openai` 语义对应 Responses；
- `@ai-sdk/openai-compatible` 不接收 `_myagent_responses` 内部字段；
- `@ai-sdk/anthropic` 正确转换 tool use/result 和 system；
- auto/manual provider 选择保持兼容；
- Judge 不读写主会话 continuation anchor。

## 14. 实施顺序

### 阶段 A：冻结行为与拆包

1. 给当前流式工具调用修复补齐回归测试。
2. 提取 `types.py`、`provider.py` 和三个 provider adapter。
3. 保持 `app/llm/__init__.py` 旧导出兼容，避免一次修改所有调用方。

验收：除明确标记的 Responses 状态测试外，现有测试结果不变。

### 阶段 B：建立 canonical replay

1. 实现 `CanonicalResponseItem` 和双向转换。
2. 所有 Responses 请求先能用 `store=false` 完整回放。
3. 加入 encrypted reasoning issuer 隔离和 item ID wire 清理。
4. 把完整 output items 与可丢弃 anchor 分开落盘。

验收：关闭 continuation 后，多轮文本、工具和 reasoning 均可正确运行。

### 阶段 C：严格 continuation

1. 实现 RequestShape、ContinuationAnchor 和前缀比较。
2. 删除 `_matching_previous_response()` 的历史回扫策略。
3. 实现官方 OpenAI `store=true + previous_response_id` 自动路径。
4. 实现一次性失效恢复和结构化能力缓存。

验收：纯追加对话发送 delta；所有变更场景自动完整回放。

### 阶段 D：联动上下文操作

1. 在 Runtime V2/legacy 统一历史修改入口增加 `history_revision`。
2. 接入改写、删除、截断、回退、分支和 provider 切换。
3. 迁移旧 `_myagent_responses`：只保留 output replay，不继承旧 anchor。

验收：历史操作测试和跨重启测试全部通过。

### 阶段 E：Compaction

1. 已实现 `/responses/compact` 能力探测与官方路径。
2. 已将现有本地摘要明确限制为 Runtime V2 model-history replacement fallback。
3. 已复用既有压缩边界/工具配对校验，并在替换入口统一剥离旧 anchor。

验收：官方与代理两条压缩路径均能在下一轮建立干净的新 anchor。

### 阶段 F：配置和文档收口

1. 前端移除普通 stateful/stateless 选择。
2. 保留“禁止服务端存储”隐私开关。
3. 更新 `docs/llm-transport.md`，删除“auto 默认盲探测 stateful”的旧描述。
4. 增加迁移日志和可观测指标说明。

## 15. 完成标准

满足以下条件才算重构完成：

- 当前本地历史始终可以独立完整回放；
- 没有任何代码通过“最近 response ID”猜测上下文；
- 增量发送必须经过 request shape 和 canonical prefix 双重校验；
- 所有非 append 历史操作都有统一 revision/invalidation 语义；
- response ID 过期只触发一次完整恢复；
- tool name、call ID、arguments 和原生 output items 在所有流事件顺序下完整；
- OpenAI、OpenAI-compatible、Anthropic 三种 provider 合同测试通过；
- Goal Judge 与主对话状态解耦；
- 官方 compact 与本地 fallback 都有端到端测试；
- 用户日常无需理解或手动选择 stateful/stateless。

## 16. 官方协议依据

- Responses `previous_response_id` 用于多轮上下文，但与其一起使用时，上一轮 instructions 不会自动继承，
  因此本方案要求每轮重发 instructions。
- `store=false` 时可通过 `reasoning.encrypted_content` 回放 reasoning item，因此完整无状态请求可以作为
  正确性基线。
- `/responses/compact` 返回 compacted output，其中包含用户消息和一个 opaque compaction item；本方案不把
  它降级成普通文本摘要。

参考：

- <https://developers.openai.com/api/reference/cli/resources/responses/methods/create>
- <https://developers.openai.com/api/reference/java/resources/responses/methods/compact>
