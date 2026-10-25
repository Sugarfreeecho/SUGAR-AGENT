# ACP Agents

通过官方 ACP v1 协议提供双向接入；标准接口与 DSH 的 automation-only ACP 方案对齐。接口与所有权规格见 [docs/acp.md](../../docs/acp.md)。

## 对外提供 Agent

安装 `app/requirements.txt` 依赖并启动现有后端。在设置页确认 ACP Agents 插件启用，然后让 ACP 客户端启动：

```text
<Python 的绝对路径> <仓库绝对路径>/app/acp_stdio.py --server-url http://127.0.0.1:8192
```

Windows 可使用仓库 `python/python.exe`；Linux/macOS 使用项目虚拟环境。参数数组要把解释器、脚本路径和每个参数分开传递，路径中的空格不需要额外内嵌引号。适配器连接已经运行的后端，不会另起 Web 服务。只有 loopback HTTP origin 被接受，代理环境变量不会用于后端连接。退出 stdio 连接会停止该连接发起的任务并释放其 MCP，持久会话保留。

客户端依次发送 initialize、session/new（绝对 cwd）、session/prompt，消费 session/update，并响应 session/request_permission。session/list、session/resume、session/close 按声明的 capability 使用。resume 不回放历史。配置使用 session/set_config_option 的 model / reasoning_effort，并始终使用服务返回的 opaque value。

可在 new/resume 传入标准 stdio / Streamable HTTP mcpServers。stdio command 必须是绝对路径；环境和 HTTP headers 使用标准 name/value 数组。连接/发现失败会拒绝会话激活；请求不会改变全局 MCP 配置。开启扩展注册确认的部署仍执行原有注册审批策略。

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

每次调用有独立进程、会话和上下文；不承诺继承父工具限制或硬沙箱。父取消和超时发送 cancel，随后关闭连接并回收进程树；模型结果限制为 32000 个字符，截断时返回 truncated=true。非 end_turn 终态返回工具失败及已收集的部分文本。外部 stderr 和异常载荷不进入模型结果。

## 验证

```text
python -m pytest tests/test_acp_bridge.py tests/test_acp_interop.py tests/test_acp_mcp_scope.py
```

将 ACP_TYPESCRIPT_SDK 指向 DSH 安装的 `@agentclientprotocol/sdk/dist/acp.js` 可运行同版本 TypeScript SDK 对生产 stdio 入口的协议检查。将 DSH_ACP_CHECKOUT 指向构建完成的 DSH 源码目录，可运行 `tests/test_acp_dsh_peer.py`：使用隔离的临时 DSH_HOME 和占位 key，只验证 initialize/new/close/resume/list，不发送模型请求。普通测试不需要真实 API key。

当前不声明图像/音频输入、历史回放、fork、客户端文件系统/终端及其他交互扩展。遇到原生 ask_user 会停止运行并返回协议错误；用户可在原生界面继续处理，不会伪造回答。
