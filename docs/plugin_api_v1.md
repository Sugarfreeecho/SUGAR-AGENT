# SugarAgent Plugin API v1

## 会话固定系统上下文（2026-10-23）

固定章程、角色与长期任务规则可保存在会话 metadata 的 `system_context`，不再周期性复制到 user 消息。它是单个会话的附加系统指令，每次主任务请求装配时进入 `SystemMessage`；重启及历史压缩后仍保留。未设置的会话沿用原来的系统提示。

宿主 HTTP 接口：

```http
POST /sessions
Content-Type: application/json

{"system_context":"该会话的固定章程"}
```

已有会话使用 `PUT /sessions/{session_id}/system-context`，请求体同上；空字符串清空。必须是字符串，最多 256 KiB UTF-8 文本，不静默截断。非法参数返回 422，会话不存在返回 404；更新接口与聊天启动共用锁，正在执行时返回 409。创建时省略该字段与旧调用兼容。

进程内可信宿主插件可以调用：

```python
from agent_harness import session_manager

sid, *_ = session_manager.get_or_create_session(system_context=charter)
session_manager.set_session_system_context(sid, updated_charter)  # 相同内容不重复写盘
session_manager.set_session_system_context(sid, "")               # 清空
```

`get_or_create_session` 的该参数只用于新建；更新使用独立 setter。运行开始时固定本轮的 metadata 快照，setter 的变化在下一轮运行生效。子会话创建时继承一份章程快照，后续修改互不影响；fork 的冻结请求快照记录 `system_context`，装配时替换原段，更新或清空不会叠加旧章程。普通会话分支沿用复制的 metadata。静态提示缓存及本地整包 token 缓存识别章程内容变化，token 预览把它归入系统部分。

此入口承载宿主或用户明确设置的系统指令。普通 Worker 的 `@plugin.context` 继续提供带来源的 user 资料，不通过返回 `role` 自动升级为系统指令，也不会获得修改任意会话的能力。

`sugar-bili-scroll` 已接入：新值班会话创建时写入章程，已有值班会话在下一轮开始前补入；用户修改家目录 `duty.md` 后，下一轮更新该字段。每轮 user 消息只保留当轮参数，移除每隔 8 轮重发章程的账本逻辑；已有历史不做删除。

系统上下文仍随每次模型请求上送并占用输入 token。它减少重复历史，避免章程被摘要压缩，并提供稳定前缀；缓存命中与计费取决于提供方，不承诺省掉章程本身的全部 token。

## 插件模型上下文（2026-10-23）

原生 Python / Node 插件可注册文本上下文提供器。宿主在主任务每个 ReAct 步骤准备时采集，按真实会话隔离，并将变化后的完整快照作为带来源的 user 消息持久记录；聊天中显示可展开的“上下文注入”行。标题生成、摘要压缩等独立后台请求不主动采集这些提供器。

manifest 需要显式声明能力和可执行 runtime：

```json
{
  "schema_version": 1,
  "id": "org.example.context",
  "name": "Context Example",
  "version": "1.0.0",
  "capabilities": {"context": true},
  "runtime": {"type": "python", "entrypoint": "./plugin.py", "api_version": "1"}
}
```

Python 注册：

```python
from myagent_plugin_sdk import Plugin
plugin = Plugin()

@plugin.context(id="selection", title="选中的资料", max_tokens=800, timeout_seconds=2)
def selected_material(context):
    selection = context["session_state"].get("selection")
    if not selection:
        return None
    return {"text": selection["text"], "revision": selection.get("revision", "")}
```

`session_state` 只包含该插件在当前会话中的命名空间，不是整个宿主状态。handler 还接收宿主提供的 `plugin_id/session_id/run_id/step/workspace_root` 和本插件数据、缓存、临时目录。已有的 `permissions.context` 继续控制 `settings/secrets` 等可选上下文。handler 不获得其他插件或其他会话的状态，也不接收整份聊天历史。

Node 注册使用同一协议，manifest runtime 改为 `type:node`：

