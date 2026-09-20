# 钩子与工作流回调 · 功能方案设计（UseCase 清单）

- 版本：2026-09-20 v2（覆盖至：当前工作区）
- 用途：逐条审查（四字段格式）。
- 适用实现：`app/agent_loop.py`（钩子执行点 L174–830）、`app/agent_extensions.py`（钩子装配）、`app/hooks.json.example`。
- 上级：`00-ReAct运行时整体设计.md`

---

## 1. 功能定位

在工作流的固定节点开放"注入点"：提醒注入、停止收尾、执行前授权——插件与用户都可挂钩子。

## 2. UseCase

### UC-2F1 before_round 提醒注入
- **触发**：每轮开始前（有配置的钩子）。
- **预期现象**：钩子输出的提醒被注入本轮上下文；注入内容与模型行为变化可复现。
- **规则与边界**：注入点在构建输入**之前**；钩子输出为空则不产生任何痕迹。
- **依据**：`_workflow_callbacks`、`_append_hook_context`。

### UC-2F2 停止钩子
- **触发**：run 即将终止。
- **预期现象**：钩子可执行收尾逻辑（如整理输出/写外部系统）；失败不阻塞终止（按策略）。
- **依据**：`_apply_stop_hooks`。

### UC-2F3 执行前授权钩子
- **触发**：工具执行前。
- **预期现象**：钩子可给出 allow/ask/deny 结论与理由；ask/deny 进入审批/阻断路径（与 ../07-权限审批联动）。
- **规则与边界**：钩子结论理由会进入审计（谁因什么被拦）。
- **依据**：`_authorize_hook_before_execute`、`_dispatch_state_hook`、`_hook_decision_reason`。

### UC-2F4 钩子失败策略
- **触发**：命令型钩子失败/超时且 `failure_policy=block`。
- **预期现象**：对应操作被**阻断**（fail-closed）；审计记录失败原因；其余操作不受影响。
- **依据**：`hooks.json.example`、扩展模块分发逻辑。

### UC-2F5 工作流回调注册表短时缓存
- **触发**：连续 ReAct 轮次查询工作流回调。
- **预期现象**：2 秒 TTL 内直接复用 `_WORKFLOW_CALLBACKS_CACHE`，避免每轮重新激活内置回调并竞争激活锁；缓存过期后重新确认注册表。
- **规则与边界**：失效函数会清空缓存；内置回调 registry 采用原地更新，因此缓存持有引用不会阻止显式失效。TTL 只是热路径降本，不能替代扩展变更的正式失效机制。
- **依据**：`_workflow_callbacks / _invalidate_workflow_callbacks_cache`、`_WORKFLOW_CALLBACKS_TTL_SEC`。

### UC-2F6 Todo 活跃计划内存判定
- **触发**：Todo `before_round` 在每轮判断当前会话是否仍有活跃计划。
- **预期现象**：稳态只读取 `TodoManager._by_session`，不再每轮读取 Runtime V2 扩展状态和一致性快照。
- **规则与边界**：run 初始化、Todo 工具更新、UI 清空和上下文压缩边界负责同步/刷新内存状态；不得为了省读盘而让跨边界状态永久陈旧。
- **依据**：`TodoManager.has_active_plan / initialize_state`、Todo 更新与上下文压缩刷新调用点。

## 3. 边界

- 钩子的装载/信任/审计细节在 ../06-能力扩展加载/07；本篇只写"运行时如何使用钩子"。
- 钩子不改变工具本体语义（只可拦/放/提醒）。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-2F1 | `agent_loop.py` L174–203 |
| UC-2F2 | L788 |
| UC-2F3 | L501–606 |
| UC-2F4 | `hooks.json.example`、`agent_extensions.dispatch_hook` |
| UC-2F5 | `_workflow_callbacks`、`_WORKFLOW_CALLBACKS_CACHE` |
| UC-2F6 | `TodoManager.has_active_plan`、`initialize_state` |

## 5. 版本记录

- 2026-09-20 v2：补入工作流回调 2 秒 TTL 缓存与 Todo `before_round` 内存态查询边界。
- 2026-09-13 v1：拆分首版（原 UC-204）。
