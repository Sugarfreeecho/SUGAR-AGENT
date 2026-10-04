# 2026-10-04 执行服务、执行日志与恢复链路（对齐 DSH）

## 一、执行服务（后端）

- 新增 `app/execution_services/**`：独立于 chat/HTTP 生命周期的执行资源服务——作业（jobs）、持久 PTY（terminals）、shell、computer、集成与通知；专用事件循环承载；工具返回 / 本轮结束 / 浏览器断开都不再回收这些资源。
- 模型工具扩展：`run_shell`（受信会话默认 30s 前台等待，超时提升为可见作业；显式后台立即返回 jobId；配额 10 个活跃作业，满额时普通前台回退有界旧路径）、`job_output / job_list / job_kill`（等待封顶 600s、超时不杀）、`terminal_open / send / read / signal / close / list`（8 终端、160×40 视口、1 万行/4 MiB 历史、256 KiB 读取、64 KiB 输入；取消发送=Ctrl+C 保留 shell；静默/超时不证明命令退出）。
- 插件：`execution-tools`（含会话面板）、`computer-use`（可选 Cua 提供商，未装不可见）。
- 依赖/构建：前端新增 `@xterm/xterm` + `@xterm/addon-fit`；`vite` dev 代理保持 changeOrigin=false。

## 二、执行日志与恢复（Runtime V2）

- 新增 `runtime_v2/execution_journal.py` 与 `execution_recorded` 事件：独立保存已接收 reasoning、回复文本、工具参数草稿与工具输出；稳定 `execution_id / process_group_id / turn_id / run_id / attempt_id / tool_call_id`；完整工具 ID 分派=草稿提升；增量批先追加 JSONL 再发布；终态等待前序批；状态区分 generating / 等待执行·审批·输入 / running / completed / failed / timed out / interrupted / unknown；迟到增量只加输出、不重开终态。
- `event_schema / projector / ui_projection / versions` 同步；`projection_revision / last_runtime_seq` 供前端播种。

## 三、前端（终端与恢复渲染）

- 新增 `terminal-runtime.js`（xterm 6 + fit addon）；`session-management` 快照播种 `execution_records` + `executionRecoveryBySession`；`message-rendering / sse-handling / event-dispatch` 支持执行行恢复与重启顺序；`smooth-stream / session-scroll-history` 联动（含流式行插入动画期间的释放与跟随）；`human-interactions` 适配执行中等待交互；公开侧栏窄态签名同步（避免流式期间整条重建）。

## 四、质量

- 新增测试：`test_execution_services / test_execution_api / test_execution_integration / test_execution_frontend / test_execution_recovery / test_execution_restart_browser / test_computer_use_provider` 与 3 个 JS 运行时（execution_recovery / restart_order / display_compat）；既有契约（feature_flags / stream_resilience / settings-center 注入 / PTY 计时容差）同步更新。
- 本批全量 `pytest`：**2101 passed / 5 skipped**；PTY 取消在 winpty 上存在 Ctrl+C 交付延迟——用例以"有界等待命令真正产出"覆盖两种收敛路径。

## 五、文件（主要）

- 后端：`app/execution_services/**`（新）、`app/runtime_v2/execution_journal.py`（新）、`app/agent_tools.py`、`app/agent_loop.py`、`app/webui.py`、`app/human_interaction/service.py`、`app/security/**`、`app/session_lifecycle.py`、`app/requirements.txt`；
- 插件：`plugins/execution-tools/**`（新）、`plugins/computer-use/**`（新）；
- 前端：`frontend/src/app/terminal-runtime.js`（新）、`modules/{message-rendering,sse-handling,event-dispatch,smooth-stream,session-scroll-history,session-management,human-interactions,public-sidebar}.js`、`package.json / package-lock.json`、`vite.config.js`、`app/templates/dist/**`（重建产物）；
- 文档：`docs/execution_services.md`、`docs/execution_recovery.md`（新）；`docs/steer_reliability.md` 更新；本 changelog。