```javascript
module.exports.setup = plugin => {
  plugin.context({id: 'selection', title: '选中的资料', maxTokens: 800, timeoutSeconds: 2}, context => {
    const selection = context.session_state.selection;
    return selection ? {text: selection.text, revision: selection.revision ?? ''} : null;
  });
};
```

| 注册参数 | 规则 |
|---|---|
| `id` | 插件内唯一；1–64 位 ASCII 字母、数字、下划线、连字符 |
| `title` | 1–128 字符；省略时使用 id |
| `order` | 默认 100，范围 -10000 至 10000；同顺序按插件 id 与提供器 id 排序 |
| `max_tokens` / Node `maxTokens` | 默认 800，范围 1–4096；按宿主现有 tokenizer 估算裁剪 |
| `timeout_seconds` / Node `timeoutSeconds` | 默认 2 秒，范围 0.05–10 秒；不超过插件 runtime 超时 |
| `trigger` / `mode` | 本版仅支持 `step` / `snapshot` |

每插件最多 16 个提供器；每次最多调度 64 个、并发 4 个，描述与采集共用 8 秒调度预算。整体文本预算不超过 4096 个估算 token，且不超过当前配置模型上下文窗口的 5%；包含快照说明与来源标题。超限内容有截断标记，无法容纳的提供器列入省略信息。tokenizer 不可用时沿用应用的近似估算。

返回非空字符串或 `{text: string, revision?: string|int}`；空文本、Python `None`、Node `null/undefined` 表示明确撤销。额外角色或权限字段无效，提供器不能自行指定 system role。结果最多 256 KiB。相同实际内容不因采样时间或 revision 单独变化而重复追加；内容或来源签名变化后形成新快照。

采集失败不当作清空：同签名的旧资料会标为“上次状态，可能过期”；恢复后更新。禁用、注销、签名变化或授权撤销会移除旧贡献，整个活动集合为空时追加清除说明。压缩移除快照后按需要重新注入；停止后的迟到结果受运行写入围栏约束。模型重试复用已进入步骤的消息，不重新采集。

实际文本保存在 `model_user` 事实的 `content` 中，来源等元数据位于 `metadata.plugin_context`；UI 从同一事实投影内容，实时显示不另写一份 UI 事实。这类消息不计为真人用户轮次。既有 Hook 的 `additional_context` 保持兼容；右栏 `MyAgentPluginPage.context` 仍是界面上下文。

完整可安装示例见 [`examples/plugins/context-provider`](../examples/plugins/context-provider/README.md)，功能方案与验收见 [05/18](Agent%20设计（用户方案）/05-WebUI对话界面/18-插件上下文注入方案设计-UseCase清单.md)。当前提供器面向自动文本快照；页面“加入上下文”、任意浏览器 DOM 提取及图片注入未在此接口中开放。

## 右侧详情栏页面（2026-10-22）

插件可用 `capabilities.ui["details.tab"]` 注册完整界面；宿主使用已有 `web.entry`，自动生成 `/plugins/{plugin_id}`，不接受声明传入任意页面 URL 或宿主脚本。旧 `navigation` 页面贡献仍可打开，并自动进入右栏。示例：

```json
{
  "capabilities": {
    "web": { "entry": "web/index.html", "assets": "web" },
    "ui": {
      "details.tab": [{ "id": "main", "title": "示例页面", "scope": "session", "order": 60 }]
    }
  }
}
```

`scope` 为 `session`（默认，绑定当前会话）或 `app`（应用数据，无会话也可打开）。页面 ID、标题长度、scope 和顺序经宿主校验；标题作为文本显示。只提供 Web 资源目录但没有 `web.entry` 的插件不会生成页面。右栏开始页只有一个「插件」类型入口，进入 `plugins` 页面后集中列出已启用插件的页面贡献，内嵌设置项继续保留在设置中。插件选择器、设置入口、输入框页面动作与该列表使用同一打开链路；重复打开相同绑定页面聚焦已有标签。

