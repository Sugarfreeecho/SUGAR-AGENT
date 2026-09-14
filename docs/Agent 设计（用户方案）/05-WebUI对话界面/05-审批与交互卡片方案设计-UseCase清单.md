# 审批与交互卡片 · 功能方案设计（UseCase 清单）

- 版本：2026-09-14 v2（覆盖至：HEAD `d022831`）
- 用途：逐条审查（四字段格式）。
- 适用实现：`modules/human-interactions.js`、`modules/permissions.js`、后端 approvals/interactions API。
- 上级：`00-WebUI对话界面整体设计.md`

---

## 1. 功能定位

"需要人拍板"的两类卡片：工具审批卡（做不做）与问答卡（问什么答什么）。

## 2. UseCase

### UC-5E1 审批卡片出现
- **触发**：工具调用被判定需人工批准。
- **预期现象**：卡片出现（工具名、命令/参数预览、批准/拒绝按钮）；多个待批可并列处理；卡片与具体工具调用一一对应。
- **依据**：`human-interactions.js`、`_emit_tool_approval_required_sse`。

### UC-5E2 批准 / 拒绝
- **触发**：点击批准或拒绝。
- **预期现象**：提交后按钮进入处理态→卡片状态更新（已批准/已拒绝）；工具随决议执行或收尾（结果为"用户未批准"）；重复点击幂等。
- **依据**：`resolve_session_approval / post_tool_approval`、`tool_approval_gate`。

### UC-5E3 审批分析入口
- **触发**：点击"分析"按钮。
- **预期现象**：卡片给出结构化分析（风险/影响），辅助决策；分析失败不影响批准/拒绝。
- **依据**：`analyze_session_approval`（+ reviewer 联动）。

### UC-5E4 ask_user 问答卡
- **触发**：模型发起 ask_user。
- **预期现象**：问题与选项清晰呈现；提交后模型继续；可取消（模型收到"已取消"结果）。
- **规则与边界**：应用重启后未答问题**可恢复**（后台恢复任务）；同一会话可同时存在多个问答与多个审批（不互相吞没）。
- **依据**：`_run_human_interaction_recovery_background`、interactions API。

### UC-5E5 权限设置面板联动
- **触发**：卡片上切换到"完全访问/请求批准/替我审批"，或在设置面板修改。
- **预期现象**：模式变更**即时广播**（permission_mode_changed），后续行为立即变化；面板状态同步。
- **依据**：`permissions.js`、`set_session_permissions`。

## 3. 边界

- 策略与模式语义见 ../07-权限审批/01–03；
- 审批等待对运行的影响（挂起而非失败）见 ../07/05。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-5E1/5E2 | `human-interactions.js`、approvals API |
| UC-5E3 | `analyze_session_approval` |
| UC-5E4 | interaction 恢复段（webui L789–938） |
| UC-5E5 | `set_session_permissions` L3517 |

## 5. 版本记录

- 2026-09-14 v2：修正 `set_session_permissions` 行号（webui.py L3517）并更新版本线至 `d022831`。
- 2026-09-13 v1：拆分首版（承接 UC-508）。
