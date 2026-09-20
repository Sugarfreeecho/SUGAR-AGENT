# 提示装配与静态段缓存 · 功能方案设计（UseCase 清单）

- 版本：2026-09-20 v4（覆盖至：当前工作区）
- 用途：逐条审查（四字段格式）。
- 适用实现：`app/agent_loop.py`（静态段构建与重建）、`app/agent_tokenizer.py`（分词/缓存/估算）。
- 上级：`00-ReAct运行时整体设计.md`

---

## 1. 功能定位

决定"模型每轮到底看到了什么"：系统提示、环境信息、技能目录、工具清单——以及它们的**缓存策略**。

## 2. UseCase

### UC-2B1 系统提示多段装配
- **触发**：每轮请求前构建输入。
- **预期现象**：提示由多段组成（prompt.md + 环境/路径模型 + 插件与技能目录 + 工具清单等），内容完整可复现；用户不可见但可通过调试信息检查。
- **规则与边界**：段拼接顺序稳定（对前缀缓存友好）；环境信息中的动态值不破坏整段缓存。Core 允许这些来源继续形成多条、甚至后置的 system；目标模型要求的“开头唯一一条”等形状由 LLM 接入层按实际候选投影，见 `../01-LLM接入/09-SystemPrompt能力投影与Qwen兼容方案设计-UseCase清单.md`。
- **依据**：`_build_static_segments_for_session`、`agent_tokenizer.build_static_system_segments / build_env_static`。

### UC-2B2 静态段进程级缓存
- **触发**：连续多轮 / 多会话。
- **预期现象**：提示静态部分不重复重算（响应更快）；技能/插件/工具变更后**最多滞后一次请求**生效。
- **规则与边界**：重建在后台调度（`_schedule_static_segments_rebuild`），不阻塞当前请求；缓存失效由签名驱动。
- **依据**：`_build_static_segments_for_session` + generation 修订、`_skills_tree_signature`。

### UC-2B3 分词与估算
- **触发**：需要判断"输入多大"（压缩判断、界面显示）。
- **预期现象**：估算与实际用量偏差可控；显示为"上下文 xx%"类提示；追加历史时，思考剥离、消息哈希、扁平文本和真实分词都只处理新增尾部，同一消息序列精确命中时不重复工作。
- **规则与边界**：`strip_reasoning_for_api_request()` 与 tokenizer 缓存都按最长对象身份前缀复用；缓存保存对象引用并用 `is` 比较，避免对象 id 回收复用造成误命中。扁平文本使用精确层 O(1) 命中；估算失败回退字/字符系数法（不阻断）；prompt-usage 基线来自真实用量（回写）。
- **依据**：`strip_reasoning_for_api_request / _messages_token_hashes / _flatten_messages_incremental / _seed_flatten_token_cache / count_message_tokens_incremental / estimate_full_input_tokens_for_messages`。

### UC-2B4 历史消息规整
- **触发**：把会话历史转成模型消息。
- **预期现象**：工具消息成对完整（无"孤儿工具结果"）；给模型的序列合法（端点不会 400）。
- **依据**：`inject_missing_tool_messages / messages_for_openai_turns`。

### UC-2B5 tokenizer 启动预热
- **触发**：WebUI 生命周期启动。
- **预期现象**：在后台线程加载仓库 tokenizer 并执行一次极小 encode，使首个真实请求不再承担 tokenizer.json 解析；缺少依赖或词表时维持原有字符/4回退。
- **规则与边界**：`_TOKENIZER_LOAD_LOCK` 串行化后台预热与首个在线请求，保证只解析一次；预热失败不阻断服务启动。
- **依据**：`agent_tokenizer.warm_tokenizer / _get_tokenizer`、`webui.start_webui_lifecycle::_warm_tokenizer_task`。

### UC-2B6 本地 token 估算诊断旁路
- **触发**：性能诊断时显式设置 `CONTEXT_TOKEN_SKIP_LOCAL_ESTIMATE=1`。
- **预期现象**：`estimate_full_input_tokens_for_messages` 在入口直接复用 provider 上次上报计数，用来隔离本地分词对轮间耗时的影响。
- **规则与边界**：该开关只用于测量，默认必须关闭；启用后缺少当前本地估算，可能削弱上下文压缩 gate 的准确性，不得作为生产优化常态。
- **依据**：`agent_tokenizer.estimate_full_input_tokens_for_messages` 的 `CONTEXT_TOKEN_SKIP_LOCAL_ESTIMATE` 分支。

## 3. 边界

- 每轮输入的**可变部分**（新用户消息、压缩摘要）不入静态缓存。
- 本模块负责语义装配，不以 Qwen 等单一模型的 wire 限制重写 Core 历史；协议形状归 LLM 接入层。
- 上下文占用显示属观测（见 08/../09-横切能力/04）。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-2B1/2B2 | `_build_static_segments_for_session`、`_schedule_static_segments_rebuild` |
| UC-2B3 | `strip_reasoning_for_api_request`、`agent_tokenizer.py` 的哈希/扁平文本/增量分词与 prompt-usage 缓存 |
| UC-2B4 | `inject_missing_tool_messages`、`messages_for_openai_turns` |
| UC-2B5 | `agent_tokenizer.warm_tokenizer`、`webui.start_webui_lifecycle` |
| UC-2B6 | `estimate_full_input_tokens_for_messages` 入口诊断分支 |

## 5. 版本记录

- 2026-09-20 v4：明确“Core 多段 system 装配”和“候选模型 wire 能力投影”的边界，链接 Qwen 首部唯一 system 专项设计。
- 2026-09-20 v3：补入只用于性能归因的本地 token 估算旁路开关及生产边界。
- 2026-09-20 v2：补充消息哈希/扁平文本/精确分词的增量缓存，以及 tokenizer 后台预热和并发加载锁。
- 2026-09-13 v1：拆分首版。
