# 控制服务接入与接口迁移清单

## 模块所有权

| 文件 | 职责 |
| --- | --- |
| agent-session-control.py | 独立 cwd 的 CLI 引导 |
| app/session_control/cli.py、client.py | 参数、认证凭据、HTTP、等待、NDJSON、归档传输 |
| api.py | RPC、事件、登录/配对、Webhook、归档 HTTP 接口 |
| service.py、coordinator.py | 公共查询/命令服务、持久入箱消费、共享启动租约、运行结果对账 |
| public.py | 宿主插件客户端、后端事件循环桥、受限来源身份、业务绑定、执行观察及生命周期回调 |
| settings_api.py、notifications.py | 原生设置页的本机同源适配、时区解析及持久任务通知 |
| policy.py | 真实身份、任务范围、委派上限、撤销检查 |
| configuration.py、integration.py | Prompt/工具/参数解析、配置版本、每 turn 快照、执行边界与宿主集成 |
| store.py | 应用级 SQLite WAL，幂等请求、事件消费及提交回执 |
| scheduling.py、automation.py | 纯时间计算、规则验证、派发与执行分离、持久事件桥 |

事件采集和规则匹配按批次共享资源，设计与现有领域监听边界见 [事件监控资源复用](shared-event-monitor.md)。

## 公共协议

`POST /api/control/v1/rpc` 使用 Bearer 身份，JSON 请求：

```json
{"request_id":"trace-id","method":"session.send","idempotency_key":"business-key","params":{"session_id":"...","message":"继续","mode":"queue"}}
```

方法按 CLI 映射：session.read→session.history，stop→interrupt，config.set/reset→session.config.update，tools→tool_catalog，preset→config_preset，schedule/event→automation，event source→event_source，execution→operation（list→automation.history）。session.steer、session.notice、session.detach 也可供宿主适配器直接调用。session.unarchive 使用 session.archive + archived=false。更新配置/预设/任务时传 expected_revision；配置 update 是完整替换，任务 update 合并当前定义。

`GET /api/control/v1/events?session_id=...&cursor=...&generation=...` 为鉴权的 NDJSON；它与旧 UI SSE 共用 Runtime V2 事实，并不创建执行。传输 cursor 是当前会话 Runtime seq。RPC session.attach 仅返回观察快照；实际订阅使用 GET events。

`GET /api/control/v1/operations/{operation_id}/events?cursor=...` 按具体 operation 回放持久 NDJSON，末尾为 `operation.completed` 和该操作的终态回执。返回助手文本、工具进度及审批事件，不返回内部推理；工具大正文会截断。调用者须拥有该操作且仍有目标会话权限（管理员可查其他身份）。此游标独立于会话 Runtime 游标，渠道断线后可继续观察同一操作。

辅助接口：`POST /api/control/v1/auth/claim|pairings|logout`、`POST /api/control/v1/archives`、`GET /api/control/v1/archives/{export_operation_id}`、`POST /api/automation/v1/hooks/{source_id}`。归档上传使用 Idempotency-Key 头；下载仍需对导出会话有权限。

## 现有入口接入状态

| 原入口/模块 | 本次接入 | 保留状态与兼容边界 |
| --- | --- | --- |
| webui 的 /sessions、/chat、continue/recover | 新旧入口共用 SessionManager、Runtime V2 和 SessionExecutionCoordinator；未连接浏览器的 after_turn 追问由后端入箱接管 | 原 HTTP/SSE 格式不变；已有活跃 UI run 继续原流消费器 |
| 设置中心「定时任务」 | 本机同源适配转接公共服务，与 CLI 共用自动化定义、执行台账和运行配置 | 表单、通知策略、时区与恢复行为见 [设置页说明](schedule-settings.md)；不在浏览器调度 |
| remote_control gateway | 网关安装时转接公共 service.execute；device/approval/audit 转交原服务 | 原配对、审计、审批、WebSocket 格式保留；新 CLI 不依赖远控开关 |
| 飞书 | 公共传输代理提交 queue；message ID 去重；插件 SQLite 保存 operation、游标及待投递回复 | SDK 长连接仍由插件持有；投递失败退避重试，重连沿用原操作与回复去重标识；不依赖远控开关 |
| ACP | stdio 桥使用带身份的 RPC、持久 operation 流及精确取消；MCP 挂载独立鉴权和连接所有权 | 保留标准 ACP 协议与插件 MCP 连接；默认不向委派进程转交个人控制凭据 |
| Goal 续跑 | Goal runner 经公共客户端提交持久 continue；执行前重验目标，执行后对账实际 run | 目标、Judge、预算及退避继续属于 Goal；不再从 webui 私有函数启动 Runtime |
| 子 Agent、后台完成唤醒 | 完成事实提交持久 continue；同来源同会话合并尚未执行的唤醒，执行前检查事实仍待消费 | 子 Agent 注册表、后台进程/PTY 与完成事实仍由原服务持有；观察者退出不取消已接收执行 |
| Team、子 Agent 内部执行 | 继续通过共享租约和 Runtime 配置执行边界；子会话创建复制配置 | 团队状态、成员调度及内部运行注册表保留；未将成员任务改写为通用 automation |
| 插件后台批量运行 | sessions.run_many 一次事务接收 1–8 条输入，返回每条 operation_id；忙碌会话排队 | 保留宿主签发的一次性、精确会话集合授权；稳定业务 key 重试；停用只撤销该来源的操作 |
| B站 | 会话创建/Prompt 绑定、单轮工具限制、消息执行、私信追加/清理经公共 API；job 关联实际 operation/run | 原任务窗口、额度、账号、来信游标、发送 outbox 保留；结果不明不自动重跑，显式重试增加业务代次 |
| 历史/搜索/导入导出 | 公共服务调用已有分页、索引与归档实现；搜索在索引前过滤会话范围 | 历史查询不激活模型；管理员归档迁移沿用原校验 |
| system_context/工具目录 | 配置映射旧字段；原 UI 更新 Prompt 同步 runtime_config；过滤目录后再构建发现桥，执行边界再次校验 | 新规则叠加原 allow/deny、run scope、Hook、中央安全授权 |
| agentctl.py | 无需迁移 | 继续负责进程启停 |

