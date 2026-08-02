# MyAgent Plugin API v1

Plugin API v1 让原生 MyAgent 插件在独立的持久 Worker 进程中注册并执行 Tool、
Hook 和 Slash Command。声明式 Skill、Hook、Command、MCP、Agent、Prompt 与
代码型 Runtime 可以放在同一个插件包内。

## Manifest

插件入口位于 `.myagent-plugin/plugin.json`：

```json
{
  "$schema": "../../docs/schemas/myagent-plugin-v1.schema.json",
  "schema_version": 1,
  "id": "org.example.hello",
  "name": "Hello Plugin",
  "version": "1.0.0",
  "commands": {
    "review": {
      "source": "./commands/review.md",
      "description": "Review the current change",
      "argumentHint": "[focus]"
    }
  },
  "dependencies": {
    "python": {"requirements": "./requirements.txt"},
    "plugins": {"org.example.base": ">=1.2,<2"}
  },
  "runtime": {
    "type": "python",
    "entrypoint": "./plugin.py",
    "api_version": "1",
    "timeout_seconds": 30
  }
}
```

`runtime.type` 支持 `python` 和 `node`。插件工具会转换成稳定、无冲突的模型工具名：

```text
plugin_<plugin-id>__<local-tool-name>
```

例如 `org.example.hello` 的 `greet` 会注册为
`plugin_org_example_hello__greet`。

## Python 插件

Python 插件可以导出模块级 `plugin = Plugin()`：

```python
from myagent_plugin_sdk import Plugin

plugin = Plugin()

@plugin.tool(
    name="greet",
    description="Generate a greeting.",
    input_schema={
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
        "additionalProperties": False,
    },
)
def greet(name):
    return {"message": f"Hello, {name}!"}
```

也可以导出 `setup(plugin)`：

```python
def setup(plugin):
    @plugin.tool(name="ping")
    async def ping():
        return "pong"
```

Handler 的 JSON 参数按关键字传入，返回值必须可转换为 JSON；同步和异步函数均可。

### 代码型 Hook

代码 Hook 与声明式 Hook 进入同一个 HookManager，因此共享 event、matcher、priority、
failure_policy、阻断/暂停决策及 Pre/PostToolUse 调用链。

```python
@plugin.hook(
    "PreToolUse",
    hook_id="deny-dangerous-shell",
    matcher="Shell",
    priority=20,
    failure_policy="block",
)
def deny_dangerous_shell(payload):
    if "format " in str(payload.get("tool_input", "")).lower():
        return {"decision": "deny", "reason": "Command rejected by plugin"}
    return {}
```

支持的事件为 `SessionStart`、`SessionEnd`、`UserPromptSubmit`、`PreToolUse`、
`PostToolUse`、`PostToolUseFailure`、`Stop`、`RunFailed`、`SubagentStart`、
`SubagentStop`、`PreCompact`、`PostCompact`、`GoalCreated`、
`GoalBeforeContinue`、`GoalCompleted`、`GoalBlocked`。

### 代码型 Slash Command

```python
@plugin.command(
    name="explain",
    description="Turn arguments into an explanation request",
    usage="<topic>",
)
def explain(arguments, context):
    return {
        "prompt": f"Explain this carefully: {arguments}",
        "additional_context": f"Session: {context.get('session_id', '')}",
    }
```

用户可使用 `/org.example.hello:explain topic` 调用；当本地命令名没有冲突时，也可使用
短别名 `/explain topic`。声明式 Markdown Command 支持 `$ARGUMENTS`、
`{{arguments}}` 和 `$1` 到 `$9`。

### 生命周期

`@plugin.on_activate` 在 Worker 首次完成插件装载后执行；`@plugin.on_deactivate`
在正常关闭、热重载或禁用时按逆序执行。Handler 接收宿主提供的 JSON context。

### Tool effect 与 worktree 契约

会写入文件或外部系统的工具应声明 effect 和资源参数。托管 worktree 中未声明 effect 的
Plugin 工具会 fail closed。

```python
@plugin.tool(
    name="write_report",
    description="Write a report inside the active workspace.",
    effect="workspace_write",
    resource_arguments=["path"],
    path_arguments=["path"],
    workspace_root_argument="workspace_root",
    worktree_compatible=True,
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "workspace_root": {"type": "string"},
        },
        "required": ["path"],
    },
)
def write_report(path, workspace_root):
    ...
```

支持的 effect：

