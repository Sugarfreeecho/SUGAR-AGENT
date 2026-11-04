# ACP Agents

通过官方 ACP v1 协议提供双向接入；标准接口与 DSH 的 automation-only ACP 方案对齐。接口与所有权规格见 [docs/acp.md](../../docs/acp.md)。

## 对外提供 Agent

安装 `app/requirements.txt` 依赖并启动现有后端。在设置页确认 ACP Agents 插件启用，然后让 ACP 客户端启动：

```text
<Python 的绝对路径> <仓库绝对路径>/app/acp_stdio.py --server-url http://127.0.0.1:8192
```

Windows 可使用仓库 `python/python.exe`；Linux/macOS 使用项目虚拟环境。参数数组要把解释器、脚本路径和每个参数分开传递，路径中的空格不需要额外内嵌引号。适配器连接已经运行的后端，不会另起 Web 服务。只有 loopback HTTP origin 被接受，代理环境变量不会用于后端连接。退出 stdio 连接会停止该连接发起的任务并释放其 MCP，持久会话保留。

首次独立连接前，以运行 ACP 客户端的系统用户执行 `python app/agent-session-control.py auth login`，复用同一后端地址的登录凭据。宿主委派进程使用任务令牌；任务身份缺失时不会回退个人登录。prompt 进入统一持久队列，通过具体 operation 的事件流返回结果和取消；后端连接不依赖远控开关。

终端内需要直接收到任务结果时，可运行 `python app/acp_call.py --cwd <绝对工作目录> --prompt "任务"`；加 `--session-id` 继续已有会话，`--result-file` 保存最终 JSON。进程会等到 `completed` 后退出；`started` 只代表会话已激活，终端工具若先返回进程 ID 需要继续等待。HTTP 事件流中断按原 operation 和游标有界重连，不重复运行任务。此入口不提供对已经结束的客户端聊天的自动唤醒；详细契约见 [docs/acp.md](../../docs/acp.md)。

客户端依次发送 initialize、session/new（绝对 cwd）、session/prompt，消费 session/update，并响应 session/request_permission。session/list、session/resume、session/close 按声明的 capability 使用。resume 不回放历史。配置使用 session/set_config_option 的 model / reasoning_effort，并始终使用服务返回的 opaque value。

可在 new/resume 传入标准 stdio / Streamable HTTP mcpServers。stdio command 必须是绝对路径；环境和 HTTP headers 使用标准 name/value 数组。连接/发现失败会拒绝会话激活；请求不会改变全局 MCP 配置。开启扩展注册确认的部署仍执行原有注册审批策略。

非空 mcpServers 另需 `session.mcp.configure` 能力；模型与 reasoning 修改需要配置写入能力，工具审批需要审批能力。MCP 挂载和释放校验身份、会话范围及连接所有权。

## 委派给 DSH / Hermes

在 ACP Agents 设置的 agents_json 中配置目标，例如：

```json
{
  "dsh": {
    "command": "node",
    "args": ["D:/path/to/deepseek-harness/apps/cli/lib/bin.js", "--profile", "acp"],
    "env_refs": ["DEEPSEEK_API_KEY"],
    "permission": "reject",
    "timeout": 600
  },
  "hermes": {
    "command": "D:/path/to/hermes-venv/Scripts/python.exe",
    "args": ["-m", "acp_adapter"],
    "env_refs": [],
    "permission": "reject",
    "timeout": 600
  }
}
```

请替换示例路径，先安装/构建对应 Agent。Unix 上改为对应 node/虚拟环境路径。Windows 的 npm `.cmd` 启动器应改为 node + 已安装的 JS 入口；本实现直接 spawn 参数数组，不使用 shell 拼接。需要登录或凭据的外部 Agent 应事先完成自己的配置；env_refs 只引用当前后端环境中存在的变量名，不在 JSON 中存储凭据。

配置目标后，模型可发现 acp_agents 和 acp_task。acp_task 接受 agent（配置 ID）和 prompt；工作目录来自当前会话，模型不能覆盖命令、环境或 cwd。默认拒绝子 Agent 的权限请求。管理员选择 permission=allow 时，只批准 allow_once，遇到仅提供长期授权的请求仍拒绝。

目标可选 `"session_control": true`：由宿主签发受限会话控制令牌，继承父调用者范围、工具上限和撤销链。默认关闭且不转交个人控制令牌。该开关只控制外部 Agent 访问 SugarAgent 会话控制 API，不限制它自己运行时的工具。

