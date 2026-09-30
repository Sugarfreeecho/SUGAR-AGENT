# 注册表与描述符 · 功能方案设计（UseCase 清单）

- 版本：2026-09-30 v2（覆盖至：当前工作区；目录版本检查的本地拆分诊断）
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
- **依据**：`agent_loop.py::_combined_tool_registry_revision`、`host_tool_registry.py::HostToolRegistry.catalog_revision`；`tests/test_tool_registry.py`；复测数值与未验证项见 [09/05](../09-横切能力/05-性能优化基线与已完成项方案设计-UseCase清单.md)。

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
| UC-3A5 | `_combined_tool_registry_revision`、`HostToolRegistry.catalog_revision` |

## 5. 版本记录

- 2026-09-30 v2：新增 UC-3A5，补录 registry 来源拆分、host 墙钟/CPU 与排序/动态回调明细；未把既有 MCP 缓存或新 TTL 当作本批优化。
- 2026-09-13 v1：拆分首版（承接原 UC-301/302）。
