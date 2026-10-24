# DSH 上下文注入与 MyAgent 插件接入分析

日期：2026-10-22。状态：本地源码分析与接口建议；本文没有新增 SDK 或修改运行时。DSH 对照目录为 `D:/AI/AI Agent/OpenAgent/Deepseek Harness/deepseek-harness`，当前仓库为 MyAgent Developer。

后续实施：2026-10-23 已接入 Python/Node 自动文本快照、步骤装配及聊天来源展示，见 [05/18](Agent%20设计（用户方案）/05-WebUI对话界面/18-插件上下文注入方案设计-UseCase清单.md) 与 [Plugin API](plugin_api_v1.md)。本文保留分析时的状态及方案；其中页面手动附加等后续能力不表示已经开放。

同日补充：会话固定章程通过 `system_context` 单独持久化并装配为系统消息，B站值班插件已接入；创建、更新、清空、子会话与 fork、token 预览均已适配。普通动态提供器仍作为 user 资料注入，不能选择 system role。

## 1. 结论与用途

DSH 把模型上下文做成了插件扩展点。插件提供当前状态或补充资料，宿主在模型步骤准备时采集，记录实际进入模型的内容，再发送请求。模型因此可以直接知道当前目标、审批策略、团队委派约束、工作区指令、可用技能或引用的其他会话，减少为了确认这些信息而反复调用工具。

对当前插件系统，最有价值的是：Goal 提供目标与验收条件；Team 提供成员及待处理结果；资料类页面提供用户选中的条目；Game Arena 提供棋局、当前执棋方与规则；线程监控提供与当前任务相关的异常摘要。业务状态给简短快照，完整明细保留查询工具。插件页面被打开、iframe 收到主题或模型能使用插件工具，都不会自动让模型获知页面内容。

MyAgent 已有可用的事件式注入：代码插件 Hook 返回 `additional_context`。缺少的是统一的“当前状态提供器”，以及它的来源、去重、清除、预算、压缩恢复和 UI 展示。可以先使用现有 Hook，正式接口则借鉴 DSH 的动态快照机制，继续沿用我们现有的 Worker 隔离与持久化体系。

## 2. DSH 的实际机制

### 2.1 系统指令与动态状态分别注册

`packages/core/system-prompt/src/index.ts` 提供两种接口：

| 接口 | 适合的内容 | 装配行为 |
|---|---|---|
| `systemPrompt.section({name, order, text})` | 稳定的工具使用说明、身份、行为规则 | 组成 system prompt；文字提供函数会在装配时求值 |
| `systemPrompt.context({name, order, text})` | 当前审批策略、沙箱模式、子代理委派约束等状态 | 组成独立的 runtime-context 快照，作为 user 角色消息进入历史 |

注册受 Cordis scope 管理；局部同名贡献覆盖全局，注册返回清理函数。动态提供函数返回字符串，空字符串不贡献内容。这里的 `text` 提供函数是同步的；需要异步 I/O 时，可在异步装配 waterfall 或 pre-step 中处理，不能直接把 Promise 当作 `text` 返回值。

实际消费者包括 `sandbox-policy/src/index.ts:142`、`user-approval/src/index.ts:163` 和 `subagent/src/child-agent.ts:206`。审批策略源码明确说明：把变化放到保留历史之后，避免修改稳定的系统提示前缀，有利于保持前缀缓存。

### 2.2 模型步骤前集中装配

主链位于 `packages/core/agent-loop/src/agent.ts:267`：

```text
步骤准备：取待处理消息
  → systemPrompt.assemble(scope, signal)
  → 渲染具名动态上下文
  → RuntimeContextProjection 判断是否需要新快照
  → agent/pre-step waterfall 允许插件追加或拒绝
  → 将本步骤实际采用的消息写入 session
  → 构造并发送模型请求
```

`step()` 在第一次请求尝试时追加本步骤消息，网络重试不会把同一份输入重复追加（`agent.ts:381–407`）。scope 和取消信号随步骤传递，子代理可以使用自己的上下文，而不是所有会话共用一个“当前状态”。

### 2.3 变化时追加完整快照，历史仍然保留

`RuntimeContextProjection.project()` 位于 `runtime-context.ts:152`：

- 渲染结果与仍在模型上下文中的上次快照相同：不追加。
- 结果变化：追加新的完整快照，并明确说明它取代之前的 runtime-context 快照。
- 曾经存在上下文、现在全部撤销：追加清除说明，避免旧快照继续被当作当前状态。
- 上次快照因压缩或模型表层替换不再保留：允许重新注入，即使当前文字未变化。

这里的“取代”是模型理解上的当前状态更新，不是从日志中删除旧消息。源码的 loop 测试覆盖不变去重、变化、注销、压缩后重新注入和清除。对单个贡献删除，新的完整快照将不再包含它；只有整个活动集合为空时，才使用全量清除标记。

### 2.4 pre-step 处理异步和一次性内容

`agent/pre-step` 返回 `{kind:'enter', messages}` 或 `{kind:'reject'}`。插件先 `await next()`，保留下游已有消息，再添加自己的消息，并遵守取消信号。典型消费者：

