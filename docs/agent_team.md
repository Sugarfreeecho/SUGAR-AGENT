# Agent Team 使用与实现说明

Agent Team 是构建在现有 `task`/subagent 和 Runtime V2 之上的实验性团队控制面。它默认关闭；关闭状态不会改变现有 subagent 工具和会话行为。

## 启用与关闭

在主界面设置中选择“Agent Team（实验功能）→ 启用”，或者写入：

```dotenv
AGENT_TEAM_ENABLED=1
```

保存后立即生效，无需重启。关闭可设为 `0`；未配置、空值或未知值均按关闭处理。运行中关闭后，Team API、`team` 工具和成员的普通工具调用都会 fail closed；已写入的 Runtime V2 团队事件不会被删除，重新启用后可恢复投影。

可选限制：

```dotenv
AGENT_TEAM_MAX_MEMBERS=4
AGENT_TEAM_MAX_TASKS=1000
AGENT_TEAM_MAX_MESSAGES=2000
AGENT_TEAM_MAX_PERMISSIONS=500
AGENT_TEAM_MAX_MESSAGE_CHARS=32000
AGENT_TEAM_SERIAL_WRITE_TOOLS=write_file,apply_patch,edit_file,delete_file,run_shell,web_download
AGENT_TEAM_PERMISSION_TOOLS=delete_file,web_download
```

无效的数值限制会回退到安全默认值。

## Agent 工具

功能启用后，根 Agent 和已绑定的团队成员会获得一个多动作 `team` 工具。普通 subagent 不会看到该工具。

主要动作：

- `create`、`status`：创建或读取当前根会话的唯一团队。
- `spawn_member`：创建 roster 成员和持久 subagent 会话，并绑定成员身份。
- `dispatch`：通过现有 subagent `resume` 唤醒同一个成员会话；可关联共享任务。
- `create_task`、`claim_task`、`release_task`、`update_task`：维护共享任务与唯一 assignee。
- `send_message`、`read_inbox`、`consume_message`：使用持久邮箱协调。
- `request_permission`、`resolve_permission`：申请和处理一次性高风险工具授权。
- `shutdown`、`complete_shutdown`、`archive`：显式结束团队生命周期。

根 Agent 是 `lead`。只有 lead 可创建/归档团队、创建和派工成员、移除成员、审批权限以及关停。成员身份取自子会话 metadata，不能通过工具参数冒充其他成员。

## 持久成员语义

`spawn_member` 调用现有 `SessionManager.create_subagent_session` 创建一个 child session，并在 metadata 中记录：

- `agent_team_root_session_id`
- `agent_team_member_id`
- `agent_team_role`
- `agent_team_prompt`

每次 `dispatch` 都对这个 child session 执行 `task(action="resume")`。前台执行完成后成员回到 `idle`；后台执行由监视任务在结束后回收状态。如果成员因权限停止，则保持 `waiting_permission`，直到 lead 审批并再次派工。

## 并发与权限

任务认领、权限消费以及所有 Team 事件提交都在根会话的 `SessionEventLog.session_transaction` 内完成。两个成员同时认领同一任务时只有一个会成功。

首版共享同一工作区。为降低文件冲突，配置在 `AGENT_TEAM_SERIAL_WRITE_TOOLS` 中的工具使用每个根团队一把进程内写锁。默认高风险工具为删除和下载；`run_shell(restrict_to_workspace=false)` 也始终需要授权。

授权是一次性的：

1. 成员尝试受保护工具，运行时拒绝并将成员置为 `waiting_permission`。
2. 成员调用 `request_permission`，说明 action、resource 和原因，然后把控制权交还 lead。
3. lead 通过 `resolve_permission(decision="allowed")` 或 Web 面板“允许一次”审批。
4. lead 再次派工；匹配的权限在工具执行前原子变为 `consumed`，不可重复使用。

## HTTP API 与 Web UI

功能状态：

- `GET /api/features/agent-team`
- `POST /api/features/agent-team`，JSON 为 `{"enabled": true|false}`

团队控制面以 `/api/agent-team/{session_id}` 为根，提供团队、成员、任务、邮箱、权限、关停和归档路由。关闭时统一返回 HTTP 403 和 `code=feature_disabled`；校验、未找到和并发冲突分别返回 400、404、409。

主设置页的“管理当前会话团队”可查看 roster、共享任务和权限请求，可创建团队/任务、允许或拒绝权限以及执行关停和归档。

## 持久化

团队事实写在根会话 `events.jsonl`，事件类型以 `team_` 开头。`snapshot.json` 中的 `team` 只是可重建投影，包含：

- `members`
- `tasks`
- `messages` 与逐收件人 delivery
- `permissions`
- 团队状态和生命周期时间戳

投影版本已升级；旧快照会从事件日志自动重建。现有 `task` subagent 的事件和目录布局保持不变。

## 验证

仓库测试覆盖默认关闭、动态开关、API 错误映射、事件投影、重启恢复、并发任务认领、一次性权限竞争、持久成员会话复用、工具身份、共享写锁和 UI 接线。生产前端必须运行 `npm run build` 并通过 `scripts/check_frontend_dist_sync.py`。