默认每次 acp_task 新建会话；先用 acp_sessions 查询已有会话或用 acp_session_new 显式创建，再给 acp_task 传入 session_id 可继续同一上下文。续接失败不会自动新建。会话在来源会话、目标配置摘要和工作目录下隔离；配置改变后要重新查询，不能将其他工作区或来源未登记的 ID 直接传入。活跃连接由宿主复用，acp_session_close 释放连接并保留历史；断开后的继续依赖目标声明 session/resume。

acp_task 默认同步等待，进度可在任务页实时查看，结束后作为工具结果返回。background=true 立即返回 task_id；notify 可选 final（默认，仅在结束时回送汇总）、all（中间进度提示加结束汇总）、none（只保存，不主动推送）。接收者固定为宿主记录的发起会话，模型和远端 Agent 不能指定任意回送地址。进度用 session.notice 写提示，不开启模型轮次；结束汇总用 session.send 排队唤醒原 Agent。同步任务不另行推送第二份回报。

ACP v1 普通文本流没有统一的“最终回答片段”标记：中间说明与末尾回答均被收集，任务结束汇总包含全部普通回复文本。内部思考、原始工具流、stderr 和异常载荷不进入这个汇总。文本限制为 32000 字符，超过时 truncated=true。取消、超时、失败保留已收到的部分文本，失败诊断仅存类别。调用 acp_tasks、acp_task_get(task_id, after)、acp_task_cancel(task_id) 可查看、增量读取、取消自己来源会话的任务。

任务、进度和回送意图保存在宿主工作区外的 acp-outbound.sqlite。回送有固定幂等 key 与受理操作 ID，暂时失败重试，授权撤销或来源丢失时标记 blocked，不改投其他会话。宿主重启将未完成任务标记 interrupted 并回送已有结果，不自动重复执行外部任务。不承诺继承父工具限制或硬沙箱。

## 验证

```text
python -m pytest tests/test_acp_bridge.py tests/test_acp_interop.py tests/test_acp_mcp_scope.py
```

将 ACP_TYPESCRIPT_SDK 指向 DSH 安装的 `@agentclientprotocol/sdk/dist/acp.js` 可运行同版本 TypeScript SDK 对生产 stdio 入口的协议检查。将 DSH_ACP_CHECKOUT 指向构建完成的 DSH 源码目录，可运行 `tests/test_acp_dsh_peer.py`：使用隔离的临时 DSH_HOME 和占位 key，只验证 initialize/new/close/resume/list，不发送模型请求。普通测试不需要真实 API key。

当前不声明图像/音频输入、历史回放、fork、客户端文件系统/终端及其他交互扩展。遇到原生 ask_user 会停止运行并返回协议错误；用户可在原生界面继续处理，不会伪造回答。

## 热重载

设置 → ACP Agents 现在包含入站客户端列表、启动配置和出站目标配置；也可直接打开 `/plugins/acp-agents`。
入站列表显示客户端名称/版本、协议、连接时间、最后心跳、最近活动、忙碌状态，以及关联会话和工作目录。点击「查看会话」可在新标签页打开原生会话。
15 秒发送一次心跳，超过 50 秒显示心跳超时；正常关闭后保留断开记录 10 分钟。旧适配器需重连才能上报。连接列表不展示凭据或任务正文。
启动配置中的 `env_refs` 是环境变量名；适配器仍需已有 Session Control 登录或宿主签发的 `MYAGENT_CONTROL_TOKEN`。页面不签发或显示凭据。
出站目标继续使用原来的 `agents_json`，保存前通过服务端完整校验；刷新连接列表不会覆盖未保存的配置。

- 改本目录里的 `host.py` → 设置页「重新发现 / 热重载」即生效，不必重启：`acp_agents` / `acp_task` 工具按内容摘要换新模块，`/api/acp/*` 路由先摘旧的再注册。
- ACP 协议实现位于宿主 `app/acp_bridge/`。适配器进程中的修改（backend/server）在客户端重连后生效；宿主已导入的共享模块修改仍需重启后端。新加入的连接登记模块可随插件首次导入，无需重启。已建立的 stdio 连接不会因为插件重载而重建。
- 判定口径见 [插件热重载](../../docs/plugin_hot_reload.md)。
