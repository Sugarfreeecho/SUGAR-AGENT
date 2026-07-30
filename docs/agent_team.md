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
- `shutdown`、`complete_shutdown`、`archive`：显式结束团队生命周期。

根 Agent 是 `lead`。只有 lead 可创建/归档团队、创建和派工成员、移除成员以及关停。成员身份取自子会话 metadata，不能通过工具参数冒充其他成员。

## 持久成员语义

`spawn_member` 调用现有 `SessionManager.create_subagent_session` 创建一个 child session，并在 metadata 中记录：

- `agent_team_root_session_id`
- `agent_team_member_id`
- `agent_team_role`
- `agent_team_prompt`

每次 `dispatch` 都对这个 child session 执行 `task(action="resume")`。前台执行完成后成员回到 `idle`；后台执行由监视任务在结束后回收状态。

## 自动认领与连续调度

默认启用本地自动调度器（可用 `AGENT_TEAM_AUTO_SCHEDULE=0` 关闭）。调度器只为
`idle`/`starting` 且没有 in-progress 任务的成员认领任务，并要求所有 `depends_on`
任务已经 completed。候选任务按 `urgent > high > normal > low`、创建顺序和 task id
稳定排序。

创建任务、更新依赖任务为 completed、成员完成执行，以及后台活动 Team 扫描都会触发
下一轮原子 claim 与 dispatch。进程重启后，持久化的 pending 任务可被重新唤醒。
lead 也可显式调用 `team(action="auto_schedule")`。

## 并发与权限

任务认领和所有 Team 事件提交都在根会话的 `SessionEventLog.session_transaction` 内完成。两个成员同时认领同一任务时只有一个会成功。

首版共享同一工作区。为降低文件冲突，配置在 `AGENT_TEAM_SERIAL_WRITE_TOOLS` 中的工具使用每个根团队一把进程内写锁。成员和普通 subagent 与主 Agent 使用同一套权限与用户审批路径，不会因 Team 身份额外请求 lead 放行。

## HTTP API 与 Web UI

功能状态：

- `GET /api/features/agent-team`
- `POST /api/features/agent-team`，JSON 为 `{"enabled": true|false}`

团队控制面以 `/api/agent-team/{session_id}` 为根，提供团队、成员、任务、邮箱、关停和归档路由。关闭时统一返回 HTTP 403 和 `code=feature_disabled`；校验、未找到和并发冲突分别返回 400、404、409。

主设置页的“管理当前会话团队”可查看 roster 和共享任务，可创建团队/任务以及执行关停和归档。

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
