# 注册表与描述符 · 功能方案设计（UseCase 清单）

- 版本：2026-11-02 v3（工具schema计数按内容复用与披露线程执行）
- 用途：逐条审查（四字段格式）。
- 适用实现：`app/tool_registry.py`（361 行）、`app/agent_tools.py`（schema 构造）、组合注册表逻辑。
- 上级：`00-工具系统整体设计.md`

---

## 1. 功能定位

"工具目录"的形成与维护：谁注册、同名怎么办、描述符承载哪些行为特征。

## 2. UseCase

### UC-3A1 组合注册表
- **触发**：构建模型请求的工具表。
- **预期现象**：内置 + 宿主 + 插件 + MCP 工具合并；会话侧看到一致的工具清单；来源变更后自动刷新。
- **规则与边界**：同名冲突**拒绝**（DuplicateToolError）而非覆盖；不可用工具（unavailable）保留占位但不可执行。
- **依据**：`tool_registry.ToolRegistry`、`build_combined_tool_registry_for_session / _combined_tool_registry_revision`。

### UC-3A2 描述符行为特征
- **触发**：调度任意工具。
- **预期现象**：行为与描述符一致——只读工具可并行、写类串行；压力受限/可交互工具走特殊通道；可中断性被调度器尊重。
- **规则与边界**：特征由来源提供（host/plugin/mcp），宿主侧有默认值（`plugin_tool_policy`）；不合法声明（如 unavailable 却 executable）在注册时被拒。
- **依据**：`ToolDescriptor.from_openai_definition`（invocation_kind/effect/required_permissions/parallel_safe/pressure_limited/interactive/early_stream_safe/interruptibility）。

### UC-3A3 结局契约
- **触发**：工具执行结束（或挂起）。
- **预期现象**：统一为四态之一：completed / failed / **deferred** / **interaction**——界面（等待中/成功/失败/待回答）与之一一对应。
- **依据**：`ToolOutcomeKind / ToolOutcome`。

### UC-3A4 宿主工具桥
- **触发**：宿主服务类工具（如 ask_user/context_manage）被调用。
- **预期现象**：经 `host_tool_invokers` 边界执行——能力逻辑不进主循环，授权边界保持；失败以统一结局返回。
- **依据**：`host_tool_registry.py`、`builtin_host_tools.py`。

### UC-3A5 目录版本检查可定位到实际来源

- **触发**：请求前组合注册表修订检查耗时升高。
- **预期现象**：`tool_registry_revision_detail` 区分 MCP、session shape、extension、host、executor；host 另记线程 CPU。`host_catalog_revision_timing` 在 ≥50 ms 时记录 invoker 数量、排序、动态可用性回调累计耗时、最长回调名称/耗时及线程 CPU。
- **规则与边界**：墙钟远大于该线程 CPU 只能说明该线程未持续计算，不能直接认定 MCP、GIL、锁或 I/O 是原因；需同窗口调用栈/子段证据。已有 MCP 后台目录刷新与 stale-hit 保留；本批未给 host 动态可用性回调增加 TTL，也未改变注册表版本失效或可执行性语义。
- **依据**：`agent_loop.py::_combined_tool_registry_revision`、`host_tool_registry.py::HostToolInvokerRegistry.catalog_revision`；`tests/test_tool_registry.py`；复测数值与未验证项见 [09/05](../09-横切能力/05-性能优化基线与已完成项方案设计-UseCase清单.md)。

### UC-3A6 工具schema计数复用与披露不阻塞协调循环

- **触发**：主代理或子代理按当前权限与工具档案构建目录，披露阶段重建内容相同的工具定义列表。
- **预期现象**：保留原列表身份缓存，增加稳定 JSON 全文为键的计数缓存；不同列表但内容相同只编码一次。组合注册表等待 `asyncio.to_thread(tool_search.assemble, …)` 完成后再发布结果，期间协调循环可继续处理其他任务。
- **规则与边界**：只缓存派生 token 数与既有 SHA1 指纹，权限、来源、工具档案过滤仍实时执行；全文比较决定相等，摘要仅选择固定16把编码协调锁。内容缓存最多32项/4MiB（按UTF-8序列化字节计），超大schema绕过内容缓存与协调锁；原身份缓存仍保持32项及强引用防id复用。tokenizer对象、加载状态、计数函数或编码失败代次变化使两级缓存失效；临时编码失败的字符估算不进入schema缓存，下一次允许重试。固定指纹格式不变，避免破坏落盘基线。工作线程仅计算私有目录，取消可丢弃结果，不异步推迟任何模型事实或授权检查。
- **依据**：`agent_tokenizer._tool_schema_cache_values / count_text_tokens`、`agent_loop.build_combined_tool_registry_for_session`；`tests/test_tool_schema_content_cache.py`（重建、变更、并发、容量、tokenizer切换、临时失败）、`tests/test_tool_disclosure_off_loop.py`（等待及取消）、工具搜索/权限回归；收益与限制见[11-02报告](../../performance/subagent-heartbeat-and-schema-cache-2026-11-02.md)。

## 3. 边界

- 描述符不包含"实现"：可执行性由来源保证（插件被停用 → unavailable）。
- 修订号（revision）用于缓存失效，不影响工具语义。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-3A1 | `tool_registry.py` L153–235 |
| UC-3A2 | L53–152 |
| UC-3A3 | L236+ |
| UC-3A4 | `host_tool_registry.py`、`builtin_host_tools.py` |
| UC-3A5 | `_combined_tool_registry_revision`、`HostToolInvokerRegistry.catalog_revision` |
| UC-3A6 | `_tool_schema_cache_values`、`build_combined_tool_registry_for_session` |

## 5. 版本记录

- 2026-11-02 v3：新增 UC-3A6，记录32项/4MiB内容计数缓存、单次并发编码、失败失效及披露等待式线程执行；权限和模型事实边界保留。
- 2026-09-30 v2：新增 UC-3A5，补录 registry 来源拆分、host 墙钟/CPU 与排序/动态回调明细；未把既有 MCP 缓存或新 TTL 当作本批优化。
- 2026-09-13 v1：拆分首版（承接原 UC-301/302）。
