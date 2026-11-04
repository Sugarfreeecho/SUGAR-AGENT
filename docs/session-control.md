# 统一会话管理 CLI

入口为 `app/agent-session-control.py`，实现位于 `app/session_control/`。它连接当前 SugarAgent FastAPI 后端；`agentctl.py` 继续负责应用启停。CLI 退出和浏览器关闭不会取消后端已经持久接收的输入。

## 安装与第一次连接

使用仓库配套 Python 安装新增依赖，并按项目原有方式启动包含本次改动的后端：

```powershell
.\python\python.exe -m pip install -r app\requirements.txt
.\python\python.exe app/agent-session-control.py --help
.\python\python.exe app/agent-session-control.py auth login
.\python\python.exe app/agent-session-control.py doctor
.\python\python.exe app/agent-session-control.py session list
```

`auth login` 在交互终端隐藏输入 Bootstrap key 或现有远控配对码。控制服务在后端启动时生成 `bootstrap.key`：Windows 默认 `%LOCALAPPDATA%\SugarAgent\session-control\bootstrap.key`；Linux 默认 `$XDG_STATE_HOME/sugaragent/session-control/bootstrap.key`（未设置时为 `~/.local/state/`）。设置 `MYAGENT_SESSION_CONTROL_HOME` 可覆盖后端状态目录；设置 `MYAGENT_SECURITY_HOME` 时默认使用其同级的 `session-control/`。Bootstrap 只能经直接 loopback 连接兑换管理员身份。现有配对设备保留其原有权限，write 不等于配置或自动化管理员。

非交互登录支持 `auth login --file PRIVATE_LOGIN.json` 或 `--stdin`，内容为 `{"bootstrap_token":"...","name":"My CLI"}` 或 `{"pairing_code":"...","name":"My CLI"}`。凭据文件应由调用者保密；命令结果不打印令牌。个人凭据按后端地址存储于用户状态目录，`MYAGENT_SESSION_CREDENTIAL_DIR` 可覆盖客户端凭据目录。`auth status/logout` 查看身份或撤销当前凭据。

地址依次取 `--base-url`、`MYAGENT_SESSION_BASE_URL`、`http://127.0.0.1:$MYAGENT_SERVER_PORT`，默认端口 8192。支持从任意工作目录用脚本绝对路径调用。脚本不启动后端；无连接时退出码为 6。非 loopback 地址要求 HTTPS。服务注册不依赖 `MYAGENT_REMOTE_CONTROL_ENABLED`，也不改变原有监听地址；`MYAGENT_SESSION_CONTROL_ENABLED=0` 拒绝控制调用和后续自动化派发。

## 命令

| 命令组 | 子命令 |
| --- | --- |
| auth | login、status、logout |
| session | create、list、get、read、search、send、attach、fork、stop、continue、recover、update、archive、unarchive、delete、export、import |
| config | get、set、preview、reset |
| tools | list、describe |
| preset | list、get、create、update、delete、apply |
| schedule | create、list、get、update、pause、resume、run、delete |
| event | create、list、get、update、pause、resume、test、delete |
| event source | create、list、get、update、disable、test |
| execution | list、get、wait、cancel |
| doctor | 连接、协议和功能检查 |

常用字段有专用参数；其余字段用 `--file` 或 `--stdin` 传一个 JSON 对象。所有命令都有 `--help`，全局参数可放在命令之前或之后。`--human` 美化 JSON；默认单个 JSON 回执：

```json
{"schema_version":1,"ok":true,"request_id":"...","operation_id":"...","data":{},"error":null}
```

修改命令接受 `--idempotency-key`。客户端默认每次生成新 key；网络超时后重试需显式复用原 key。后端按身份、key、方法与业务参数摘要去重；同一 key 改参返回冲突。不要将密钥放入业务参数、Prompt 或消息。

```powershell
python app/agent-session-control.py session create --name "研究" --work-dir "D:\Research"
python app/agent-session-control.py session read --id SESSION_ID --limit 50
python app/agent-session-control.py session search --query "部署"
python app/agent-session-control.py session send --id SESSION_ID --message-file prompt.txt --idempotency-key report-20261026
python app/agent-session-control.py session send --id SESSION_ID --message "继续处理" --wait --timeout 120
python app/agent-session-control.py execution get --id OPERATION_ID
python app/agent-session-control.py execution wait --id OPERATION_ID --timeout 120
python app/agent-session-control.py execution cancel --id OPERATION_ID
```

`send` 默认 queue，上一轮结束后运行；append 在当前轮安全边界加入；interrupt 需要额外打断能力。`attach` 仅观察，不新增用户轮次，使用逐行 JSON 输出快照、事件、心跳、游标和 gap。保存 `cursor` 与 `generation` 后可用 `session attach --id ... --cursor ... --generation ...` 重连。无游标连接从当前快照接收后续事实，显式 cursor=0 请求日志回放。日志换代会返回 gap 和新快照。流不返回内部推理或原始工具正文。Ctrl+C 只断开客户端。

