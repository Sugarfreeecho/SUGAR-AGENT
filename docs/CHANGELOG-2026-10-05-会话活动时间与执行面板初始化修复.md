# 2026-10-05 会话活动时间与执行面板初始化修复

- 定位“侧栏会话全部变成今天、顺序打乱”的根因：`execution_services/notifications.py` 的启动扫描在**每个宿主进程**里为**每个未归档会话**补写一次执行面板状态（`execution-tools/panel`）。控制事件追加进 `events.jsonl` 后，启动期活动时间回填把日志 mtime 当成对话活动，于是所有旧会话的时间戳被刷成宿主启动时刻、排序退化为扫描顺序。
- 面板初始化改为幂等：新增 `_initialize_owner()`，先读命名空间状态，仅在缺失时写一次；`recover()` 仍每次启动执行。已有状态不再被改写，revision 不再随重启递增。
- 活动时间回填改为事件感知：`refresh_sessions_index_from_disk()` 在 mtime 提示有新增时，反向扫描事件日志取“最后一条非控制事件”的时间；`SESSION_ACTIVITY_CONTROL_EVENTS` 显式列出不计入活动的控制类事件（扩展命名空间状态 `extension_state_changed`、插件清单 `plugin_state_changed` / `plugin_reloaded`）。日志不可解析时退回 mtime 旧口径；尾部只有控制事件时保留已存活动时间。
- 已损坏的索引无需手工修：按上述口径重算即可自愈，本次实测 68 个未归档会话中仅 1 条需要更新；宿主重启一次后侧栏时间与顺序恢复。
- 启动重建成本可接受：全量索引重建约 0.47–0.51 s，其中 307 次日志尾扫合计约 0.23 s（仅对 mtime 新于已存活动时间的会话触发）。

回归覆盖：`tests/test_session_index_startup_rebuild.py`（新增“控制事件不改活动时间”“仅控制事件的日志保留 metadata 活动时间”两例）、`tests/test_execution_panel_bootstrap.py`（新增三例：一次写、保留原值、无管理器不写）；连带 `tests/test_execution_services.py`、`tests/test_execution_integration.py`、`tests/test_agent_harness_reconcile.py`（61 passed）与 `tests/runtime_v2`（222 passed）全绿。
