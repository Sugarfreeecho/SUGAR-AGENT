# 审批闸口、卡片与人工问答 · 功能方案设计（UseCase 清单）

- 版本：2026-09-13（覆盖至：HEAD `6acc6bf`）
- 用途：逐条审查（四字段格式）。
- 适用实现：`app/tool_approval_gate.py`（352 行）、`human_interaction/service.py`、approvals/interactions API。
- 上级：`00-权限审批整体设计.md`

---

## 1. 功能定位

"人机握手"的运行时：等待、决议、取消、恢复——以及 ask_user 问答通道。

## 2. UseCase

### UC-7E1 等待与超时
- **触发**：工具进入待批状态。
- **预期现象**：run 在闸口**挂起等待**（不失败、不空转）；等待时长可配置；超时按策略收尾（拒绝并说明）。
- **依据**：`approval_wait_seconds / wait_tool_ui_approval_after_emit`。

### UC-7E2 决议落地
- **触发**：用户/复核给出结论。
- **预期现象**：决议原子落地（resolve_tool_approval / resolve_tool_approval_decision）；工具随决议继续/收尾；重复决议幂等（以后到为准或拒绝重复）。
- **依据**：`resolve_tool_approval / resolve_tool_approval_decision`。

### UC-7E3 批量拒绝与中断
- **触发**：会话被中断/清理时有多个待批。
- **预期现象**：全部被标记拒绝、无悬挂；相关工具调用以"用户未批准"收尾；等待者被正确唤醒（中断轮询）。
- **依据**：`reject_pending_approvals_for_sessions / _interrupt_poll_until_done`。

### UC-7E4 待批列表与实时性
- **触发**：查看待批。
- **预期现象**：列表实时（事件驱动）；多会话各自独立；已决议的从待批移除。
- **依据**：`list_pending_approvals / has_live_approval_waiter / get_live_approval_review_context`。

### UC-7E5 手动审批卡片流程
- **触发**：非自动场景的人工卡片。
- **预期现象**：卡片含工具预览与风险说明；批准/拒绝/分析三路可行；持久化失败有明确错误（不丢决议）。
- **依据**：`ApprovalPersistenceError`、审批卡片 API（../05-WebUI对话界面/05）。

### UC-7E6 ask_user 问答
- **触发**：模型发起人工提问。
- **预期现象**：问题卡出现（含选项）；回答回填模型继续；取消返回"已取消"；应用重启后未答问题可恢复（后台恢复任务）。
- **依据**：`human_interaction/service.py`、`_run_human_interaction_recovery_background`。

## 3. 边界

- 卡片 UI 细节见 ../05-WebUI对话界面/05；本篇管闸口语义。
- ask_user 与审批是**两套卡片**但同一"人在回路"承诺：都不丢、都可取消、都可恢复。

## 4. 依据映射

见上表（gate + human_interaction）。

## 5. 版本记录

- 2026-09-13 v1：拆分首版（承接 UC-706~708/711）。