上述已迁入入箱的渠道、插件及唤醒都有 operation 记录，可通过 execution 查询；业务投递是否成功仍查各插件的领域状态。历史 UI 执行、Team/子 Agent 内部任务不会补造 operation。通用 automation 与原业务触发器保持各自所有权；迁移触发职责时须同时关闭旧触发器，避免重复派发。

## 宿主插件接入

可信宿主适配器使用 `session_control.public.host_client`，指定稳定插件 ID、目标会话集合及最小能力：

```python
from session_control.public import host_client, stable_key

client = host_client("my-plugin", session_ids=[sid], capabilities=["session.send", "operation.cancel"])
receipt = await client.call("session.send", {"session_id": sid, "message": text},
                            key=stable_key("incoming", [account_id, incoming_id]))
async for event in client.observe(receipt["operation_id"]):
    if event["type"] == "operation.completed":
        save_result(event["operation"])
```

这是宿主 Python API，不能把来源身份、权限或 `_` 私有字段交给模型填写。普通插件/MCP 工具继续通过已授权的 host_actions 或宿主签发的任务令牌调用。公共 HTTP RPC 拒绝私有字段。

后端拥有唯一执行循环。插件异步代码使用 call/run/observe；同步工作线程可用 blocking，后端循环内调用 blocking 会拒绝。run 将旧工具名称解析为唯一来源 ToolRef，附加单轮预算及领域上下文；ensure_host_session 负责持久绑定与 Prompt 配置 CAS。业务 key 必须来自稳定触发事实，明确重新执行时使用新代次。

register_source_lifecycle 的 before/after 在实际获得执行租约后运行，before 可拒绝过期意图，after 处理领域收尾。带生命周期标记的恢复队列会等待适配器注册。停用/卸载/重载撤销来源代次并取消该来源操作，不能打断另一来源正在运行的轮次；应用正常关闭保留尚未运行的入箱，重启后恢复。

插件在 Agent 执行上下文中转发请求时，继承父身份的会话范围、能力、工具与预算上限，以及凭据和来源撤销链。委派到另一个插件或自动化不能扩大这些权限。内部子 Agent 唤醒使用封闭的 `@runtime/subagents` 来源，不受无关插件刷新影响。

## 设计参考与范围

采用 Hermes 的触发/执行分离、持久台账；ZCode 的入箱和稳定触发标识；DeepSeek Harness 的查询不激活会话与恢复边界；Claude 官方 SDK 的 Prompt/恢复/分支概念。没有复制参考项目实现，也没有将本地非官方 Claude 快照当现行能力依据。

- [Hermes cron internals](https://hermes-agent.nousresearch.com/docs/developer-guide/cron-internals)
- [ZCode automations](https://zcode.z.ai/en/docs/automations)
- [DeepSeek Harness schedule](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/subsystems/schedule.md)
- [Claude system prompts](https://code.claude.com/docs/en/agent-sdk/modifying-system-prompts)

当前不包含独立调度进程、通用 DAG、跨机器调度、工具代码编辑器或独立 Web 管理站点；管理入口位于现有设置中心。强语义参数规则仅覆盖已声明且能验证的内置契约；Shell 不是安全沙箱。临时基础设施失败留下可见执行错误，不盲目重放已开始的副作用。

## 验证

```powershell
.\python\python.exe -m pytest tests/test_session_control.py -q
.\python\python.exe -m pytest tests/test_plugin_session_control.py tests/test_plugin_host_services.py tests/test_feishu_adapter.py tests/test_goal_runner.py tests/test_execution_integration.py tests/test_subagent_notifications.py tests/test_acp_plugin.py tests/test_acp_interop.py tests/test_sugar_bili_scroll_workflows.py -q
```

新测试覆盖持久化/长期 key 冲突、隔离存储、远控关闭鉴权、配置 CAS 与临时覆盖、忙碌排队、参数约束、任务范围、夏令时、调度与签名 Webhook、进程恢复、预设版本、真实 HTTP + CLI 子进程、因果抑制，以及批量原子接收、渠道投递恢复、委派上限/撤销、精确执行事件流、领域生命周期与 B站显式重试。兼容性回归使用已有 Prompt、工具目录、追问、远控、飞书、Goal、Team、子任务、后台任务和 Runtime V2 测试。模型及外部平台使用替身；不声称完成真实账号端到端验收。
