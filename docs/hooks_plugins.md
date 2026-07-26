# Hooks 与 Plugins

MyAgent 现在提供两个彼此独立、可以组合的扩展层：

- Hook 是生命周期执行点。它接收 JSON，运行受超时与最小环境限制的命令，并返回结构化决定。
- Plugin 是可安装扩展包。它可以同时贡献 Skill、声明式/代码型 Hook、Command、MCP、
  Agent、Prompt 和在独立持久 Worker 中运行的 Python/Node Runtime；插件入口不会
  导入 MyAgent 主进程。

## 开关与路径

```dotenv
HOOKS_ENABLED=1
HOOKS_PATH=
STOP_HOOK_MAX_RETRIES=3

PLUGINS_ENABLED=1
PLUGINS_DIR=../workspace/plugins
PLUGINS_STATE_PATH=../workspace/.myagent/plugins-state.json
```
`HOOKS_ENABLED` 与 `PLUGINS_ENABLED` 都默认开启，`0`、`false`、`no`、`off` 表示关闭。

- 关闭 Hooks：项目 Hook 和插件 Hook 都不执行；插件 Skill/MCP 等其他组件仍可使用。
- 关闭 Plugins：所有插件组件都从运行时注册表移除；项目自己的 `hooks.json` 仍可使用。
- 插件 Hook 需要两个开关同时开启。
- `MCP_ENABLED` 仍是 MCP 层的独立总开关。

`HOOKS_PATH` 留空时使用 `WORK_DIR/hooks.json`。`PLUGINS_DIRS` 可替代 `PLUGINS_DIR` 指定多个目录，Windows 用分号分隔。环境配置可在“设置 → 高级设置”编辑，扩展状态可在“设置 → 扩展管理”查看。

## Hook 配置

支持的事件：

```text
SessionStart, SessionEnd, UserPromptSubmit,
PreToolUse, PostToolUse, PostToolUseFailure,
SubagentStart, SubagentStop,
PreCompact, PostCompact, Stop, RunFailed,
GoalCreated, GoalBeforeContinue, GoalCompleted, GoalBlocked
```

`hooks.json` 示例：

```json
{
  "version": 1,
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "^(run_shell|write_file)$",
        "hooks": [
          {
            "id": "workspace-policy",
            "type": "command",
            "windows_command": "python scripts/hook_policy.py",
            "unix_command": "python3 scripts/hook_policy.py",
            "timeout_seconds": 10,
            "failure_policy": "block",
            "env_allowlist": ["MY_POLICY_MODE"]
          }
        ]
      }
    ]
  }
}
```

Hook 从标准输入读取事件 JSON，并在标准输出写一个 JSON 对象：

```json
{
  "decision": "allow",
  "updated_input": {"command": "git status --short"},
  "additional_context": "The command was reduced to a read-only check.",
  "user_message": "Policy adjusted the command."
}
```

决定值为 `allow`、`deny`、`ask`、`pause`、`continue`。`PreToolUse` 修改参数后，MyAgent 使用新参数重新进入原有路径限制与 UI 审批；Hook 不能绕过工具自身的安全检查。`ask` 在 Web UI 中打开确认框，没有审批通道时采取拒绝执行。Stop Hook 可以要求 Agent 继续工作，重试次数由 `STOP_HOOK_MAX_RETRIES` 限制。

失败策略：

- `ignore`：记录后继续。
- `warn`：向运行记录写入警告并继续（默认）。
- `block`：拒绝当前操作。
- `pause`：暂停当前运行。

命令默认只继承运行所需的最小环境；额外变量必须放入 `env_allowlist` 或 Hook 的静态 `env`。超时会终止命令及其子进程树，stdout 有大小上限，同一事件串行执行并带防重入保护。

## Native Plugin 格式

目录结构：

```text
my-plugin/
├─ .myagent-plugin/plugin.json
├─ plugin.py
├─ commands/review.md
├─ skills/review/SKILL.md
├─ hooks/hooks.json
├─ mcp/servers.json
├─ agents/reviewer.md
└─ prompts/finish.md
```

Manifest 示例：

```json
{
  "schema_version": 1,
  "id": "org.example.quality",
  "name": "Quality Tools",
  "version": "1.0.0",
  "description": "Review and quality gates",
  "runtime": {
    "type": "python",
    "entrypoint": "./plugin.py",
    "api_version": "1"
  },
  "commands": ["./commands"],
  "skills": ["./skills"],
  "hooks": "./hooks/hooks.json",
  "mcp_servers": "./mcp/servers.json",
  "agents": ["./agents"],
  "prompts": ["./prompts"],
  "permissions": {"shell": true, "network": false}
}
```

资源会自动命名空间化，例如 `org.example.quality:review` 和
`plugin_org_example_quality__lint`。Plugin Agent/Prompt 作为可按名称激活的声明式
指令资源进入现有 Skill 目录；MCP server 合并到现有 MCP 桥；声明式与代码 Hook
合并到同一生命周期注册表。完整 SDK、effect/worktree 契约、安装与依赖说明见
[Plugin API v1](./plugin_api_v1.md)。

插件启用状态写入原子 JSON。管理页支持单插件启停和重新发现/热重载；Skill、Hook 与 MCP 缓存会同步失效，下一次 Agent 边界立即使用新注册表。

## Claude / Codex / Hermes / OpenCode 兼容范围

MyAgent 会识别：

- `.myagent-plugin/plugin.json`：Native。
- `.claude-plugin/plugin.json`：Claude 兼容适配。
- `.codex-plugin/plugin.json`：Codex 兼容适配。
- `plugin.yaml` / `plugin.yml`：Hermes Python API 常用子集适配。
- OpenCode npm `package.json`：Tool 与常用 Hook 子集适配。

兼容报告为 `native`、`compatible`、`partial` 或 `unsupported`。Skill、Hook、Command、
MCP、Agent、Prompt 等通用能力可转换；Hermes backend/CLI、OpenCode `client`/`$`、
host 专属 App、认证流程和 UI 扩展会出现在诊断中。因此这不是“所有市场插件都能直接
运行”的二进制兼容承诺，而是一个带明确诊断的适配层。

## 安全与审计

- 组件路径必须留在插件根目录；拒绝 `..`、绝对越界、symlink 逃逸，并在加载时再次校验。
- 插件代码只在按插件隔离的 Worker 进程中导入，不进入 MyAgent 主进程。
- 将插件复制/安装到发现目录等同于信任其 Runtime、Hook 和 MCP 能力；不信任的插件应
  立即在管理页禁用并检查 manifest。
- Runtime V2 记录 Hook 开始、完成、失败、阻塞、超时、输入修改和插件状态/重载。快照只保留紧凑白名单字段，不复制大型 stdout/stderr/result 正文。

## 管理 API

```text
GET  /api/extensions
POST /api/extensions/reload
POST /api/plugins/install
POST /api/plugins/{plugin_id}/dependencies
DELETE /api/plugins/{plugin_id}
POST /api/plugins/{plugin_id}/enabled   {"enabled": true|false}
GET  /setup/extensions
```
