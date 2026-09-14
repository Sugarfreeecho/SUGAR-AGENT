# 执行策略、危险识别与自保护 · 功能方案设计（UseCase 清单）

- 版本：2026-09-13（覆盖至：HEAD `6acc6bf`）
- 用途：逐条审查（四字段格式）。
- 适用实现：`app/tool_execution_policy.py`、`app/agent_tools.py`（危险模式/自保护段 L445–670）。
- 上级：`00-工具系统整体设计.md`

---

## 1. 功能定位

每次工具调用的"安检门"：策略画像 + 危险识别 + 自保护 + 审批对接。

## 2. UseCase

### UC-3B1 执行策略画像
- **触发**：工具调度。
- **预期现象**：内置只读（read_file/ls/glob/grep/activate_skill）与网络只读（web_search/web_fetch）标记为并行安全、可中断；写类默认串行。
- **规则与边界**：策略是"默认值+声明合并"，插件可用 effect=read 提升并行度；错误声明不影响安全底线。
- **依据**：`tool_execution_policy.builtin_tool_policy / plugin_tool_policy`。

### UC-3B2 危险命令识别
- **触发**：`run_shell` 参数命中危险模式（如强制删除、系统级操作）。
- **预期现象**：被拦（或要求确认）并给出替代建议（如"改用 delete_file 软删除"）；提示可操作。
- **规则与边界**：区分"纯删除类"与"通用危险类"（`_has_non_delete_dangerous_pattern`），误伤率可控；识别不等于执行拒绝——最终按审批档位。
- **依据**：`_is_dangerous / _has_non_delete_dangerous_pattern / _dangerous_command_guidance`。

### UC-3B3 Agent 自保护
- **触发**：命令试图结束 Agent 自身进程、占用其端口、kill 生命周期脚本。
- **预期现象**：明确拒绝 + 指引（"请用托盘/agentctl 重启 Agent"）；**不会**把 Agent 弄崩或误杀。
- **规则与边界**：受保护进程 ID 集合动态计算（当前进程/父链/端口占用）；显式指定无关 PID 的终止仍允许（不过度拦截）。
- **依据**：`_agent_self_protection_reason / _agent_protected_process_ids / _agent_lifecycle_guidance`。

### UC-3B4 审批闸口对接
- **触发**：写类/外网类工具在受限模式下调用。
- **预期现象**：先显示"等待中"，随后弹卡（请求批准）/自动复核（替我审批）/直通（完全访问）；决议后继续。
- **依据**：`agent_loop`（`_emit_tool_pending_sse / _emit_tool_approval_required_sse / _tool_ui_approval_spec`）+ ../07-权限审批/05。

## 3. 边界

- 危险识别面内是"命令行文本特征"；脚本内部的动态行为不由本层负责（属沙箱/审批策略讨论范围）。
- 自保护白名单可通过环境变量调整（极端场景）——默认保守。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-3B1 | `tool_execution_policy.py`（52 行全文） |
| UC-3B2 | `agent_tools.py` L445–474 |
| UC-3B3 | L582–669 |
| UC-3B4 | `agent_loop.py` L3702–3809 |

## 5. 版本记录

- 2026-09-13 v1：拆分首版（承接 UC-303~305）。
