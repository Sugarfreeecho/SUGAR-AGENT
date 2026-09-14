# Shell 执行器 · 功能方案设计（UseCase 清单）

- 版本：2026-09-14 v2（覆盖至：HEAD `d022831` + 9-14 路径基准修复）
- 用途：逐条审查（四字段格式）。
- 适用实现：`app/agent_tools.py`（L574–2331：shell 选择/进程管理/物化/环境）。
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
- **预期现象**：二进制输出被摘要化（不喷终端）；编码解码健壮；内置 Python 目录自动前置（脚本可直接用）；stderr 有修复提示（如缺依赖给命令）。
- **依据**：`_decode_cli_subprocess_bytes / _summarize_shell_stream_if_binary_like / _run_shell_env_with_prepended_agent_python_dir / _run_cli_stderr_hints`。

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
| UC-3C5 | L1084–1236、L1854–1928 |

## 5. 版本记录

- 2026-09-13 v1：拆分首版（承接 UC-306/307）。
- 2026-09-14 v2：UC-3C4 补充"相对路径按生效工作目录（workdir）解析"与只读 git/歧义输入边界（配合当日路径基准修复）。