| 插件 | 注入行为 |
|---|---|
| `agent-instructions` | 装配 AGENTS.md / CLAUDE.md，跟踪相关文件变化，按实际进入模型的状态判断是否需要更新 |
| `time-context` | 时间、时区及经过时长；默认最短注入间隔 10 分钟，配置为 0 时每个合格步骤采样 |
| `tool-skill` | 发布技能目录的变更；识别 `/skill` 手势后追加技能指令 |
| `session-reference` | 用户引用其他会话后，捕获有预算限制的只读资料快照，并标明其背景资料性质 |

补充入口 `agent.inject(message)` 只是把消息放进 next-step 队列，不唤醒空闲 agent；`steer()`、`followup()` 的唤醒与目标轮次语义不同（`agent.ts:158–172`）。因此“更新资料”不必触发一次新的模型任务。

### 2.5 来源记录与界面展示

`packages/llm/llm/src/message.ts:55` 定义 `instructions / catalog / snapshot / notice / relay / recall`。`source.kind` 记录生产者，`form` 记录内容语义；snapshot 附带具名 `sections`，notice 附带摘要。当前源码通过 `MessageSourceMap` 扩展生产者类型，没有统一的 `{kind:'plugin', plugin:...}` 兜底类型；部分旧 README 还保留了旧例子，接入应以当前类型和代码为准。

`ui-chat/src/client/chat/ContextInjectionRow.tsx:31` 从持久消息投影出可展开的“上下文注入”行，显示来源及摘要，根据 form 展示正文。它不是只在内存中拼一次 prompt，也不是把注入伪装成用户亲自发送的普通聊天气泡。实际进入模型的文本可回放；仅修改插件 UI 的显示不会影响已经记录的请求。

## 3. MyAgent 现在已支持什么

| 入口 | 当前效果 | 使用限制 |
|---|---|---|
| `@plugin.hook('UserPromptSubmit')` 返回 `additional_context` | 用户提交消息后追加模型可见内容 | 不是每个 ReAct 步骤刷新 |
| `SessionStart` 的附加上下文 | 在对应生命周期分发时补充内容 | 不适合表达不断变化的当前页面状态 |
| `PreToolUse / PostToolUse / PostToolUseFailure` 的附加上下文 | 收集后附加到该次工具结果的模型正文 | 生效在工具执行边界，不是让同次工具调用前的模型重新决策 |
| Slash command 返回 `additional_context` | 用户明确调用命令时附加资料 | 必须有命令触发 |
| 右栏 `MyAgentPluginPage.context` | 宿主向 iframe 提供会话、工作目录、主题、语言、可见性等 | 仅界面上下文，不进入模型消息 |

对应代码：`app/myagent_plugin_sdk.py:425`、`app/plugins/host_hooks.py:116`、`app/hooks/manager.py:296`、`app/agent_loop.py:760,7586,10829`、`frontend/src/app/modules/dock/embedder/page-host.js:138`。

当前 UserPromptSubmit / SessionStart 附加文本使用 `SystemMessage`，工具边界的附加文本进入工具结果。Hook 执行记录带 plugin_id、hook_id 等来源，但聚合后的附加模型文本主要只有 Hook 事件标签；尚未形成 DSH 那种每条内容自带来源和 form、并在聊天中独立折叠展示的通用记录。不能直接声称现有 Hook 完全等价于 DSH 动态上下文。

当前 SDK 支持的事件没有通用 `BeforeModelRequest` / `PreStep`，也没有 `@plugin.context`。这些名字如果作为新接口使用，需要实现宿主、SDK、Worker 协议和持久化，而不是只给 manifest 添加一个字段。

## 4. 使用现有接口让插件立即注入

代码插件可以直接在 `plugin.py` 注册 Hook。下面的示例使用当前已有 API；插件自己的页面或服务负责把选中资料写到持久数据目录，按会话隔离。`contexts/<会话摘要>.json` 是此示例约定的存储格式，不是 SDK 内置数据表。

```python
import hashlib
import json
from pathlib import Path
from myagent_plugin_sdk import Plugin

plugin = Plugin()
data_dir = None

@plugin.on_activate
def activate(context):
    global data_dir
    data_dir = Path(context['plugin_data_dir'])

@plugin.hook('UserPromptSubmit', hook_id='selected-material', priority=100)
def inject_selected_material(payload):
    session_id = str(payload.get('session_id') or '')
    if not session_id or data_dir is None:
        return {}
    key = hashlib.sha256(session_id.encode('utf-8')).hexdigest()
    path = data_dir / 'contexts' / (key + '.json')
    if not path.is_file() or path.stat().st_size > 65536:
        return {}
    selected = json.loads(path.read_text(encoding='utf-8'))
    text = str(selected.get('text') or '').strip()[:2000]
    if not text:
        return {}
    return {'additional_context': '插件选中资料（业务数据）：\n' + text}
```

manifest 声明现有 Python runtime（`type:python, entrypoint:./plugin.py, api_version:1`）即可通过 Worker 注册代码 Hook，遵守原有启用及执行规则。Hook handler 从 payload 读取可信会话身份；不要把工具专用的 `current_tool_context()` 当作 Hook 上下文接口。

