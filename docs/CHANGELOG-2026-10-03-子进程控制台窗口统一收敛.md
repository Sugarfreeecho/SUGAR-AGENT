# 隐藏子进程控制台窗口：统一收敛（2026-10-03）

把"桌面黑框一闪"的修复从散点补丁收敛为一处：`app/proc_flags.py`，并对全仓派生点做了一次审计与接线。

## 根因与实测结论

- 后端在**没有可继承控制台**的形态下运行时（`pythonw.exe` 或 `DETACHED_PROCESS`），任何未加
  `CREATE_NO_WINDOW` 的控制台子系统子进程（`git` / `cmd` / `powershell` / `taskkill` / `pip`…）
  都会被 Windows 新建一个**可见**控制台窗口。
- 进程内实测（本机）：由无控制台进程派生未加标志的 `git` → 每次派生都新建终端宿主窗口
  （本机默认终端为 Windows Terminal，表现为 `CASCADIA_HOSTING_WINDOW_CLASS` + `PseudoConsoleWindow`）；
  同一命令加 `CREATE_NO_WINDOW` → 新建窗口 **0**。
- 反向实测：`pythonw → python.exe + CREATE_NO_WINDOW → git(未加标志)` 新建窗口 **0**，
  因为 `python.exe` 已经带一个无窗口控制台，子进程继承它。**也就是说托盘正常启动的会话里，
  后端派生点多为空转**；本改动的真实收益在"无控制台调用方"（托盘/更新/直接 `pythonw` 启动、
  `agentctl`、WebUI 触发的重启链路）以及防止未来新增调用点再漏。

## 改动清单

| 文件 | 内容 |
| --- | --- |
| `app/proc_flags.py`（新增） | `NO_WINDOW` / `NEW_PROCESS_GROUP` 常量、`hidden_flags()`、`console_attached()`、`inherit_or_hide_flags()`。非 Windows 全部取 0，可无脑使用。 |
| `app/agent_tools.py` | `_kill_process_tree` 的 `taskkill` 加标志；`_run_cli_subprocess_stdio_kwargs`（`run_shell`/`rg` 共用）改用统一 helper，保留 `RUN_CLI_NO_WINDOW` 开关语义。 |
| `app/agent_subagent.py` | 子代理 worktree 的 8 处 `git` 调用全部加标志。 |
| `app/runtime_observability.py` | `_git_output`（文件审计）加标志。 |
| `app/webui.py` | 技能安装的 `git clone` 加标志。 |
| `app/path_picker_util.py` | Windows PowerShell 文件选择器加标志（WinForms 对话框不受影响）。 |
| `app/plugins/installer.py` / `app/plugins/runtime.py` | 插件依赖安装（pip 等）与插件 worker 进程加标志。 |
| `app/hooks/executor.py` | Hook 命令的 `taskkill`（Windows 分支）与 shell 派生统一走 helper。 |
| `app/security/egress_guard.py` / `app/desktop_notify.py` | 出网助手健康检查、Windows 通知脚本改用统一常量。 |
| `app/tray_launcher.py` | 7 处 `subprocess.CREATE_NO_WINDOW` 收敛到常量；后端主进程启动改为 `hidden_flags(new_process_group=True)`。 |
| `app/agent_updater.py` | 更新时的 `git`/`pip`（输出经 PIPE 收集进 UpdateLog）加标志。 |
| `app/platform_lifecycle.py` | `RUN.bat` 启动改为**自适应**：调用方自己有控制台就继承（照旧可见），没有控制台才隐藏，并把 stdout/stderr 追加到 `logs/launcher_console.log`，同时把 stdin 指向 `DEVNULL`（避免隐藏窗口后 `pause`/`input` 把进程挂住）。 |
| `plugins/change-review/store.py` | `_git_inventory` 加标志；新增 `_has_git_repository()` 快路径：非 git 工作区直接返回 `None`，不再每次捕获都空跑一次 `git`（含上游无 `.git` 的情况）。 |
| `scripts/audit_subprocess_flags.py`（新增） | AST 巡检 `app/`、`plugins/` 的派生点是否声明 `creationflags`；豁免项集中在 `ALLOWED` 表并写明原因。未覆盖点非零即退出 1。 |
| `tests/test_proc_flags.py`（新增） | helper 语义 + `console_attached()` 不抛异常 + **巡检脚本回归**（新增未覆盖派生点会直接失败）。 |
| `tests/test_change_review_plugin.py` | 补 `.git` 祖先探测与"非 git 工作区不 spawn git"两个用例。 |

## 验证

- `python -m py_compile`：18 个改动文件全部通过。
- `scripts/audit_subprocess_flags.py`：**未覆盖派生点 0**，豁免 32 处（均注明原因：macOS/Linux 分支、`**kwargs` 构造、CLI/更新等自带可见控制台、`CREATE_NEW_CONSOLE`/`DETACHED_PROCESS` 等有意行为）。
- 相关回归：`pytest tests/test_proc_flags.py tests/test_change_review_plugin.py tests/test_desktop_notify.py tests/test_platform_lifecycle.py tests/test_path_picker_platforms.py tests/test_egress_guard.py tests/test_tray_launcher.py tests/test_hooks_core.py tests/test_plugin_host_services.py tests/test_runtime_observability_shared.py tests/test_agent_tools_performance_paths.py` → **184 passed**（196.97s）。
- 全量回归：`python -m pytest tests -q` → **1986 passed, 4 skipped**（166.11s）。
- `git diff --check`（改动文件范围）无错误；新增文件为 LF 且以换行结尾。

## 复核边界

- 本机是自动化会话，**无法在交互桌面上目视确认"黑框"**；证据是窗口对象级计数（无标志会新建终端宿主窗口，加标志为 0），不是肉眼复现。
- `console_attached()` 在 ConPTY 终端下可能返回 `False`（本机 `GetConsoleWindow()` 与标准句柄探测在部分形态下都取不到），此时 `RUN.bat` 按"无控制台"处理：隐藏窗口 + 输出落日志。有独立控制台（经典 conhost，或 stdout 未重定向的终端）时保持原来的可见输出。
- 之前引用的 `sugaragent_console_window_fix.patch`（8 文件 / 15 调用点）已被本批改动覆盖：同样位置都接了标志，另外补了 `agent_updater`、`tray_launcher` 统一常量、以及巡检与测试；`platform_lifecycle` 采用自适应而非无条件隐藏。
- 改动在内存中，需**重启 Agent** 后生效。
