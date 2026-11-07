# 常驻工具定义优化对照（2026-11）

> 范围：本会话实际下发的 37 个常驻工具（`OPENAI_TOOL_DEFINITIONS` + host/goal/team/terminal/web/workspace）。
> 口径：只统计 `function.description`；参数说明另列（§5）。
> **状态（2026-11-08）**：§2 的 20 条已全部落地，实测 `description` 合计 **14630 → 6659 字符**；下沉内容已写入 `sugar-agent-manual`（03-tools / 05-settings / 06-goal-hooks-mcp）。§5 参数层尚未改动。
> 现状：37 个工具 description 合计 **14630 字符**；按本稿改写后 **6659 字符**（-7971，约 -54%）。

## 1. 优化原则

1. **描述只答三件事**：何时用、做什么、关键边界。参数含义留在 schema，不重复。
2. **非普遍细节下沉**：平台差异、模态路由、后台提升、settings 跳转、示例流程 → `sugar-agent-manual`。
3. **一条一句**：删掉“注意/另外/同时”堆叠；能删的从句直接删。
4. **保留硬约束**：唯一调用、审批、禁区、原子失败、不可凭回执宣称完成。

## 2. 总览

| # | 工具 | 现描述 | 建议 | 变化 | 策略 |
| --- | --- | --- | --- | --- | --- |
| 1 | `task` | 2739 | 514 | -2225 | 下沉：图片模态路由、best-of-n、worktree、status/collect 语义、并行 scope 规则 |
| 2 | `run_shell` | 1728 | 476 | -1252 | 下沉：login shell、TEMP、二进制输出、后台提升规则 |
| 3 | `apply_patch` | 1048 | 381 | -667 | 精简：删掉参数名否定清单与语法教程 |
| 4 | `manage_scheduled_task` | 755 | 329 | -426 | 下沉：settings 页面跳转、runtime override 边界 |
| 5 | `read_file` | 745 | 300 | -445 | 精简：删掉模型模态说明与 end_line 兼容注记 |
| 6 | `show_user` | 664 | 337 | -327 | 下沉：History 不重放、notification provider 细节 |
| 7 | `terminal_signal` | 536 | 205 | -331 | 下沉：in-process 无法验证的处理建议 |
| 8 | `update_goal` | 528 | 238 | -290 | 精简 |
| 9 | `history_context` | 516 | 245 | -271 | 精简 |
| 10 | `write_file` | 511 | 222 | -289 | 精简：删掉 AGENT_DEFAULT_WRITE_FILENAME 变量名与重复路径解释 |
| 11 | `ask_user` | 488 | 267 | -221 | 精简：删掉 companion 描述与重复提示 |
| 12 | `grep` | 425 | 192 | -233 | 精简 |
| 13 | `delete_file` | 415 | 193 | -222 | 精简 |
| 14 | `switch_work_dir` | 332 | 225 | -107 | 精简 |
| 15 | `web_download` | 251 | 136 | -115 | 精简 |
| 16 | `context_manage` | 242 | 128 | -114 | 精简 |
| 17 | `scheduled_tasks` | 239 | 103 | -136 | 精简 |
| 18 | `tool_search` | 206 | 106 | -100 | 精简 |
| 19 | `ls` | 190 | 84 | -106 | 精简 |
| 20 | `web_search` | 190 | 96 | -94 | 精简 |
| 21 | `tool_call` | 182 | 182 | 0 | 保留 |
| 22 | `web_fetch` | 180 | 180 | 0 | 保留 |
| 23 | `terminal_send` | 160 | 160 | 0 | 保留 |
| 24 | `glob` | 142 | 142 | 0 | 保留 |
| 25 | `create_goal` | 136 | 136 | 0 | 保留 |
| 26 | `terminal_open` | 128 | 128 | 0 | 保留 |
| 27 | `team` | 117 | 117 | 0 | 保留 |
| 28 | `terminal_read` | 108 | 108 | 0 | 保留 |
| 29 | `update_todo` | 107 | 107 | 0 | 保留 |
| 30 | `terminal_list` | 100 | 100 | 0 | 保留 |
| 31 | `get_goal` | 97 | 97 | 0 | 保留 |
| 32 | `activate_skill` | 96 | 96 | 0 | 保留 |
| 33 | `tool_describe` | 88 | 88 | 0 | 保留 |
| 34 | `job_output` | 84 | 84 | 0 | 保留 |
| 35 | `terminal_close` | 62 | 62 | 0 | 保留 |
| 36 | `job_list` | 51 | 51 | 0 | 保留 |
| 37 | `job_kill` | 44 | 44 | 0 | 保留 |

