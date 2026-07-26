# Agent 共享运行时与 Subagent 隔离

主 Agent、普通 Subagent 和 Agent Team 成员统一接入共享运行时观测层。会话目录中的
`runtime_observability.json` 是心跳、运行状态、文件变更、Token、货币成本和预算状态的
持久数据源；`execution_metrics.json` 继续保存请求阶段和工具耗时，并在 API 返回时合并
共享观测数据。

## 心跳、重启与超时

- 每个运行都会记录 `started_at`、`heartbeat_at`、`stage`、`status` 和 `finished_at`。
- 进程启动时将上一进程遗留的 `running` 标记为 `orphaned`，不会让 UI 长期显示假运行。
- 后台 watchdog 默认每 15 秒检查一次；心跳超过 90 秒未更新时标记 `stale` 并请求中断，
  总运行时间超过 7200 秒时标记超时并取消运行任务。
- 可用 `AGENT_RUN_HEARTBEAT_INTERVAL_SECONDS`、`AGENT_RUN_STALE_SECONDS`、
  `AGENT_RUN_TIMEOUT_SECONDS` 和 `AGENT_RUN_WATCHDOG_INTERVAL_SECONDS` 调整。

## 文件轨迹

所有可能写入工作区的内置工具、Shell、MCP、Plugin 和 Hook 都会在调用前后获取工作区
状态并记录净变更。Git 状态与完整文件系统快照结合使用，因此也能发现 ignored 文件和
非 Git 目录中的创建、修改和删除。

这是工具调用边界的净变更审计，不是内核级文件追踪：一次调用中先创建后删除的瞬时文件，
以及工作区之外未声明的外部路径，不一定能被轨迹捕获。可用
`FILE_AUDIT_FULL_SNAPSHOT=0` 关闭完整扫描，或用 `FILE_AUDIT_MAX_FILES` 设置上限。

## 成本和预算

模型 Profile 可配置每百万 Token 的输入、输出、缓存读取和缓存写入价格（USD），以及
单次运行的成本预算。共享运行时按实际 usage 累加成本；达到预算后在下一次模型请求前
终止继续执行。未配置价格的 Profile 仍记录 Token，但货币成本为 0。

## 模型选择与 fork

- `task` 不填写模型 Profile 时默认继承父 Agent 的有效 Profile。
- 只有父 Agent 判断任务需要特定模型时，才显式填写 Profile。
- 普通隔离启动不复制父历史。
- `resume=self` 在 Runtime V2 中创建不可变父模型前缀引用，记录父会话和锚点事件序号，
  不再深拷贝历史。子会话只持久化自己的尾部。
- fork 同时冻结父请求实际使用的 System Prompt 段、完整工具定义，以及模型、
  temperature、max output、context window、`extra_body` 和 reasoning/thinking 配置。
- 子会话压缩或重写历史时会物化有效历史并脱离引用。Legacy runtime 为兼容仍使用深拷贝。

这种实现与 Claude Code 的 fork 目标相近：父前缀不可变、子分支追加自己的消息，便于
提供商复用相同序列化前缀。实际 prompt-cache 是否命中仍取决于提供商、模型和请求序列化。

## 一次性审批

普通 Subagent 复用 Agent Team 的一次性授权语义。默认保护 Shell、删除、下载和外部写
操作；授权按 `child + tool + resource` 精确匹配，只消费一次。

```text
task(action="permissions", resume="<child-id>")
task(
  action="resolve_permission",
  resume="<child-id>",
  permission_id="<permission-id>",
  decision="allowed" | "denied",
  reason="..."
)
```

## 托管 worktree

所有写型普通 Subagent 和可写 Team 成员默认尝试创建托管 Git worktree；主工作树即使有
未提交修改，也可从当前 `HEAD` 创建隔离分支。只读任务不创建 worktree。显式
`isolation="worktree"` 时 Git 不可用会拒绝启动；`isolation="shared"` 可主动选择共享目录。

```text
task(action="worktree", resume="<child-id>", worktree_action="status")
task(action="worktree", resume="<child-id>", worktree_action="diff")
task(action="worktree", resume="<child-id>", worktree_action="retain")
task(action="worktree", resume="<child-id>", worktree_action="merge")
task(action="worktree", resume="<child-id>", worktree_action="discard")
```

`merge` 仍要求主工作树干净；冲突时自动 abort 并保留 worktree。`discard` 只删除通过路径
校验的 MyAgent 托管 worktree。

## Plugin/MCP worktree 契约

Plugin 命令 Hook 在隔离任务中以 worktree 为 cwd，并获得
`MYAGENT_WORKSPACE_ROOT` 和 `MYAGENT_WORKTREE_ISOLATED=1`。MCP 服务应为工具声明 effect：

```json
{
  "servers": {
    "filesystem": {
      "command": "example-mcp-server",
      "tool_contracts": {
        "read_file": {
          "effect": "read",
          "resource_arguments": ["path"]
        },
        "write_file": {
          "effect": "workspace_write",
          "resource_arguments": ["path"],
          "path_arguments": ["path"],
          "workspace_root_argument": "workspace_root",
          "worktree_compatible": true
        },
        "publish": {
          "effect": "external_write",
          "resource_arguments": ["destination"]
        }
      }
    }
  }
}
```

托管 worktree 中，未声明 effect 的 MCP 工具会 fail closed。`workspace_write` 必须声明
worktree 兼容性和根目录参数；运行时注入 worktree 根并拒绝逃逸路径。
`external_write` 不改写目标，但必须经过一次性审批。

原生 Plugin API v1 工具使用相同字段，在 `@plugin.tool(...)` /
`plugin.registerTool(...)` 中声明 `effect`、`resource_arguments`、
`path_arguments`、`workspace_root_argument` 和 `worktree_compatible`。未声明的原生
Plugin 工具在托管 worktree 中同样 fail closed。

Plugin/外部进程若显式使用绝对路径，cwd 本身无法构成操作系统级沙箱；需要通过 MCP
契约、一次性审批或进程级沙箱继续约束。

## 运行中 steer

父 Agent 可向仍在运行的子代理发送持久消息：

```text
task(
  action="steer",
  resume="<running-child-id>",
  prompt="新的约束或纠正",
  steer_mode="interrupt" | "append",
  client_id="<optional-idempotency-key>"
)
```

`interrupt` 在安全边界停止当前步骤并用新消息重启；`append` 在下一轮加入消息。消息先
持久化再消费，进程异常时不会静默丢失。

## Agent Team 自动调度

Team 调度器按 `urgent > high > normal > low` 选择依赖已完成的 pending 任务，只向没有
in-progress 任务的 idle 成员分配。任务创建、完成、成员空闲及后台扫描都会触发下一轮
claim 和 dispatch，因此可连续唤醒成员。claim 仍通过事件事务和 CAS 完成，避免重复分配。
进程重启后扫描活动 Team，可继续认领持久化的待办任务。

当前调度器面向单 MyAgent 进程；尚未提供多实例分布式 leader election。