主页面脚本可调用 `MyAgentDock.openPluginPage(pluginId, {pageId?, sessionId?})`；可信脚本注册 `registerTabType({id,kind,title,body,keepMounted?})` 后可通过 `openTab(kind)` 展示正文，注册返回注销函数。页面默认保活，正文元素可提供 `__dockVisibility(visible)` 与 `__dockDispose()` 钩子。普通插件使用声明式 iframe，不会因此获得导入宿主 JS 的权限。

宿主自动在插件 HTML 中装入 `/static/plugin-page-bridge.js`；仅在 `surface=details` 的嵌入模式启用。页面可读 `window.MyAgentPluginPage.context`，包括 `pluginId/pageId/tabId/sessionId/workDir/theme/lang/fontPx/visible`。上下文更新派发 `myagent:plugin-page-context`，可见性变化派发 `myagent:plugin-page-visibility`。公共桥在隐藏时跳过 interval 回调，关闭时清理 interval 并取消通过页面 fetch 发出的请求；插件自己的其他后台工作应订阅可见性和清理事件。

页面可调用 `MyAgentPluginPage.close()`、`openUrl(url)`，或 `request('open-plugin', {pluginId, pageId})` 打开本插件的其他声明页面。消息带 `version:1`，双方验证 origin 与 source；隐藏页面不能发起宿主导航。资源使用 `/plugin-assets/{plugin_id}/…` 绝对路径。同源 iframe 沿用原有插件网页信任模型，不是第三方权限隔离。

禁用插件会关闭页面，声明内容签名或 scope 变化也会回收旧页面。标签切换、会话切换、收起、分栏与浮动保留页面浏览上下文；布局及页面内存仅在当前应用页面生命周期中保留，不跨刷新恢复。完整方案与验收见 [05/17](Agent%20设计（用户方案）/05-WebUI对话界面/17-右栏插件页面与浏览器方案设计-UseCase清单.md)。

Plugin API v1 让原生 SugarAgent 插件在独立的持久 Worker 进程中注册并执行 Tool、
Hook 和 Slash Command。声明式 Skill、Hook、Command、MCP、Agent、Prompt 与
代码型 Runtime 可以放在同一个插件包内。

## Manifest

设置页面扩展使用 `capabilities.ui.settings.section`，可注册配置表单页签、文件/目录选择器或独立页面入口，见 [设置页插件接口](settings_plugin_api.md)。

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

宿主随应用发布的原生插件可以声明 `"system_builtin": true`。宿主只有在插件实际位于内置
`plugins/` 目录时才认可该标记，并将其从用户插件目录列表隐藏；插件已有的导航、设置、消息渲染、
会话徽章和面板贡献仍正常生效。用户目录中的插件不能靠该字段隐藏自身。

`runtime.type` 支持 `python` 和 `node`。代码型插件和 MCP 工具默认使用最简的模型工具名，
只有重名（包括与内置工具重名）时才逐级添加来源前缀：

```text
<local-tool-name>
<plugin-id>__<local-tool-name>
<plugin-id>__<server-name>__<local-tool-name>
```

例如 `org.example.hello` 的 `greet` 默认注册为 `greet`；不同插件均提供 `greet` 时，
分别注册为各自的 `<plugin-id>__greet`，如 `org_example_hello__greet`。
同一插件内多个 MCP 服务器仍有同名工具时，再添加服务器名；独立 MCP 服务器重名时使用
`<server-name>__<local-tool-name>`。非法字符转换为下划线，超长名称或规范化后仍重名时使用
摘要后缀，模型工具名最长 64 字符。命名结果不依赖注册顺序。

宿主内部仍以原有 `plugin_<plugin-id>__<local-tool-name>` / `mcp_<server>_<tool>`
标识绑定工具、保存启停状态和执行权限检查；模型简名通过注册表映射到对应来源。

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

工具正常返回的 JSON 或文本按业务数据处理，顶层 `error`、`ok`、`exit_code` 或文本中的
`Error:` 不会被通用执行层推断为调用失败。需要报告工具执行失败时，Python handler 应抛出异常，
Node handler 应抛异常或拒绝 Promise，由 worker 的独立调用状态信封传给宿主。
内置工具和 MCP 的判定契约见 [工具执行状态](tool_result_status.md)。

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

