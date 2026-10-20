# 扩展、子代理与运行注册 · 功能方案设计（UseCase 清单）

- 版本：2026-10-18 v7（扩展状态受守卫的投影补尾）
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
- **规则与边界**：子代理事件提交仍在原事务内耐久追加；独立日志夹入后的投影只补连续后缀，相邻追加也核对投影版本。旧版本、后缀断档/缺失保留全量恢复，详见 [02 · UC-8B7](02-投影回放与快照方案设计-UseCase清单.md)。
- **依据**：`RuntimeSubagentStore`。

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

### UC-8D7 任务索引的并发与保真
- **触发**：同一父会话下的并发任务行更新（多子代理并行启动）、删除清理与重启对账对 `tasks.json` / `pending_results.json` 的读写。
- **预期现象**：进程内互斥保证并发 upsert 不丢行（16 行 / 8 线程全数保留）；任务行更新**只合并任务字段**，不再以任务行整体覆盖子会话元数据——`subagent_work_dir`、`git_worktree_managed`、`readonly_strict` 等保持原值。
- **规则与边界**：子会话元数据归 SessionManager 所有（`write_metadata` 通道），任务索引侧只做字段合并；JSON 写入采用原子临时文件 + 有界 `replace` 重试（Windows 瞬时锁不导致丢行）。
- **依据**：`RuntimeSubagentStore.upsert_task / append_pending_result / remove_parent_rows / _write_json`；回归 `tests/runtime_v2/test_storage_layout.py::test_task_updates_preserve_child_worktree_metadata_and_concurrent_rows`。

### UC-8D8 pending 通知的最小读取范围

- **触发**：父 Agent 查询、消费或 claim 子代理 pending 结果。
- **预期现象**：`_load_pending_subagent_results` 读取 pending 行后，空队列直接返回，不再加载 metadata 或取得其会话锁；提供精确 `parent_run_id` 时，consume/claim 只过滤该 run，不构建完整 UI 历史投影。
- **规则与边界**：未指定 run ID 的旧路径保留 final-index/UI-history 过滤；非空队列所需兼容迁移保留。pending 文件、claim/ack/release 状态和所有权交接仍按原方式持久化；本批没有全局 metadata mtime 缓存。
- **依据**：`agent_harness.py::_load_pending_subagent_results / consume_pending_subagent_notifications / claim_pending_subagent_notifications`；`tests/test_agent_harness_reconcile.py`。pending 读取和通知领取 ≥50 ms 时记录墙钟/读取线程 CPU 或领取行数等明细，主循环落点见 [02/10 · UC-2J11](../02-ReAct运行时/10-子代理任务生命周期与事件循环隔离方案设计-UseCase清单.md)。

### UC-8D9 扩展状态更新的最小投影范围

- **触发**：扩展CAS、mutate、事件追加或读取命名空间；包括后台任务启动、结束、取结果和通知确认的`execution-tools`状态。
- **预期现象**：原会话事务中校验投影版本、实际文件身份、size/mtime及seq。已追平则复用不可变投影；同源且落后的快照走既有完整行游标/连续seq补尾，不再每次无条件`read_all()`。`get`在短事务中只复制目标namespace，调用者修改返回值不会污染发布快照。
- **规则与边界**：冷缓存、旧stamp/旧投影、替换、截断、seq不符及后缀不连续保留实际事实恢复。projector维持COW；实际扩展事实追加、CAS冲突、通知模型事实先于ack、失败传播和检查点契约保持同步，不增加陈旧状态TTL或后台延迟确认。
- **依据**：`SessionExtensionStateStore._snapshot_for_update/get`及`SnapshotStore.project_after_append`；`tests/runtime_v2/test_extension_append_suffix.py`覆盖journal/外部后缀、同size/mtime/seq替换、截断、旧版本/stamp和不可变发布。13.1MB真实前缀3次局部更新从803–892ms/6次全量读变为5–7ms/0次，完整重放一致；它是局部证据，不能外推整体500ms已达标。详见[88def复核](../../performance/agent-session-8533-run-88def-2026-10-18.md)。

**真实恢复补验**：88def磁盘快照seq7919落后事实7933；副本中仅重绑定文件身份、保留原seq/字节边界，禁止被测路径read_all，14条后缀6.160ms补到finished，模型消息和扩展状态与完整重放一致，旧发布快照不变。此为单次真实数据机制验证，不承诺一般冷恢复耗时。

## 3. 边界

- 子代理的**界面呈现**见 ../05-WebUI对话界面/04；
- 扩展状态的**插件侧**使用方式由插件自定（宿主只提供语义）。

## 4. 依据映射

见上表（runtime_v2 + webui 清理段）。

## 5. 版本记录

- 2026-10-18 v7：新增UC-8D9，消除后台执行扩展更新事务内无条件全量日志读取；命名空间读取只复制目标行，保留源身份/版本/seq校验、冷恢复和同步通知确认。
- 2026-10-17 v6：子代理事件追加复用严格后缀补齐，保留相邻版本检查、旧版/断档完整恢复和同步耐久提交。

- 2026-10-04：删除从未接线的 `SubagentRepository / PermissionManager / HealthMonitor` 三个零引用模块及 `subagent_repository.py`；实际子代理存储路径为 `RuntimeSubagentStore`（`subagent_store.py`）。

- 2026-09-30 v5：新增 UC-8D8，补录空 pending 提前返回和精确 parent run 查询跳过 UI 投影，区分读取优化与未改动的耐久通知协议。
- 2026-09-28 v4：新增 UC-8D7《任务索引的并发与保真》——任务行更新加锁且只合并字段（不再覆盖子会话元数据：worktree 根 / 模型档案 / 只读标记保持）；JSON 写入原子化 + Windows `replace` 重试。
- 2026-09-20 v3：新增 UC-8D6；孤儿清理加入跨进程 exact-run 心跳租约并强制尊重宽限期，避免第二 WebUI 把长模型/工具调用误判为 `no_local_activity`。
- 2026-09-20 v2：运行注册与孤儿清理收紧到 exact run；新增 UC-8D5 stale 看门狗隔离。
- 2026-09-13 v1：拆分首版（承接 UC-809/810）。