普通 send 成功仅表示已持久接收。`--wait` 或 `execution wait` 等待具体执行；超时不取消。自动化 `run --wait` 等待其子执行，不把派发回执当完成。退出码：0 成功；1 执行/内部错误；2 参数错误；3 身份/权限错误；4 不存在；5 状态/版本冲突或容量不足；6 后端不可达；7 等待超时。

定时与事件来源由共享监视器调度，短 I/O、业务编排和模型执行使用各自有界工作池。已接受输入按来源、任务和会话独立计账，按来源轮转及会话 FIFO 派发；容量不足返回 HTTP 429、`Retry-After` 与 `queue_full/work_pool_full`，请保留原幂等 key 重试。`doctor` 可查看资源上限和当前占用；默认限额及插件接入说明见[共享监视器与资源预算](shared-event-monitor.md)。

导出下载到 CLI 所在机器；导入上传本地归档，当前上限 256 MiB，沿用已有后端解包、路径校验与 ID 重写：

```powershell
python app/agent-session-control.py session export --id SESSION_ID --output .\session.zip
python app/agent-session-control.py session import --archive .\session.zip --idempotency-key import-001
```

导出拒绝覆盖已有本地文件。管理员也可通过 JSON `{"source":"后端机器上的目录或归档路径"}` 调用旧导入适配器。导出回执含 `archive_path`、`filename`，可用该 operation ID 下载；后端临时归档过期时需创建新导出。

## Prompt、工具与预设

```powershell
python app/agent-session-control.py config get --id SESSION_ID
python app/agent-session-control.py config set --id SESSION_ID --expected-revision 0 --file examples/session-control/reviewer.json
python app/agent-session-control.py config preview --id SESSION_ID
python app/agent-session-control.py tools list --session-id SESSION_ID
python app/agent-session-control.py tools describe --name read_file
python app/agent-session-control.py config reset --id SESSION_ID --expected-revision 1
```

配置写入采用完整对象替换及 `expected_revision`，Prompt 和工具规则原子保存；读取当前版本后再写。运行中的轮次保留实际配置快照，下一用户轮次采用新配置。`preview` 返回同一 Prompt 组装器的系统段、工具定义及同一 Token 估算器结果；估算不含未来模型输出和循环中动态注入内容。

`system_prompt.mode` 可为 default、append、replace。default 等价于 append 空文本；replace 必须非空，上限 256 KiB UTF-8。独立配置不随历史压缩消失，必要运行事实和宿主授权仍有效。fork/子会话创建时复制配置，后续独立保存。

`tools.mode=inherit` 继承已注册目录；custom 使用 allow 列表，显式空 allow 禁用全部工具。引用是 `{"kind":"host","owner":"core.tools","name":"read_file"}` 这样的来源身份，必须先从 `tools list` 获取；显示别名不能用于扩大权限。MCP 和插件使用各自稳定 owner/name。deny 优先，任务工具集合与会话及宿主能力取交集。

bindings 支持 defaults、fixed，以及 JSON pointer 参数规则：enum、number、length、path、url。defaults/fixed 的键是工具顶层参数名；规则示例见 `examples/session-control/`。规则在 Hook 前填入绑定值，Hook 和审批之后再次检查最终参数及中央授权。Shell 可用 enum 限制完整 command、fixed 限定 workdir/后台参数、number 限制 timeout_ms；Shell 约束不等于文件系统沙箱。

path roots 为绝对真实路径或 `$workspace`；内置 URL 工具对重定向同样检查精确域名、协议、端口。没有可验证目录/网络语义的插件和 MCP 仅支持 schema 可验证的普通值规则。schema 指纹变化时必需工具阻塞派发，可选工具从有效目录移除。配置层固定值矛盾、数值或枚举无交集时拒绝执行。

预设保存明确版本，apply 复制到目标会话，之后的预设升级不会隐式更新会话：

```powershell
python app/agent-session-control.py preset create --name reviewer --file examples/session-control/reviewer.json
python app/agent-session-control.py preset apply --id PRESET_ID --session-id SESSION_ID --expected-revision 0
```

用 JSON `revision` 选择旧版。创建/更新任务的 `runtime_override` 支持临时 Prompt 追加/替换、工具收窄、read_only 和 `limits`（timeout_seconds、max_tool_calls）；快照与具体 turn 绑定，不泄漏到下一轮。

## 定时与事件

也可在设置页的「定时任务」页签管理时间、会话、Prompt、工具及通知，详见 [设置页说明](schedule-settings.md)。它与 CLI 共用后端调度和任务记录。

替换示例中的 SESSION_ID 和工作目录后提交：

```powershell
python app/agent-session-control.py schedule create --file examples/session-control/schedule.json
python app/agent-session-control.py schedule list
python app/agent-session-control.py schedule run --id TASK_ID --wait --timeout 120
python app/agent-session-control.py schedule pause --id TASK_ID
python app/agent-session-control.py schedule resume --id TASK_ID
python app/agent-session-control.py event create --file examples/session-control/event-rule.json
python app/agent-session-control.py event test --id RULE_ID --file examples/session-control/test-event.json
python app/agent-session-control.py execution list --id TASK_ID
```