### 会话 UI 插槽

插件可通过 `capabilities.ui` 声明 `session.badge` 和 `session.panel`。宿主只投影
Manifest 明确列出的扩展状态字段，并默认使用通用安全组件渲染。面板动作通过
`set_state` 或 `invoke_tool` 声明，浏览器不能自行指定工具名或固定参数。
`session.badge` 默认显示文字徽章；内置工作流可使用 `"display": "activity"` 将匹配
状态投影为会话运行圆点，而不把领域判断重新写回宿主会话代码。

`session.panel` 支持可选 `group`（`{"id": "...", "label": "...", "order": 10}`）声明面板在
聊天区左缘「公共左侧栏」中的页签归属：同一 `group.id` 的面板归入同一页签，页签按 `order`
排序；未声明（或声明非法）时回退到默认「插件」页签。内置示例：session-todo → `plan`
（计划，order 10）、agent-goal → `goal`（目标，order 20）。

仓库自带的原生系统插件可为面板声明专用渲染资源：

```json
{
  "capabilities": {
    "web": {"assets": "web"},
    "ui": {
      "session.panel": [{
        "id": "current-plan",
        "namespace": "plan",
        "title": "Current plan",
        "renderer": {
          "module": "session-panel.js",
          "style": "session-panel.css"
        },
        "fields": [{"path": "/items", "label": "Items"}]
      }]
    }
  }
}
```

专用渲染器运行在宿主页，拥有页面 DOM 权限，因此不是普通插件能力。宿主会同时校验
`system_builtin`、原生格式、插件真实路径位于随应用发布的 `plugins/` 目录，以及资源
确实位于 `capabilities.web.assets` 中；用户插件即使伪造相同 Manifest 字段，也只会回退
到通用面板。资源 URL 由宿主生成并附带内容签名用于缓存失效。宿主在挂载渲染器**之前**
等待其 `module` / `style` 就绪（样式表未生效不绘制插件内容，`load` / `error` / 有界超时
兜底），因此渲染器自身**不需要**等待样式；样式加载失败不阻塞功能（照常挂载，仅缺插件
样式）。

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

- 插件入口不会导入 SugarAgent 主进程，而是在按插件隔离的持久 Worker 中加载。
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
| SugarAgent native | Tool、代码/声明式 Hook、代码/声明式 Command、MCP、Skill、Agent、Prompt |
| Claude Code | Manifest 和声明式资源；`commands/*.md` 可转为 Slash Command |
| Codex | `.codex-plugin/plugin.json` 的声明式资源兼容 |
| Hermes Agent | `plugin.yaml/yml`、常用 `register_tool/register_hook/register_command` Python API 子集 |
| OpenCode | npm package 发现、Tool 与常用 Hook 子集；TypeScript 依赖 Bun |

兼容层不是对宿主私有对象的完整模拟。OpenCode 的 `client`/`$`、Hermes 的 CLI/backend
等宿主专用上下文会出现在兼容诊断中，不能自动移植的能力标记为 `partial` 或
`unsupported`。

## v1 边界

v1 已稳定统一能力模型、持久 Worker、Tool/Hook/Command 注册、安装/卸载、依赖准备、
热重载、声明式宿主 UI 插槽和跨宿主兼容诊断。外部工具仍可通过 MCP 注册。尚未包含
中央插件市场索引、发布/签名服务，也不承诺任意 Claude、Codex、Hermes 或 OpenCode
插件无需修改即可运行。

## 公共侧栏计时文字更新

需要持续更新状态文字的面板，可在 `MyAgentPubar.configureNarrow(groupId, config)` 建立 `chip` 后调用 `MyAgentPubar.updateNarrowChip(groupId, text)`。它更新缓存配置和当前胶囊文字，保留窄栏按钮、事件处理器与焦点；未配置该分组胶囊时返回 `false`。完整状态或动作变化仍使用 `configureNarrow`。