---

## 3. 逐条对照（描述 ≥200 字符的 20 个）

### `task`

**现状（2739 字）**

```text
Delegate a bounded independent task to an isolated subagent, or manage an existing one. Use delegation when a subtask has a clear deliverable and can run independently; do not use it for a trivial step or when the parent must perform the work itself. A subagent does not receive parent chat or tool history, so every start/resume prompt must be a self-contained handoff. Foreground start/resume waits for the final result; background mode returns an ID immediately. Never use resume to poll or collect an existing result. Reading images the current model can see is a parent-side job: use `read_file` in-context when the current profile declares image input. When it does not, delegate the image instead: pass local paths or remote image URLs through file_attachments (it quotes local image paths automatically), and if the prompt itself references images, wrap each exact local image path in double quotes so it is detected reliably. Media is routed by the selected profile's effective input modalities: an image-capable profile receives image_url content prepared from durable attachments, while a text-only profile receives deterministic omission text and cannot inspect the image itself. When the user wants details of a subagent's execution process, ask that same existing subagent directly: resume the relevant resumable direct child in the foreground with focused questions and obtain its complete first-hand account. Do not infer process details from its final summary, and do not treat status or collect as a complete execution record. Reuse existing subagents before creating new ones: when a similar task may already have been delegated, call status without resume, then collect its result or resume that same direct child with a genuine follow-up. Use start only when no suitable subagent exists, the objective or scope is materially different, or deliberate independent parallelism is required. Do not create a duplicate merely because an existing subagent finished, needs clarification, or needs a correction. Parallel subagents must have independent, non-overlapping scopes; do not let them concurrently modify the same files or state. The parent remains responsible for inspecting evidence and changes, verifying results, deduplicating findings, resolving conflicts, and synthesizing the final answer instead of forwarding subagent output uncritically. Common patterns: use foreground explore for one read-only investigation; foreground generalPurpose for one implementation; several background explore runs followed by status/collect for independent parallel reviews; best-of-n-runner for genuinely different candidate solutions; readonly=true for strict local inspection; and resume with one ID only for a real follow-up.
```

**优化后（514 字）**

```text
Delegate a bounded, self-contained subtask to an isolated subagent, or manage an existing one. Start/resume with a self-contained handoff (objective, paths, constraints, acceptance); never assume it sees this chat. Foreground waits for the result; background returns an id. Reuse an existing subagent before starting a new one; resume only for a real follow-up, never to poll. The parent verifies evidence and synthesizes the answer. Modes, media and worktree details: sugar-agent-manual -> references/03-tools.md.
```

**处理**：下沉：图片模态路由、best-of-n、worktree、status/collect 语义、并行 scope 规则。

### `run_shell`

**现状（1728 字）**

```text
Execute a shell command on this host. **Syntax and backend follow the Environment line `Actual run_shell executor (this host)`** (Git Bash vs PowerShell vs sh). Default cwd is WORK_DIR unless `workdir` is set. `timeout_ms` is capped at **600000** ms. Bash uses a login shell by default; set `login=false` when startup profiles are unnecessary. In 请求批准/替我审批 modes, workspace commands run automatically while external paths, network access, destructive operations, and dynamically constructed code are routed through the central approval policy. Quote paths with spaces. Agent backend/tray PIDs and lifecycle scripts are protected: broad Python process termination is rejected, while terminating an explicitly selected unrelated PID remains allowed. Restart Agent only through the external platform tray or agentctl/RUN script. Virtual `/folder` under restriction means under the workspace root, not the OS root; avoid `cd /` expecting the workspace on Windows. Use write_file(temporary=true) and then execute its returned absolute path for throwaway scripts; long `python -c` payloads also use runtime scratch under global WORK_DIR/TempOutput. TEMP, TMP and TMPDIR point to that scratch; keep intermediate outputs there and requested deliverables in the project. Do not assume POSIX utilities exist on Windows—use Python when unsure. Binary-heavy output may be truncated or summarized. Set run_in_background=true to return a job_id immediately; use job_output/job_list/job_kill afterward. With execution-tools enabled, an authorized session command still running at timeout_ms is promoted to a background job. Use the canonical parameters command, workdir, timeout_ms, and login; do not send legacy args, working_dir, or timeout.
```

