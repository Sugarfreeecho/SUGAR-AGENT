# 执行服务与终端 · 功能方案设计（UseCase 清单）

- 版本：2026-10-05 v2（覆盖至：当前工作区；执行回执与证据链（投递≠生效））
- 用途：逐条审查（四字段格式）。
- 适用实现：`app/execution_services/**`（jobs / terminals / shell / computer / integration / notifications）、`app/runtime_v2/execution_journal.py`、`plugins/execution-tools/**`、`plugins/computer-use/**`、`frontend/src/app/terminal-runtime.js`。
- 上级：`00-横切能力整体设计.md`；对接：`../02-ReAct运行时`（工具循环）、`../06-能力扩展加载`（插件宿主）、`../08-会话存储RuntimeV2`（执行日志投影）。

---

## 1. 功能定位

DSH 式"执行服务"：后台作业、持久 PTY 终端与执行日志，独立于 chat / HTTP 生命周期（工具返回、本轮结束、浏览器断开都不再拥有其生命周期）。

## 2. UseCase

### UC-9F1 后台作业（run_shell 提升 / jump 管理）
- **触发**：`run_shell` 授权会话默认前台等待 30s；超时或显式 `run_in_background`；`job_output / job_list / job_kill`。
- **预期现象**：超时的前台进程提升为**可见作业**（job ID 返回）；显式后台立即返回 jobId；`job_output(wait)` 新输出消费（等待封顶 600s、超时不杀）；配额满时普通前台回退到有界旧路径、显式后台报配额错误；非零退出码是"完成结果"，启动/服务失败才是"失败作业"。
- **规则与边界**：每 Agent 10 个活跃作业；模型输出缓冲 256 KiB（完成后首次模型读取后降为 16 KiB）；脱离会话授权（无受信 session）的调用保留旧超时/杀进程行为且不能起无主后台任务；原始持久输出每资源 32 MiB 滚动、截断显式可见。
- **依据**：`execution_services/jobs.py`、`agent_tools.py`（工具接线）；回归 `tests/test_execution_services.py`、`tests/test_execution_api.py`。

### UC-9F2 持久 PTY 终端（terminal_* 四件套）
- **触发**：`terminal_open / terminal_send / terminal_read / terminal_signal / terminal_close / terminal_list`。
- **预期现象**：Windows=PowerShell、POSIX=Bash；send 保持 shell/REPL 状态（跨调用）；后台 send 是 `pty-send` 作业，其完成=等待收敛（`stdin_read / inferred_idle / timeout / session_exit`）；取消发送=Ctrl+C 且保留 shell；模型只管理自己 owner 的终端。
- **规则与边界**：每 owner 8 终端；160×40 模型视口；1 万行 / 4 MiB 文本预算内保留历史；读取结果 256 KiB、输入 64 KiB；**静默与超时不证明命令退出**（文档口径如此，工具说明照搬）；不支持的平台信号显式报错。
- **依据**：`execution_services/terminals.py`；前端 `terminal-runtime.js`（xterm）；回归 `tests/test_execution_services.py`（PTY 隔离/取消保留 shell）。

### UC-9F3 执行日志（execution_recorded / journal）
- **触发**：流式推理/回复/工具参数草稿/工具输出逐批到达。
- **预期现象**：`execution_recorded` 事件不依赖供应商消息模型保存"已接收"内容；稳定 `execution_id / process_group_id / turn_id / run_id / attempt_id / tool_call_id`；完整工具 ID 分派时是"草稿提升"而非新增行；增量批**先追加 JSONL journal 再发布**（不每 token 重写快照）；终态展示等待前序批；状态区分 generating / 等待执行·审批·输入 / running / completed / failed / timed out / interrupted / unknown；参数生成≠已执行；迟到增量只加输出、不重开终态。
- **依据**：`runtime_v2/execution_journal.py`、`event_schema / projector / ui_projection / versions`；回归 `tests/test_execution_recovery.py`、`tests/js/execution_recovery_runtime.cjs`。

### UC-9F4 执行恢复（重启顺序 / 显示兼容）
- **触发**：刷新/重启后历史快照携带 `execution_records` 重放。
- **预期现象**：以 `last_runtime_seq / projection_revision / projection_version` 播种；未 `ui_committed` 的记录按恢复渲染补行；重启顺序（历史行 vs 实时行）稳定；旧版本记录显示兼容（缺字段降级）。
- **依据**：`session-management.js`（快照播种）、`message-rendering.js`、`session-scroll-history.js`；回归 `tests/js/execution_restart_order_runtime.cjs`、`tests/js/execution_display_compat_runtime.cjs`、`tests/test_execution_restart_browser.py`。

### UC-9F5 computer-use 供应商（可选）
- **触发**：安装 `computer-use` 插件并配置。
- **预期现象**：插件拥有一个可选 Cua 提供商（截图/输入动作走其契约）；未安装/未配置时不可见且不影响既有工具面。
- **依据**：`plugins/computer-use/host.py`；回归 `tests/test_computer_use_provider.py`。

### UC-9F6 执行回执与证据链（投递≠生效，2026-10-05 补）
- **触发**：CUA 像素动作、终端 SIGINT/取消、后台 send 完成、工具结果状态判定。
- **预期现象**：所有"投递"型回执显示 DELIVERY ONLY 及原始验证状态；窗口动作可选 `_verify`（同 pid/window/session 检查，默认不返回图片、等 1s，仅稳定 satisfied 算完成）；CUA 状态 API 带 `recording_evidence`（policy_revision / control_tracked / acknowledged_enabled / owner / counter 下限）——本地控制证据而非缓存的"实时录制状态"；终端 SIGINT 回执区分 `delivered` / `interruptVerified` / `forced`（PTY Ctrl+C → 受控子进程终止兜底），无独立子进程的命令保留未确认（`no_owned_child_processes`）；后台 send 回执带 `completion_scope=terminal_send` + `command_state`（`inferred_idle`/`timeout` = 命令状态未知）。
- **规则与边界**：不伪造实时状态、不自动重放输入、不自动升级前台；截图 hash 不变不判"投递失败"；关键显示值以 `_verify` + 新截图双通道核对；工具结果截断/超时判定优先结构化字段（不扫描正文关键词）。
- **依据**：`execution_services/{computer,computer_policy,terminals}.py`、`plugins/computer-use/host.py`；回归 `tests/test_computer_use_feedback.py`、`tests/test_terminal_regressions.py`、`tests/test_tool_result_status_regressions.py`。

## 3. 边界

- 执行服务不替代会话授权与审批：受信 session 之外的工具调用仍走既有权限路径；
- 终端与作业是"资源"，其生命周期由 owner 停止/关闭驱动，浏览器断开不回收；
- 文档与工具说明沿用同一口径：静默/超时不证明命令退出，取消只到"发送等待终结"。

## 4. 版本记录

- 2026-10-05 v2：新增 UC-9F6《执行回执与证据链》——DELIVERY ONLY/`_verify`/`recording_evidence`/SIGINT 三级回执/`completion_scope`；同类修复见审查修复 changelog。
- 2026-10-04 v1：初版——UC-9F1（后台作业）、UC-9F2（持久 PTY）、UC-9F3（执行日志 journal）、UC-9F4（执行恢复）、UC-9F5（computer-use 可选供应商）。