trigger 类型：`at`（有 UTC offset 的 ISO 时间）、`after`（seconds）、`interval`（seconds≥60）、`daily/weekdays`（time）、`weekly`（time、weekdays=ISO 1–7）、`monthly`（time、days=1–31）、`cron`（expression，五字段数字语法及 `* / , -`）。日历规则 time_zone 默认 Asia/Shanghai；周期 interval 保存 anchor。每月不存在的日期和 DST 不存在时间跳过，重复本地时间取较早一次。

target 为 `{"mode":"existing","session_id":"..."}`，或 `{"mode":"new"}` 加 workspace。action.kind 为 prompt、notice、continue、stop；prompt/notice 需 text。notice 只追加状态，不驱动模型。stop/continue 需分别在任务 policy.capabilities 中授权。可配置 `misfire=latest|skip`、`max_runs`、`end_at`（Unix 秒）。手动 run 不推进计划游标和运行次数。

后台停机时暂停调度；恢复默认只补最新周期实例，一次性任务补一次。skip 忽略超过 60 秒的漏跑。每个周期任务最多保留一个最新待执行 prompt，事件输入逐条保留；已开始执行的不重跑。忙碌和归档目标保留持久排队；删除目标使授权/派发失败并记录错误。pause 不取消已接收实例，可用 execution cancel 单独取消。

事件类型：turn.completed、run.ended、subagent.completed、job.completed、interaction.resolved、goal.state_changed、session.lifecycle_changed、webhook.received。来自持久日志和状态事实，不监听 token。条件使用 all/any 组合及 eq/ne/contains/in/gt/gte/lt/lte，字段路径如 `data.session_id`。规则从创建/更新时开始接收新事件，不自动重放历史。因果链重复同一规则或超过 16 层会记录 automation.suppressed。

Webhook 先创建规则，再创建 source；source.allowed_rules 固定允许触发的规则 ID。创建 source 时只返回一次 secret，get/list 隐藏 secret。端点为 `/api/automation/v1/hooks/SOURCE_ID`，正文 JSON 对象≤256 KiB，60 次/分钟。头部为 X-Sugar-Timestamp（Unix 秒，±300 秒）、X-Sugar-Event-ID（稳定来源 ID）、X-Sugar-Signature。签名是 `sha256=` 加 HMAC-SHA256(secret, timestamp + `\n` + eventID + `\n` + 原始正文) 的十六进制串。成功持久化返回 202，重复事件返回 200；同一来源/ID 改正文返回 409。外部事件作为普通用户输入，不作为系统指令。

## 权限与恢复

宿主为 Agent Shell 子进程注入 MYAGENT_CONTROL_TASK 和 MYAGENT_CONTROL_TOKEN。模型不传入令牌；有任务标记但缺少令牌时不会回退个人登录身份。默认同工作区开放查询、读取、订阅、创建、分支、排队发送和 notice；配置写入、打断、归档/删除、自动化与预设管理需独立授权。task policy scope 支持 self、tree、sessions、workspace、workspaces、all。任务和委派配置不能扩大宿主能力，父凭据撤销/过期与全局关闭在后续调用及工具执行时检查。

控制库 `control.sqlite3` 使用 WAL；备份需与 WAL 一并处理或使用 SQLite 备份 API。库保存入箱、操作、任务、配置快照、事件、游标、来源密钥及凭据摘要；对话事实继续属于 Runtime V2。长期去重索引不随 Runtime 最近 256 个 operation 快照裁剪。

启动时没有完成证据的原 running/部分管理操作记为 unknown，不自动重跑可能含外部副作用的整轮。可读取历史并显式 recover；排队且未提交的消息由后端继续消费。尚未进入 Runtime 的暂时连接/提供者失败最多退避重试三次。规则匹配和触发派发失败记录 last_error 并暂停对应自动化；具体执行失败保留在 execution 中，不自动重跑该轮。自动化临时配置重试和恢复使用原 turn 快照。

旧入口和剩余边界见 [接口迁移清单](session-control-migration.md)。本次验证使用隔离存储、实际 SessionManager/Runtime V2、HTTP 后端与 CLI 子进程，模型和外部平台为替身；真实账号、模型请求和业务端到端运行仍需在部署环境验收。

## 插件与渠道

飞书消息、ACP prompt、插件批量输入、B站执行及 Goal/后台完成/子 Agent 完成唤醒已接入统一入箱。可用 `execution list --session-id SESSION_ID` 查询对应操作，再用 execution get/wait/cancel 管理。渠道发送状态、B站额度与 outbox、Goal 审核及 Team 成员状态仍由原领域服务负责。

宿主插件使用公共 Python API 接入，调用示例和迁移边界见 [宿主插件接入](session-control-migration.md#宿主插件接入)。插件停用撤销其来源授权，旧凭据和委派链随之失效；正常后端停机保留未执行输入。修改宿主 `app/` 实现后需要按原流程重启后端；本次改造没有自动重启运行中的应用。
