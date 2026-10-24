# Shell 执行器 · 功能方案设计（UseCase 清单）

- 版本：2026-10-23 v6（后台作业输出空轮询免写）
- 用途：逐条审查（四字段格式）。
- 适用实现：`app/agent_tools.py`（shell 选择/进程管理/物化/环境）、`app/execution_services/jobs.py`（作业输出与消费确认）。
- 上级：`00-工具系统整体设计.md`

---

## 1. 功能定位

`run_shell` 的全部工程细节：用哪个 shell、怎么管进程、长脚本怎么办、工作区限制怎么守。

## 2. UseCase

### UC-3C1 Shell 选择与降级
- **触发**：Windows 上调用 run_shell。
- **预期现象**：默认 PowerShell；检测到 Git Bash 时可用 Bash；POSIX 环境用 Bash；选择逻辑对用户透明。
- **规则与边界**：WSL 的系统 bash 会被识别与排除（避免路径语义混乱）；显式指定 shell 参数时以指定为准。
- **依据**：`_windows_bash_executable / _windows_powershell_executable / _run_cli_should_use_bash_on_windows / describe_run_shell_executor_for_prompt`。

### UC-3C2 进程树与作业对象
- **触发**：命令启动子进程；用户取消或超时。
- **预期现象**：Windows 下整棵进程被作业对象收拢；取消时**整树终止**（不留孤儿）；大输出不炸内存（流式摘要）。
- **依据**：`_assign_windows_run_shell_job / _close_windows_run_shell_job / _kill_process_tree`。

### UC-3C3 长脚本物化
- **触发**：`python -c` 超长脚本 / 复杂转义。
- **预期现象**：自动落盘为 `.run_shell_temp` 下脚本再执行；执行完清理（软删除进 .trash 体系）。
- **规则与边界**：仅在"值得物化"时触发（启发式判定），短命令保持内联；物化不改语义。
- **依据**：`_maybe_materialize_python_c_script / _unlink_run_shell_temp`。

### UC-3C4 工作区收窄
- **触发**：命令包含相对/绝对路径（含 `..`）、重定向、多命令链，或显式传入 `workdir`。
- **预期现象**：路径被抽取并检查是否在工作区（或已授权目录）内；**相对路径按 `workdir`（生效工作目录；未指定 = 工作区根）解析**，与命令执行语义一致，子目录里 `..` 回到工作区其他目录不误判越界；越界触发审批（受限模式），删除类红线维持强制单次；只读 git 命令有专门白名单。
- **规则与边界**：命令族级解析（head/grep/sed/dd/cd/重定向…）+ 正则兜底；Windows POSIX 路径误报有豁免逻辑；Windows 虚拟根 `/foo` 固定映射工作区根；含空格但未加引号的绝对路径保持保守判定；分类与 `required_dirs` 复核共用同一基准，避免二次判定反转。
- **依据**：`_resolve_shell_working_dir / _resolve_shell_token_for_workspace_restrict（base）/ _outside_workspace_tokens / _readonly_git_scope_ok / _windows_skip_posix_path_false_positive / security/runtime._effective_shell_base`。

### UC-3C5 环境与编码
- **触发**：子进程输出二进制/乱码；需要内置 Python。
- **预期现象**：二进制输出被摘要化（不喷终端）；编码解码健壮——UTF-8 严格优先，整段失败后按“行”在 UTF-8 / GBK 间择优（混合编码流两端都能正确显示，如 PowerShell 的 GBK 日期行不再变 `�`）；兜底只替换无法解码的字节；Windows PowerShell 执行器统一前置 UTF-8 I/O（PS 自有中文按 UTF-8 写出；原生命令输出含经 `Select-Object` 等管道按 UTF-8 读入；`Get-Content / Set-Content / Add-Content` 文件读写默认 UTF-8——消除「PS 中文 GBK 写出」「UTF-8 输出经管道被 GBK 误读（`✓`→`�?`）」「`Get-Content` 默认 ANSI 读 UTF-8 文本（`鐩綍绱㈠紩…`）」三类误码）；CLIXML 进度噪音被消除；内置 Python 目录自动前置（脚本可直接用）；stderr 有修复提示（如缺依赖给命令）。
- **规则与边界**：不以“结果含 U+FFFD”作为整套回退 GBK 的信号——合法 UTF-8 文本可自带 U+FFFD（历史误例：`B2 \"�\" ENDB` 曾被改写为 `B2 \"锟絓" ENDB`）；逐行 GBK 阈值（2026-10-11 放宽）：非 ASCII 字节中替换符 ≥2 且 ≥约 1/3 时启用（实测 PS 中文行 11/24 曾被漏判为 `���ٻع飨…`），仍高于“UTF-8 行个别坏字节”比例（如 1/13）不误改写；PowerShell UTF-8 前置可由 `RUN_SHELL_PS_UTF8=0` 关闭，代价是 GBK 工具（如 cmd 内建）输出“经管道”时会被按 UTF-8 误读（直连输出走字节透传不受影响）；文件编码默认值（`Get-Content / Set-Content / Add-Content` = UTF-8）随前置一并设置——BOM 文件仍按 BOM 优先（UTF-16 / UTF-8-BOM 读回正常），无 BOM 的 GBK/ANSI 文本需显式 `-Encoding Default`；`Out-File` / `>` 默认仍为 UTF-16（带 BOM，读回正常）；流式输出的切片安全见 09/07 UC-9F7。
- **依据**：`_decode_byte_line / _decode_cli_subprocess_bytes / _powershell_script_with_utf8_prelude / _summarize_shell_stream_if_binary_like / _run_shell_env_with_prepended_agent_python_dir / _run_cli_stderr_hints`；回归 `tests/test_decode_cli_subprocess_bytes.py`、`tests/test_run_shell_ps_utf8_prelude.py`。

