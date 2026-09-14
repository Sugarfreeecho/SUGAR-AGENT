# 注册表与描述符 · 功能方案设计（UseCase 清单）

- 版本：2026-09-13（覆盖至：HEAD `d022831`）
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

## 5. 版本记录

- 2026-09-13 v1：拆分首版（承接原 UC-301/302）。