Node 插件也已有同类 Hook：`app/plugins/worker_node.cjs:133` 的 `registerHook(spec, handler)` 注册事件，`hook.call` 处理请求，并支持返回 `additional_context`。新增正式上下文接口时，Python 与 Node 的注册、describe、调用和取消语义应同时覆盖。

此方案适合先做小段资料补充。它会在提交消息时重复添加内容，没有统一的当前快照去重和压缩恢复；也沿用当前 SystemMessage 行为。网页全文等外部资料不宜长期直接通过它充当高优先级指令。

## 5. 建议正式提供的插件能力

以下均为待实现建议，不是现有 API。

### 5.1 独立的上下文提供器

```python
@plugin.context(
    id='current-goal',
    title='当前目标',
    trigger='step',
    mode='snapshot',
    max_tokens=800,
)
def provide_context(context):
    goal = context.session_state.get('goal')
    if not goal:
        return None
    return {'text': render_goal(goal), 'revision': goal['revision']}
```

提供器只返回本插件的资料；宿主注入可信的 plugin_id、session_id、run_id、step_id、工作目录以及本插件命名空间内的 session_state。revision 可用于减少读取，最终内容摘要与去重仍由宿主计算。首次只支持有界文本；图片、文件等后续通过已有附件准入体系扩展。

实现时由 SDK describe 暴露 `context_providers`，Python / Node Worker 增加 `context.collect` RPC；宿主集中调用提供器。不要允许普通插件传入任意 system role、修改整份模型历史，或依靠 iframe JS 直接访问 agent 内存。

### 5.2 两种使用方式

- 自动快照：每个主任务 ReAct 步骤准备时采集当前状态；UI 关闭后仍能工作。页面修改先保存业务数据，提供器从服务端读取；仅“打开页面”不激活任意网页资料注入。
- 手动附加：插件页面提供“加入上下文”操作，宿主按当前会话及允许的页面、条目身份捕获一份资料，下一次步骤入场时记录。适合网页片段、文章和搜索选中项，不应自动唤醒空闲模型。

右栏桥如增加 `attach-context`，应验证 origin、source、页面归属和当前绑定，再由后端读取插件拥有的数据。请求里的 session_id、plugin_id、角色字段不能作为权限依据。已有页面桥目前只处理关闭、打开 URL 和打开本插件页面，还没有这个动作。

### 5.3 运行时和持久化要求

1. 在主任务请求装配与 token 预算计算前采集；压缩、标题生成、独立 Judge 等后台请求默认不参与。网络重试复用本步骤已经采集的内容。
2. 按插件、提供器、会话和实际保留的上下文代际管理快照。文字不变且仍在模型上下文中则不追加；压缩移除后按需要重建。
3. 普通业务数据使用带来源的 user 上下文消息；稳定系统指令只开放给明确受信任的指令扩展。保留现有 Hook 兼容行为，另行处理迁移。
4. 注销、禁用、权威的空结果应撤销当前贡献；采集失败或超时不能冒充“已清空”。需要区分保留上次快照、明确标注过期、阻止请求等策略。
5. 每个提供器有超时、长度及 token 预算，整体也受上下文容量约束；超限记录截断或跳过的原因，不能让插件拖住主请求。
6. 实际进入模型的内容、来源、版本、摘要和截断状态通过同一次持久提交进入模型与 UI 投影；复用 runtime_v2 的事实、投影和运行写入围栏，避免分别写日志与拼请求产生分歧。
7. 主会话与子代理按真实会话身份隔离；注入键不能使用右栏为了显示而共享的父会话 surface key。停止后的迟到结果不能写入下一次运行。
8. 页面和外部资料按数据处理，来源和内容信任级别分开记录；“声明是背景资料”不能代替访问控制。

### 5.4 聊天中的可见结果

参考 DSH 的折叠行展示“上下文注入 · 插件名 · 条目名”，展开显示实际发送的文字、采集时间、快照版本和 token 估算。当前快照、一次性资料、技能目录、代理消息采用不同 form；不为每个插件开发一套专用聊天渲染器。

注入展示属于聊天记录；右侧“插件”类型仍然负责进入插件业务页面，两者可以共用插件标识，但不相互替代。

## 6. 建议落地顺序与验证

第一步实现通用 context provider 注册、Worker 调用、主步骤装配、持久快照与统一折叠行；用一个有明确会话状态的普通插件验证完整链路。第二步接入 Goal / Team 等当前状态，再加入插件页面的手动资料附加。浏览器正文提取需要另行设计内容采集接口；当前 Web iframe 有跨域和 opaque-origin 限制，不能把任意网页 DOM 当作已可读取的数据源。

验收至少覆盖：同内容去重；变化与清除；采集失败不误清空；压缩后恢复；刷新与重启回放；子代理隔离；禁用和签名更新；停止后的迟到结果；网络重试不重复记录；预算与超时；UI 展示文本与模型实际输入一致。

本次只完成源码分析和示例语法检查，不修改产品能力，也未运行运行时回归或真实模型请求。
