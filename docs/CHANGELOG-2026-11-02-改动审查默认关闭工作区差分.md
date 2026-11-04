# 改动审查：工作区差分默认关闭（2026-11-02）

## 背景

用户核查（CR 第 6 条）实测确认：同一工作根下两个会话并发时，B 会话的补扫会把 A 会话的落盘写入记成自己的改动行，且 B 的撤销会把 A 的改动退回 B 的轮次起点（探针与结论见 `workspace/改动审查_同目录多会话_20261012/`）。

工作区差分（Git inventory 对比每轮全量基线）本身无法区分“谁写的”；默认开启等于让共享目录里的会话互相污染统计与撤销范围。因此改为**默认关闭**，保留显式开关。

## 变更内容

- 默认关闭 Git 工作区差分：不再建立每轮全量基线、不再执行 `git ls-files` 补扫。
- 新增开关 `MYAGENT_CHANGE_REVIEW_WORKSPACE_SWEEP=1`（写入 `app/.env` 或进程环境，重启后端生效）恢复原观测面。
- 关闭时：
  - `baselines/` 不产生新归档；已有旧基线由 `finish_other_runs` / `finish_run` 按原规则清理；
  - 不登记 `deferred_sweeps` 补扫义务；历史遗留义务在下一次 flush 时退役；
  - 声明式文件工具（`write_file / edit_file / apply_patch / delete_file`）仍按字节快照记录，覆盖率 `declared_paths`；
  - `run_shell` / MCP / 插件工具不再有改动行，覆盖状态为 `unavailable`（内部诊断；面板只呈现真实失败，不显示覆盖提示）；
  - 恢复被中断的旧捕获时，“无工作区覆盖面”记为 `checked + unavailable`，不再误报 `failed`；
  - 撤销/恢复、冲突保护、幂等、事务回滚语义不变，只作用于已记录（声明路径）的文件。

## 代码点

- `plugins/change-review/store.py`
  - 新增 `_workspace_sweep_enabled()`（默认 `0`）；
  - `_create_workspace_baseline`：关闭时直接返回，不枚举工作区；
  - `finish_capture`：关闭时跳过 `_sweep_workspace`，不写 `deferred_sweeps`；
  - `flush_deferred_sweeps`：关闭时清空遗留义务，仍交付 outbox 中已有事件；
  - recovery 状态：`workspace` / `declared_paths` / `unavailable` 三态按实际覆盖面判定。
- 未改 `host.py`、`runtime.py`、前端：`coverage` 三态与“只显示真实失败”的显示规则此前已存在。
- 文档：`docs/Agent 设计（用户方案）/06-能力扩展加载/08-内置插件-改动审查方案设计-UseCase清单.md` 新增 UC-121，并标注 UC-101/102/115/116/118/701 的开关前提。

## 行为对照

| 场景 | 默认（关闭） | `MYAGENT_CHANGE_REVIEW_WORKSPACE_SWEEP=1` |
|---|---|---|
| `write_file` 等声明式工具（Git / 非 Git、忽略文件） | 记录、可撤销 | 同左 |
| 目录删除 | 每文件一行 + 空目录行 | 同左 |
| `temporary=True` | 隐身，毕业后按原规则补全 | 同左 |
| `run_shell` / 脚本 / MCP / 插件写入 Git 仓库 | 不记录 | 记录、可撤销（原 UC-101/102/115） |
| 外部编辑器 / git checkout 改动 | 不记录 | 记录 |
| 同工作根其他会话的写入 | 不进入本会话审查 | 会进入（原行为，无法区分写者） |
| 每次工具调用的开销 | 少一次全工作区枚举/基线 | 首次工具建基线 + 批次尾补扫 |

## 验证

- `.\python\python.exe -m pytest tests/test_change_review_plugin.py tests/test_change_review_compact_store.py tests/test_change_review_diagnostics.py tests/test_change_review_ui_payload_runtime.py -q` → **82 passed**。
- `node tests/js/change_review_stats_runtime.mjs`、`change_review_visibility_runtime.mjs`、`change_review_ui_payload_runtime.cjs` → 全部通过。
- 扩大回归（`test_agent_loop_runtime_v2.py`、`test_agent_extensions_integration.py`、`test_plugin_ui_frontend.py`、`test_execution_recovery.py`）→ 140 passed，2 个失败与本改无关且开启开关后同样失败：
  - `test_agent_extensions_integration.py::test_agent_loop_wires_hooks_before_safety_approval_and_across_lifecycles`（缺少 `SessionEnd` 生命周期断言，工作树中 `agent_loop.py` 的既有差异）；
  - `test_execution_recovery.py::test_shell_timeout_keeps_stdout_and_stderr`（shell 超时后未带回 stdout）。
- 新增用例：`test_workspace_sweep_is_off_by_default`、`test_workspace_sweep_opt_in_keeps_git_observation`、`test_disabled_sweep_retires_legacy_obligations`、`test_disabled_sweep_recovery_reports_coverage_not_failure`、`test_runtime_reports_unavailable_when_sweep_is_off`。
- 注意：本机 pytest 需使用较短的 `--basetemp`（如 `%LOCALAPPDATA%\Temp\cr`）。默认 `TempOutput` 深层路径会让 blob 临时文件超过 Windows 260 字符上限，表现为 `FileNotFoundError`（与本次行为无关）。

## 生效与回滚

- 后端重启后生效（插件 store/runtime 由后端进程加载）；旧会话无需迁移。
- 回滚：把 `MYAGENT_CHANGE_REVIEW_WORKSPACE_SWEEP` 设为 `1` 即恢复旧行为；不设置即保持默认关闭。