### UC-3C6 作业输出只对实际消费变化提交
- **触发**：模型重复调用 `job_output` 查询已消费完或暂时无新输出的作业。
- **预期现象**：无新输出且消费/通知状态均未变化时直接返回，避免每次空轮询都提交扩展状态；产生新消费时仍等待持久化。
- **规则与边界**：比较消费游标、待交付结果、通知标记和保留缓冲起点；结束时缩小缓冲也计入变化。显式 offset 的观察读取仍不消费；wait=true 的主动等待、所有权、重启恢复与输出截断语义保持。
- **依据**：`app/execution_services/jobs.py:ExecutionService.output`；`tests/test_tool_efficiency.py`、`tests/test_execution_services.py`；[本批报告](../../performance/tool-efficiency-implementation-2026-10-23.md)。

## 3. 边界

- 中断检查回调（外部取消）由循环注入（`set_run_shell_interrupt_check`）。
- 命令行为细则（哪些算危险）见 02。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-3C1 | `agent_tools.py` L1777–1956 |
| UC-3C2 | L1665–1777 |
| UC-3C3 | L1478–1627 |
| UC-3C4 | L670–1454（路径收窄段，含 9-14 基准修复） |
| UC-3C5 | L1212–1373（解码链/环境）、L1623–1641（UTF-8 前置）、L2685–2695（EncodedCommand 组装）（2026-10-20 复核） |
| UC-3C6 | `execution_services/jobs.py:ExecutionService.output` |

## 5. 版本记录

- 2026-10-23 v6：job_output 无输出且消费状态不变时免写；保留真实消费确认、通知和缓冲边界提交。

- 2026-09-13 v1：拆分首版（承接 UC-306/307）。
- 2026-09-14 v2：UC-3C4 补充"相对路径按生效工作目录（workdir）解析"与只读 git/歧义输入边界（配合当日路径基准修复）。
- 2026-10-07 v3：UC-3C5 修订子进程输出解码链——移除“含 U+FFFD 即回退 GBK”的误判（曾把合法 UTF-8 改写为 GBK 误码“锟絓/閿熸枻鎷穃”类）；整段失败改为按行在 UTF-8 / GBK 间择优，兜底只替换无法解码的字节；新增回归 `tests/test_decode_cli_subprocess_bytes.py`（8 用例）；依据映射行号按当前工作区复核。
- 2026-10-11 v4：UC-3C5 双修复——①逐行 GBK 判据放宽至约 1/3（修复 `���ٻع飨…` 类漏判，+1 回归用例）；②Windows PowerShell 执行器统一 UTF-8 I/O 前置（`_powershell_script_with_utf8_prelude`，消除 PS 中文 GBK 写出与管道解码损伤，`RUN_SHELL_PS_UTF8=0` 可关，+回归 `tests/test_run_shell_ps_utf8_prelude.py`）；映射行号按当前工作区复核。
- 2026-10-20 v5：UC-3C5 追加 PowerShell 文件读写默认 UTF-8（`Get-Content / Set-Content / Add-Content`）——修复 `Get-Content` 默认 ANSI(936) 读取 UTF-8 无 BOM 文本产生 `鐩綍绱㈠紩…` 误码；BOM 文件仍按 BOM 优先（UTF-16/BOM 读回正常），无 BOM 的 GBK/ANSI 文本需显式 `-Encoding Default`；`Out-File`/`>` 默认值未改动；回归 6 个相关测试文件 110 passed。
