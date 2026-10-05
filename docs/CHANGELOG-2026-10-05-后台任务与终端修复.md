# 后台任务与持久终端反馈修复

> 后续真机复测：控制台辅助进程发 Ctrl+C 不能可靠中断命令，现已替换为 PTY Ctrl+C 加受控子进程终止兜底。无子进程的 shell cmdlet 保留未确认结果；下文原有辅助进程方案及验证范围属于历史记录。见 [CUA 录制与 SIGINT 复测修复](CHANGELOG-2026-10-05-CUA录制与SIGINT复测修复.md)。

针对会话 `d28caac2-9db8-4133-b32b-53c3a5ff5826` 的复核结果，已修复以下问题。保留 DSH 的 send 等待边界与原有工具参数，不重放原会话任务。

| 问题 | 修复与适配 |
|---|---|
| 空读误关 shell | pywinpty 返回空字符串时检查真实 EOF/存活状态，短暂退避后继续读取。读取异常、活进程上的传输 EOF、自然退出分别记录诊断；清理仍校验进程身份。 |
| SIGINT 只有写入回执 | Windows 改用独立隐藏辅助进程，校验 shell PID、创建时间和控制台成员后，只向该持久终端的私有控制台发 Ctrl+C。模型服务自身不附着目标控制台。 |
| 中断没有实际效果验证 | `delivered` 仅表示投递成功；新增 `interruptVerified` / `verification`。SIGINT 在最多两秒内观察新提示符与前台就绪。取消任务保存中断回执，未观察到就绪时明确保留未知状态，没有强制杀 shell 或重放命令的降级动作。 |
| 后台 send 被误当命令完成 | 结果、持久化 job 元数据、通知和界面增加 `completion_scope=terminal_send`、`command_state`、`terminal_id`。`inferred_idle`/`timeout` 明确表示命令状态未知；界面可直接跳转对应 Agent 终端读取后续输出。 |
| SStart-Sleep 等重绘噪声 | job 文本按屏幕最终行内容追加，覆盖绘制不再逐片拼接；部分行在观察结束时刷新。原始 PTY 流和终端视口仍持续保留。 |
| 模型终端环境与 DSH 不同 | 模型终端使用 `TERM=dumb`、`PAGER/GIT_PAGER=cat`、`NO_COLOR=1`；用户终端保留彩色交互。模型 PowerShell 额外禁用 PSReadLine，避免启动输入竞争和逐键重绘，并将初始提示符等待上限调整为十秒。 |
| 工具被错误标为截断/超时/失败 | 优先读取结构化结果字段；JSON 的 `truncated:false`、文件正文中的 `timeout`/`Error:`/`Exit code:` 不再被扫描为执行状态。真实退出码、错误诊断和截断标记保留。 |

Windows Ctrl+C 的进程组限制依据 [Microsoft GenerateConsoleCtrlEvent 文档](https://learn.microsoft.com/en-us/windows/console/generateconsolectrlevent)：CTRL_C 不能用非零组 ID 限定，因此辅助进程先核验私有控制台成员再投递。此路径是针对 Python/pywinpty 的平台适配；不能据此声称 DSH 的 node-pty 同样存在中断失败。

## 验证

两组测试共 **138 项通过**：

- `test_execution_services.py` 与 `test_terminal_regressions.py`：14 项。覆盖临时空读后的真实输出、自然退出/读取错误、进程身份与 owner 拒绝、模型/用户环境、重绘还原、信号投递但未就绪的未知回执，以及真实 PTY 场景。
- execution frontend/integration/API/recovery/restart、tool status/metrics/trace、shell self-protection/egress、tool-result truncation：124 项。

真实 PTY 场景断言：PowerShell 的 20 秒等待被取消后，同一 shell 在八秒内执行拼接得到的后续输出；外部 Python 的 20 秒睡眠被中断后不会打印其末尾标记，同一 shell PID 仍可复用。使用拼接输出标记，防止把命令回显当成实际执行。

另一个真实场景让命令静默五秒：job 在三秒静默后以 `inferred_idle` 结束，明确返回命令状态未知；迟到输出随后通过 `terminal_read` 读取。独立进程 job 的真实退出语义保持原样。

部署前检查了包含归档在内的 399 个会话：活动运行 0、活动 job/terminal 0、读取错误 0；在服务空闲时通过托盘完成重载。重载后服务就绪，新监听进程 PID 18388；Computer Use 仍为 ready、57 个工具；HTTP 提供的终端面板脚本与本地修复文件哈希一致。无需核心前端打包，本次 UI 改动由 execution-tools 插件资源直接提供。

## 边界

验证在本机 Windows 上进行；没有重新运行 DSH，也没有对 POSIX 作真实 PTY 验证。忽略 Ctrl+C 的程序、停留在 REPL 内的程序仍可能返回 `interruptVerified=false`，模型必须按回执继续观察。`shell_ready` 表示观察到 shell 就绪，不代表命令退出码为零。历史会话中的旧状态标签没有回写修改。