- `read`：只读操作。
- `workspace_write`：写工作区；必须声明 `workspace_root_argument` 和
  `worktree_compatible`，运行时注入隔离根并校验 `path_arguments` 不逃逸。
- `external_write`：发送、上传、发布等外部写操作；路径不重写，但 Subagent/Team
  必须取得一次性审批。

`resource_arguments` 用于生成精确审批签名。工作区隔离依赖插件实际使用注入后的参数；
`app_restricted` 会把声明外的路径、网络、Shell 和未知副作用送入中央审批，但它不是
硬沙箱，无法阻止恶意 Worker 谎报能力或忽略参数。因此可执行插件首次启用及内容摘要
变化后，必须由用户在安全设置中确认信任；未信任时不会启动 Worker 或执行
`plugin.describe`。未来可选的原生 OS 沙箱可作为额外纵深防御，而不是插件正常运行的
前置条件。

## Node.js 插件

CommonJS、ES Module 均可导出 `setup(plugin)` 或默认 setup 函数：

```javascript
exports.setup = (plugin) => {
  plugin.registerTool(
    {
      name: "greet",
      description: "Generate a greeting.",
      inputSchema: {
        type: "object",
        properties: { name: { type: "string" } },
        required: ["name"],
        additionalProperties: false
      }
    },
    async ({ name }) => ({ message: `Hello, ${name}!` })
  );
};
```

Node Handler 接收一个参数对象。

## 安装与依赖

安装器接受本地目录、压缩包和 Git URL/路径。默认安装到第一个插件发现目录，并使用
staging 后再切换目标目录；更新时旧版本移动到 `.myagent-trash`，卸载同样采用可恢复
移动。

```http
POST /api/plugins/install
Content-Type: application/json

{
  "source": "https://github.com/example/myagent-plugin.git",
  "ref": "v1.2.0",
  "replace": true,
  "install_dependencies": true
}
```

- `POST /api/plugins/{plugin_id}/dependencies`：为已安装插件准备依赖。
- `DELETE /api/plugins/{plugin_id}`：卸载到 `.myagent-trash`。
- Python 依赖安装到插件私有 `.myagent-runtime/python` 虚拟环境。
- Node 依赖使用 npm；OpenCode TypeScript 适配优先使用 Bun。
- `dependencies.plugins` 在安装和依赖准备前校验已安装插件版本。

## 运行语义

- 插件入口不会导入 MyAgent 主进程，而是在按插件隔离的持久 Worker 中加载。
- 模型看到能力定义之前，Worker 会执行 `plugin.describe`。
- Tool、Hook、Command 调用分别使用 `tool.call`、`hook.call`、`command.call`。
- Worker 还支持 `plugin.ping` 和 `plugin.shutdown`；请求使用换行分隔 JSON，并以
  request id 关联响应。
- `PreToolUse`、`PostToolUse`、`PostToolUseFailure` Hooks 与内置工具使用同一条外层链路。
- 插件内容签名改变、插件禁用或手动重新加载后，能力缓存失效并关闭旧 Worker。
- 同一个插件的多次调用复用 Worker，因此插件内存状态可跨调用保留。
- 一个插件加载失败不会阻止其他插件注册。
- Worker 超时由 Manifest 的 `timeout_seconds` 控制，范围为 0.1 到 600 秒。

## 兼容适配

| 来源 | 当前能力 |
|---|---|
| MyAgent native | Tool、代码/声明式 Hook、代码/声明式 Command、MCP、Skill、Agent、Prompt |
| Claude Code | Manifest 和声明式资源；`commands/*.md` 可转为 Slash Command |
| Codex | `.codex-plugin/plugin.json` 的声明式资源兼容 |
| Hermes Agent | `plugin.yaml/yml`、常用 `register_tool/register_hook/register_command` Python API 子集 |
| OpenCode | npm package 发现、Tool 与常用 Hook 子集；TypeScript 依赖 Bun |

兼容层不是对宿主私有对象的完整模拟。OpenCode 的 `client`/`$`、Hermes 的 CLI/backend
等宿主专用上下文会出现在兼容诊断中，不能自动移植的能力标记为 `partial` 或
`unsupported`。

## v1 边界

v1 已稳定统一能力模型、持久 Worker、Tool/Hook/Command 注册、安装/卸载、依赖准备、
热重载和跨宿主兼容诊断。外部工具仍可通过 MCP 注册。尚未包含中央插件市场索引、
发布/签名服务、宿主私有 UI 扩展的通用抽象，也不承诺任意 Claude、Codex、Hermes 或
OpenCode 插件无需修改即可运行。
