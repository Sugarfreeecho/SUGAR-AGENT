# 扩展、子代理与运行注册 · 功能方案设计（UseCase 清单）

- 版本：2026-09-20 v3（覆盖至：当前工作区；补充跨进程运行租约）
- 用途：逐条审查（四字段格式）。
- 适用实现：`runtime_v2/extension_state.py`（432 行）、`subagent_store.py`、`subagent_repository.py`、`run_registry.py`。
- 上级：`00-会话存储RuntimeV2整体设计.md`

---

## 1. 功能定位

三类"附属账目"的存储语义：扩展命名空间状态、子代理账本、运行注册表（谁是活的）。

## 2. UseCase

### UC-8D1 扩展状态（命名空间）
- **触发**：插件写入会话级状态（如 change-review 的登记、其他插件数据）。
- **预期现象**：按插件+命名空间隔离读写；写入带 compare-and-set 语义——冲突抛明确错误（StateConflict），缺失抛 NotFound；重启保留。
- **依据**：`SessionExtensionStateStore / ExtensionStateConflict / ExtensionStateNotFound`。

### UC-8D2 子代理账本
- **触发**：子代理创建/更新/结束。
- **预期现象**：子代理状态、输出引用持久化；主会话可见子代理历史（关闭应用后仍可查）；分支复制时随会话走。
- **依据**：`RuntimeSubagentStore / SubagentRepository / SubagentState`。

### UC-8D3 运行注册表
- **触发**：run 开始/心跳/结束。
- **预期现象**：活跃 run 可按 `session_id + run_id` 列举（含心跳时间）；超时/孤儿可识别；结束后以唯一终态注销。
- **规则与边界**：同一会话允许观察到旧、新 run 的短暂交叠记录，但任何控制动作必须精确匹配 run；不得把“会话还有活动”当作某个旧 run 仍活动。
- **依据**：`RunRegistry / RunState`。

### UC-8D4 孤儿清理
- **触发**：异常退出后重启。
- **预期现象**：先核对 exact run 的本地任务与耐久终态；确认孤儿后补记终态/未读并清除 `running`，界面不出现僵尸状态。
- **规则与边界**：快照落后于事件尾部时应先投影/重建，不能只按快照宽限期长期拖延终态判断；但“当前进程没有 worker”不是孤儿证据，第二 WebUI 进程必须同时核对 Runtime V2 最近活动与同一 run 的共享观测心跳。孤儿清理不得绕过宽限期。
- **依据**：`_cleanup_orphan_runtime_v2_active_runs`、`_runtime_v2_active_runs_are_recent`、`_runtime_observability_active_runs_are_recent`、`runtime_observability.reconcile_orphaned_runs`。

### UC-8D5 stale 看门狗隔离
- **触发**：观测表中某个 `status=running` 的 run 心跳超过阈值。
- **预期现象**：若同一 exact run 仍有本地任务则跳过；否则只把该 run 标 stale、写入 `runtime_watchdog` 中断原因并取消其任务，同会话的新 run 不受影响。
- **规则与边界**：扫描只消费 `running` 行，历史 `stale` 行不会再次触发取消；取消接口必须是 `cancel_run_tasks_by_id`，不能退化为会话级 `cancel_run_tasks`。
- **依据**：`runtime_observability.scan_stale_runs`、`main.runtime_watchdog`、`session_lifecycle.cancel_run_tasks_by_id`。

### UC-8D6 跨进程 exact-run 租约
- **触发**：一个进程从耐久快照发现 active run，但在自身 `session_lifecycle` 注册表中找不到对应任务。
- **预期现象**：直接读取该会话 `runtime_observability.json`，只接受 `run_id` 与 Runtime V2 active run 匹配、`status=running` 且心跳在宽限期内的行；命中则认为 run 由其他进程持有并跳过接管。
- **规则与边界**：不得使用本进程已缓存的 observability 快照，否则可能看不到另一进程刚落盘的心跳；不得用会话级“有任意活动”替代 exact-run 匹配；Runtime V2 最近事件和共享心跳任一新鲜即可续租。
- **依据**：`webui._runtime_observability_active_runs_are_recent`、`execution_metrics._heartbeat_pump`、`runtime_observability.heartbeat_run`。

## 3. 边界

- 子代理的**界面呈现**见 ../05-WebUI对话界面/04；
- 扩展状态的**插件侧**使用方式由插件自定（宿主只提供语义）。

## 4. 依据映射

见上表（runtime_v2 + webui 清理段）。

## 5. 版本记录

- 2026-09-20 v3：新增 UC-8D6；孤儿清理加入跨进程 exact-run 心跳租约并强制尊重宽限期，避免第二 WebUI 把长模型/工具调用误判为 `no_local_activity`。
- 2026-09-20 v2：运行注册与孤儿清理收紧到 exact run；新增 UC-8D5 stale 看门狗隔离。
- 2026-09-13 v1：拆分首版（承接 UC-809/810）。