**优化后（476 字）**

```text
Run a shell command with this host's executor (see `## Environment`), cwd=WORK_DIR unless workdir is set; timeout <=600000 ms. Use run_in_background=true for long jobs (read with job_output). Outside-workspace paths, network and destructive commands go through approval; Agent lifecycle processes are protected. Write complex scripts with write_file(temporary=true) and run the returned path. Syntax, quoting and terminal details: sugar-agent-manual -> references/03-tools.md.
```

**处理**：下沉：login shell、TEMP、二进制输出、后台提升规则。

### `apply_patch`

**现状（1048 字）**

```text
Preferred tool for ordinary text-file modifications; use it instead of constructing file rewrites through run_shell. It accepts exactly one argument named `patch`; there are no `before`, `after`, `path`, `search`, or `replace` arguments. The patch string uses Codex patch syntax for one or more files. The tool has no built-in workspace containment limit: relative paths resolve from the runtime WORK_DIR and may use `..`, while native absolute paths (e.g. `D:/repo/src/a.py` or an absolute path returned by read_file) are allowed. In restricted permission modes, the central policy may prompt an approval card so the user can authorize the target directory before the change is applied. Read the target immediately before editing and copy exact existing lines into each update hunk. All file sections are validated before writing; stale, missing, malformed, or ambiguous context fails atomically without partial edits. If an update fails, re-read the reported file and rebuild the hunk from its current contents instead of retrying the same patch.
```

**优化后（381 字）**

```text
Edit text files with a Codex-style patch: exactly one argument `patch`, one or more file sections. Read the target first and copy exact context lines; malformed, stale or ambiguous hunks fail atomically without partial writes - re-read and rebuild the hunk. Paths resolve from WORK_DIR; absolute paths are allowed after approval. Prefer this over rewriting files through run_shell.
```

**处理**：精简：删掉参数名否定清单与语法教程。

### `manage_scheduled_task`

**现状（755 字）**

```text
Create or manage a backend-owned scheduled task (定时任务). Use when the user asks for a reminder, recurring work, or future agent action; do not create unsolicited schedules. Tasks appear in Settings > Scheduled tasks and survive closing chat. create requires name, instructions and trigger. Default target is this chat; new_chat creates a new chat each run in this workspace. update/pause/resume/delete require id and expected_revision from scheduled_tasks. run enqueues one manual execution without changing the normal schedule. Never report completion from an acceptance receipt. Runtime overrides cannot expand the caller's tools, budgets or authorization. After creation, show_user(kind='settings', section='schedules') can open the task page if useful.
```

**优化后（329 字）**

```text
Create or manage a scheduled task (定时任务); read existing ones with scheduled_tasks. create needs name/instructions/trigger; update/pause/resume/delete need id + expected_revision. Default target is this chat; new_chat starts a fresh chat per run. Never create unsolicited schedules or report completion from an acceptance receipt.
```

**处理**：下沉：settings 页面跳转、runtime override 边界。

### `read_file`

**现状（745 字）**

```text
Read a text file by line range, or view an image file (PNG/JPEG/WebP/GIF/BMP) directly — images are returned visually and larger ones are downscaled automatically (do not install image libraries or write converters); line-range parameters are ignored for images. Viewing an on-disk image is a normal in-context call of this tool; a model profile that does not declare image input gets an explanatory error instead. Text: virtual `/` under the workspace or an allowed OS-absolute path; use start_line plus line_count (default 200); legacy end_line remains accepted internally. Do not treat PDF/PPTX/spreadsheets/other binary as plain text—convert or probe with code first. Reuse exact paths returned by ls/glob/grep; do not guess path components.
```

**优化后（300 字）**

```text
Read a text file by line range (start_line + line_count, default 200) or view an image (PNG/JPEG/WebP/GIF/BMP; large images downscaled, line params ignored). Paths: virtual `/` or absolute. Convert PDF/PPTX/spreadsheets with code rather than reading them as text. Reuse exact paths from ls/glob/grep.
```

**处理**：精简：删掉模型模态说明与 end_line 兼容注记。

### `show_user`

**现状（664 字）**

```text
Present content or notify the user while continuing work. Companion to ask_user: does not wait for an answer; ask_user is for required choices. Kinds webpage, text, image, file and plugin open the details sidebar; notice shows a dismissible top banner; settings opens a specific settings tab without saving changes; notification requests a native system notification, including when the webpage is closed. History/replayed events never repeat these automatic actions. Notification delivery uses only the enabled desktop-notifications provider and returns requested/unavailable/failed/unknown; do not claim the user read it. Do not use it for every progress update.
```

**优化后（337 字）**

```text
Show reviewable content in the details sidebar (webpage/text/image/file/plugin), a top notice, a settings tab, or a system notification, without waiting for an answer. Use it for output worth seeing, not every progress update; success does not mean the user saw it or logged in. Kind limits: sugar-agent-manual -> references/03-tools.md.
```

**处理**：下沉：History 不重放、notification provider 细节。

### `terminal_signal`

**现状（536 字）**

```text
Signal the current foreground task. delivered alone does not prove interruption; inspect interruptVerified and terminal_read. On Windows SIGINT tries Ctrl+C, then may forcibly terminate the terminal's original owned child processes if its shell prompt does not return; forced=true identifies this fallback, which can end a REPL program. In-process shell commands with no child target can remain unverified; explicitly terminal_close to stop them. The shell itself is never killed by signal. Unsupported platform signals fail explicitly.
```

**优化后（205 字）**

```text
Signal the current foreground task. delivered != interrupted: check interruptVerified and terminal_read. On Windows SIGINT may force-kill child processes (forced=true). Unsupported signals fail explicitly.
```

**处理**：下沉：in-process 无法验证的处理建议。

### `update_goal`

**现状（528 字）**

```text
Use status=continue to resume an existing paused or blocked goal, like the play button, when the user asks to resume or a reported blocker has been resolved. Respect user-requested pauses; resume a manually paused goal only when the user asks. Supply additional_budget only when explicitly authorized by the user. Use completed to request independent Judge verification after the objective is achieved, or blocked to report a genuinely repeated blocker. Judge done moves the goal to human review; Judge continue keeps it active.
```

**优化后（238 字）**

```text
continue resumes a paused or blocked goal (only when the user asks); additional_budget only with explicit authorization. completed requests Judge verification; blocked reports a repeated blocker. Judge done moves the goal to human review.
```

**处理**：精简。

### `history_context`

**现状（516 字）**

```text
Search or read durable conversation history. Results are clean semantic text: storage metadata is hidden by default. Use scope=current first for facts from this session; use scope=global only when the user asks about another or any prior session. Search returns stable refs from compressed archives and events.jsonl; pass one ref to action=read for the exact bounded record. This is the preferred way to recover context that may have been compacted. Set include_source=true only when raw-file follow-up is necessary.
```

**优化后（245 字）**

```text
Search or read durable conversation history (compressed archives and events). Default scope=current; use global only for other sessions. Search returns refs; pass one to action=read. include_source=true only when raw-file inspection is required.
```

**处理**：精简。

### `write_file`

**现状（511 字）**

```text
Write UTF-8 text under WORK_DIR (virtual `/` maps to workspace root). Omit path to write AGENT_DEFAULT_WRITE_FILENAME (default output.txt). Otherwise use a relative path or `/segment` under WORK_DIR, or an absolute path already under WORK_DIR. Set temporary=true for throwaway scripts or intermediate files: the host redirects the name to the current run's scratch under global WORK_DIR/TempOutput, returns its actual absolute path, and removes it after execution. Use that returned path in subsequent commands.
```

**优化后（222 字）**

```text
Write UTF-8 text under WORK_DIR (virtual `/` = workspace root; omit path -> output.txt). temporary=true writes to TempOutput scratch, returns the real absolute path, and removes it after the run - use that path afterwards.
```

**处理**：精简：删掉 AGENT_DEFAULT_WRITE_FILENAME 变量名与重复路径解释。

### `ask_user`

**现状（488 字）**

```text
Pause the current run and ask the user one to four structured questions when an answer is genuinely required to continue. Use companion show_user to display content without waiting for an answer. Use repository and environment evidence first. Call ask_user as the only tool in the assistant turn; do not batch it with any other tool. Put the recommended option first and mark it in the label. The UI automatically provides an Other free-text choice, so never add an Other option yourself.
```

**优化后（267 字）**

```text
Ask 1-4 structured questions when an answer is required to continue; it must be the only tool call in the turn. Put the recommended option first; the UI adds an Other choice. Use show_user for content that needs no answer. Check repository/environment evidence first.
```

**处理**：精简：删掉 companion 描述与重复提示。

### `grep`

**现状（425 字）**

```text
Search text in files. Default mode=regex (supports |, ., *, +, ?, [], (), ^, $); use mode=fixed when you need to match literal text containing regex metacharacters. Path can be work area (default /) or an OS-absolute file/dir. Search the narrowest known source directory; avoid recursive repository-root searches when a relevant subtree is already known. Results stop as soon as max_results or the output byte cap is reached.
```

**优化后（192 字）**

```text
Search file contents: regex by default, mode=fixed for literal text. Scope to the smallest known directory; avoid repository-root recursion. Results stop at max_results or the output byte cap.
```

**处理**：精简。

### `delete_file`

**现状（415 字）**

```text
Soft-delete (move under WORK_DIR/.trash): a file or directory under the workspace (virtual `/` under WORK_DIR). Blocked: anything under `sessions/`, `skills/`, or `.trash/` (recycle). If total size exceeds TRASH_SIZE_WARN_MB (default 500MB), the tool refuses and does not move anything—user must delete manually. Use for cleaning temp clones etc.; shell `rm -rf` / `rmdir /s` are blocked by run_shell safety rules.
```

**优化后（193 字）**

```text
Soft-delete a file or directory by moving it to WORK_DIR/.trash. Refuses sessions/, skills/ and .trash/, and refuses when the batch exceeds TRASH_SIZE_WARN_MB. Shell rm -rf / rmdir are blocked.
```

**处理**：精简。

### `switch_work_dir`

**现状（332 字）**

```text
Switch this conversation's working directory after the user approves the exact target. Use an existing absolute directory. Subsequent file, shell, MCP and subagent calls use the new root; history and attachments stay in shared storage. Existing terminals/jobs keep their original cwd. Do not use shell cd to change the session root.
```

**优化后（225 字）**

```text
Switch this session's working directory after approval; the target must be an existing absolute directory. The new root applies to file/shell/MCP/subagent calls; terminals and jobs keep their cwd. Never use shell cd for this.
```

**处理**：精简。

### `web_download`

**现状（251 字）**

```text
Download a file from a public http(s) URL into WORK_DIR (binary-safe). Omit path to save using the URL filename under WORK_DIR (collision-safe rename). Same SSRF rules as web_fetch. Not a substitute for web_fetch when you only need readable page text.
```

**优化后（136 字）**

```text
Download a public http(s) URL into WORK_DIR (binary-safe, SSRF-guarded). Omit path to use the URL filename with a collision-safe rename.
```

**处理**：精简。

### `context_manage`

**现状（242 字）**

```text
Session context: mode compact summarizes and trims model history into the active runtime context. mode edit_key_context rewrites the active context summary according to edit_instruction (add/remove/fix key facts, errors, lessons, user rules).
```

**优化后（128 字）**

```text
Manage session context: compact summarizes and trims history; edit_key_context rewrites the active summary per edit_instruction.
```

**处理**：精简。

### `scheduled_tasks`

**现状（239 字）**

```text
Query durable scheduled tasks (定时任务) created by this chat/caller: list, get details, or execution history. These are the same tasks shown in Settings > Scheduled tasks. Read a task's revision before modifying it with manage_scheduled_task.
```

**优化后（103 字）**

```text
List, read, or inspect execution history of scheduled tasks; read a task's revision before updating it.
```

**处理**：精简。

### `tool_search`

**现状（206 字）**

```text
Find enabled external tools by task keywords. Use select:name1,name2 for exact names or +term for required words. Returns names and summaries; use tool_describe to obtain the complete schema before calling.
```

**优化后（106 字）**

```text
Find enabled external tools by keywords (`select:name` or `+term`); then use tool_describe for the schema.
```

**处理**：精简。

### `ls`

**现状（190 字）**

```text
List a directory (virtual `/` = workspace or an accessible OS path). Shows size; directory names end with /. Line counts are opt-in because calculating them opens every recognized text file.
```

**优化后（84 字）**

```text
List a directory (virtual `/` = workspace). Shows sizes; directory names end with /.
```

**处理**：精简。

### `web_search`

**现状（190 字）**

```text
Search the public web through the selected WEB_SEARCH_PROVIDER plugin. Provider-specific configuration and fallback behavior are owned by that plugin; disabling the plugin removes this tool.
```

**优化后（96 字）**

```text
Search the public web via the configured provider plugin; disabling the plugin removes the tool.
```

**处理**：精简。

---

## 4. 只做保留的工具

以下 17 个描述已 ≤200 字，信息密度合适，本轮不动：

`tool_call`（182）、`web_fetch`（180）、`terminal_send`（160）、`glob`（142）、`create_goal`（136）、`terminal_open`（128）、`team`（117）、`terminal_read`（108）、`update_todo`（107）、`terminal_list`（100）、`get_goal`（97）、`activate_skill`（96）、`tool_describe`（88）、`job_output`（84）、`terminal_close`（62）、`job_list`（51）、`job_kill`（44）。

---

## 5. 参数说明：第二优先

参数描述合计 15068 字符，前 6 个工具占大头：

| 工具 | 参数字符 | 主要问题 | 建议 |
| --- | --- | --- | --- |
| `task` | 7820 | `model_profile_id` 2469（运行时档案清单+取舍说明）、`action` 1439（10 个动作教程）、`prompt` 1004、`resume` 721 | 档案清单保留名字+标签，取舍规则下沉；action 每项压到一句；prompt/resume 合并为“自包含交接”一段 |
| `apply_patch` | 1471 | `patch` 讲完整语法与示例 | 保留语法骨架 + 一个最小示例，其余进 03-tools |
| `show_user` | 1339 | 8 种 kind 各一段 | 每种 kind 一句；限制进 03-tools |
| `manage_scheduled_task` | 759 | 15 个参数逐个解释 | 保留必填/联动说明，示例删 |
| `task.prompt` | 1004 | 交接模板重复 system prompt | 改为一句“自包含交接”，模板进技能 |
| `history_context` | 510 | scope/ref/include_source 三套说明 | 各一句 |

**改写样例（`task.model_profile_id`）**：

```text
当前可用档案（名字 — 适用场景，一句话）：{runtime_list}。默认省略；仅当任务明确匹配某档案能力（低成本并发、高难推理、长上下文）时选择，不要因为“有档案”就选。
```

---

## 6. 下沉清单

| 原内容 | 去向 |
| --- | --- |
| task：图片模态路由、best-of-n、worktree、status/collect、并行 scope | `03-tools.md` §1「Goal 与子代理」扩写 |
| run_shell：login shell、TEMP、二进制截断、后台提升 | `03-tools.md` §1「Shell、后台任务与终端」 |
| show_user：History 不重放、notification provider 状态 | `03-tools.md` §6「show_user」 |
| manage_scheduled_task：设置页跳转、runtime override | `05-settings.md` 定时任务小节 |
| update_goal：Judge 语义 | `06-goal-hooks-mcp.md` Goal 小节 |
| apply_patch：补丁语法与失败重建 | `03-tools.md` §1 文件工具 |

---

## 7. 收益与风险

- description：14630 → 6659 字符（-7971），每轮请求都省。
- 工具定义整体（含参数 schema）约 10561 token；description 占比从 49% 降到约 22%。
- 参数说明若按 §5 执行，预计再省 3000–4000 字符。
- 风险：删过头会让模型选错工具或漏掉唯一调用/审批约束；本稿逐条保留了这类硬约束，参数 schema 完全不动。
- 未动：工具名、参数名、类型、枚举、必填项——只改文字。
