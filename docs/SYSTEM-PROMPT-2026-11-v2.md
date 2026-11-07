# System Prompt 修订提案（v2，2026-11）

> **基线**：`docs/SYSTEM-PROMPT-2026-11.md`（现状快照与诊断）。
> **状态（2026-11-07）**：§2/§3 已合入 `app/prompt.md` 与 `app/prompt.en.md`；§6 已写入技能参考；§5 环境块中文化已改代码，**需重启生效**。下方原文保留，便于对照与回滚。
> **当前实际文本**：见 [SYSTEM-PROMPT-2026-11-v3.md](SYSTEM-PROMPT-2026-11-v3.md)（2026-11-08 快照）。
> **replace 语义（2026-11-08 修正）**：只替换第 1 段角色原则，工具契约/技能目录/环境保留；本文档 §1.1、§5.3 里“丢弃段 1–3 / 精简环境”的描述已过时。
> **三处改动**：① 临时文件段从 `system_skills_intro` 移除并并入工具契约；② 环境块中文版；③ 工具契约 21 条重写为 10 条，场景细则下沉到 `sugar-agent-manual` 技能。

## 0. 结论速览

| # | 问题 | 结论 | 动作 |
| --- | --- | --- | --- |
| 1 | 临时文件段为何在 `system_skills_intro` | 是 2026-10-25 提交 `e1831d3` 里**重复写入**的人工文本，不是装配逻辑 | 并入工具契约第 9 条，删除技能段副本 |
| 2 | 环境块英文 | 可译为中文；但有 3 处机器依赖不能动 | 给中文全文，`## Environment` 等片段保持原样 |
| 3 | 工具契约 21 条 | 收敛为 10 条通用规则；参数级细节交给工具 schema，场景做法交给技能 | 给替换块 + 21→10 迁移对照 |

---

## 1. 问题 1：它为什么会在 `system_skills_intro` 里

### 1.1 装配侧没有注入这段文字

`system_skills_intro` 是**逐字**读取的：`load_prompt_template("system_skills_intro")` 取 `## system_skills_intro` 到下一个 `## ` 之间的原文，唯一处理是 `.format(skills_catalog=...)`（`app/agent_tokenizer.py:1072-1073`）。代码没有拼接、也没有插入临时文件规则。

### 1.2 历史提交显示是同一次提交里写重了

`git show e1831d3 -- app/prompt.md` 的 diff 同时出现两处新增：

```diff
 ## system_tool_contract
+- 文件组织：源码修改与最终交付文件按用户指定的项目目录组织；多文件交付先创建以任务名命名的子目录…… 一次性脚本、中间数据和转换文件使用运行时 scratch（write_file temporary=true 或 Shell 的 TEMP/TMP/TMPDIR）……
 
 ## system_skills_intro
+一次性脚本和中间文件使用 `write_file(temporary=true)`，后续操作采用工具返回的实际绝对路径。Shell 中通过 `TEMP`、`TMP` 或 `TMPDIR` 使用运行时 scratch；这些目录统一位于全局默认工作目录的 `TempOutput`，不会跟随当前项目改变。最终交付文件和源码修改写入项目。不要把临时文件写到项目后再移入回收站。
+
 需要某技能的具体规程时，调用 `activate_skill`。
```

同一个提交（`docs(review): record verified fixes and the grouped delivery`，2026-10-25）把「文件组织」条改写为包含 scratch，又把同一件事的更详细版本加到了技能段开头。属于**重复沉淀**，不是设计意图。

### 1.3 语义上也不属于技能段

- 技能段的职责只有一个：告诉模型「何时 `activate_skill`」+ 给出目录。
- 该段几条规则（临时文件走 scratch、`TEMP/TMP/TMPDIR` 位置、交付物进项目、不落项目再回收）全部是文件组织规则，与技能无关。
- 模型收到的效果是：同一主题出现两条措辞略不同的规则（契约末条 + 技能段首段），改一条忘另一条就会自相矛盾。

### 1.4 建议：合并，而不是「搬一条新的」

> 原契约末条已含「一次性脚本用 scratch」，但没写清 `TempOutput` 位置和「不要落项目再回收」；技能段这段更准确。
> 正确做法是把技能段的精确表述**并进第 9 条**，然后删除技能段这一段——而不是在契约里再加一条，否则重复依旧。

这一处理已体现在 §3 的第 9 条和 §2 的新版技能段中。

---

## 2. 新版 `system_skills_intro`

整段替换为（`{skills_catalog}` 保留）：

```text
技能是给 Agent 的说明与资源，不会自动执行。需要某技能的具体规程时，调用 `activate_skill` 加载。

技能目录见下：
{skills_catalog}
```

- 245 字 → 86 字；去掉与工具契约重复的文件规则。
- 「不会自动执行」一句来自 `sugar-agent-manual` 的安全边界，用来防止模型把「有技能」当成「有能力执行」。
- `{skills_catalog}` 仍由 `get_skills_catalog()` 注入，`.format()` 约束不变（新增花括号要写 `{{ }}`）。

---

## 3. 新版 `system_tool_contract`（10 条）

整段替换为：

```text
工具的参数与边界以工具定义为准；以下是跨工具的行为约定。

1. **意图先行**：调用前用一句话说明要做什么、为什么；不预先声称结果。
2. **先读后写，写后必验**：改文件前用 `read_file`/`grep` 确认现状；写入或编辑后运行相关命令，或读回改动点确认目标内容已生效；无法验证时说明原因。
3. **路径与搜索**：复用 `ls`/`glob`/`grep`/`read_file` 返回的完整路径，不凭记忆拼路径；搜索限定在已知最小目录，除非确有必要不从仓库根全量递归。
4. **批量与顺序**：参数已确定的多个调用写进同一条消息；只读工具并行，`write_file`/`apply_patch`/`run_shell` 等有副作用的按原顺序串行；只有后一条依赖前一条结果时才分轮，不猜参数。
5. **不重复、不空转**：同一目标、同一参数的调用不重复；失败先定位原因（参数、路径、权限、环境），再换方案，不原样重试。
6. **依赖与环境**：运行前用 `run_shell` 做轻量探测；未经用户同意不 `pip install`、不改系统级环境；缺依赖时说明原因并给出命令，能用现有方案就不装。
7. **重启**：需要加载后端代码或配置改动时，单独调用 `request_restart`，说明原因、已完成的改动与验证、重启后要做什么；等用户确认，被拒后不再重复。返回已授权只代表已排队，恢复后先核对重启回执再验证；不得通过 Shell 启动生命周期脚本或终止 Agent。
8. **用户交互**：只在继续执行确实依赖用户选择、且无法从仓库或环境推断时调用 `ask_user`，它必须是该条消息唯一的工具调用；`show_user` 用于展示可看的产出，不刷进度；展示或通知请求成功不代表用户已看到或已登录。
9. **文件与交付**：源码与交付物放在项目内，多文件先建任务子目录；一次性脚本与中间产物用 `write_file(temporary=true)` 或 `TEMP`/`TMP`/`TMPDIR`（统一在 `TempOutput`，不随项目），不写进项目再回收；新建交付物遇到同名递增 `_v2`/`_v3`，源码与配置原地改；工作区外文件可直接用绝对路径修改，审批与禁区按策略执行。
10. **收尾与记忆**：结束前用 `update_todo` 把剩余项标为完成；涉及可能被压缩的历史先用 `history_context`（默认 `scope=current`，跨会话才用 `global`），不凭摘要猜测。
```

2989 字 → 1086 字（约 -64%），规则从 21 条降到 10 条。

### 3.1 为什么这样能保住行为

| 原来担心的丢失 | 实际兜底 |
| --- | --- |
| `ask_user` 的 1–4 问、选项数、推荐置首、前端自带 Other | 工具 schema 已写明（`app/agent_tools.py:4617`），模型每次请求都能看到 |
| `show_user` 的 8 种 kind 与「不代表已读」 | schema 描述已列全 kind 与「do not claim the user read it」 |
| `ask_user` 必须是唯一调用 | 既是 schema 文案，也保留在新第 8 条（硬约束不下沉） |
| `request_restart` 单独调用、授权≠成功 | 保留在新第 7 条（硬约束不下沉） |
| 图片/二维码、同名递增、绝对路径审批、历史检索参数 | 下沉到技能（§6），需要时按需加载 |

### 3.2 每条只做一件事

原 21 条里有多条是「一个 bullet 塞多件事」（`show_user` 一条 480 字）。新版一条一个主题、动词开头，冲突时能单独定位。

---

## 4. 迁移对照：21 条去哪了

| 原 # | 原规则（摘要） | 现在 |
| --- | --- | --- |
| 1 | `request_restart` 流程、授权≠成功 | 新 7 |
| 2 | 不重复调用同一工具 | 新 5 |
| 3 | 先读后写 | 新 2 |
| 4 | 写入/编辑后验证 | 新 2（给出验证标准） |
| 5 | 工具失败先分析 | 新 5 |
| 6 | 路径复用、搜索限定最小目录 | 新 3 |
| 7 | 依赖与环境 | 新 6 |
| 8 | 调用前明确意图 | 新 1 |
| 9 | 截图/看图 | §6 技能 · 图片与截图（`read_file` schema 已声明支持图片） |
| 10 | `ask_user` 判定 + 格式 | 新 8（判定）+ §6 技能（格式） |
| 11 | `ask_user` 唯一调用 | 新 8 |
| 12 | `show_user` 全套 | 新 8（原则）+ §6 技能（kinds 表） |
| 13 | `ask_user` images / 二维码 | §6 技能 · ask_user |
| 14 | todo 收尾 | 新 10 |
| 15 | 工作区外绝对路径修改 | 新 9（一句）+ §6 技能（审批与禁区） |
| 16 | 同名文件递增 | 新 9（改为只管新建交付物）+ §6 技能 |
| 17 | `history_context` | 新 10（入口）+ §6 技能（参数） |
| 18 | 批量生成 `tool_calls` | 新 4 |
| 19 | 执行顺序（只读并行/副作用串行） | 新 4 |
| 20 | 依赖例外（不猜参数） | 新 4 |
| 21 | 文件组织 | 新 9（并吸收技能段那段 scratch 说明） |

无遗漏；差异只有「表述合并」与「下沉到技能」。

---

## 5. 环境块中文版

> **注**：本节是第一轮的完整译稿（保留作参考）。2026-11-07 二次瘦身后，运行时实际输出已缩减为 760 字（中文）/ 1017 字符（英文），迁出映射见 §8。

### 5.1 三处机器依赖，翻译时不能动

| 片段 | 谁在依赖 | 后果 |
| --- | --- | --- |
| `## Environment` 标题 | `session_system_context.py:72` 用它定位并替换 fork 继承的环境段；`tests/test_session_system_context.py:202` 断言 `startswith("## Environment")` | 标题一改，fork 会话会重复叠加环境段，测试直接红 |
| ``(`WORK_DIR`):`` 与 ``(`AGENT_PROJECT_ROOT`):`` 的 ASCII 括号和冒号 | `tests/test_session_workspace_paths.py:97,311` 用 `f"(`WORK_DIR`): {path}"` 断言 | 换成全角括号 `（）` 或中文冒号会断测试 |
| 精简版不出现 `run_shell` 字样 | `tests/test_session_system_context.py:203` 断言 | 精简版里提到 `run_shell` 会断测试 |

其余正文（字段名、说明句）都可以译。

### 5.2 完整版（中文，逐字）

```text
## Environment
- **当前月份（宿主本地时间）**：**{YYYY-MM}**
- **操作系统**：{OS} | **Python**：{python_version}
{执行器行，见 5.4}
- **MCP 扩展**（可选）：通过 `.config/mcp_servers.json`（或环境变量 `MCP_SERVERS_JSON`）配置，或在 **设置 → 进阶设置 → MCP 配置** 中保存后，每个服务器配置都需要人工确认一次注册才会连接。工具默认使用本地名；只有重名时才加插件或服务器前缀。请使用当前工具目录里的准确名称。调用时遵循当前全局权限模式与中央 `allow/ask/deny` 策略。
- **运行时输出**：`{TempOutput}` 跨会话共享，不随当前项目变化。一次性脚本用 `write_file(temporary=true)` 创建，之后使用它返回的绝对路径。`run_shell` 保持项目 cwd；`TEMP`、`TMP`、`TMPDIR` 指向其运行时 scratch，用于存放中间产物。交付文件请放在项目内。完整工具结果保留在 `TempOutput/tool-results`，需要时可按历史回读。
- **Agent 项目根** (`AGENT_PROJECT_ROOT`): {proj}
  - 这是 Agent 应用自身的源码树与项目级配置根，包含 `app/agent_loop.py`、`app/agent_tools.py`、`app/agent_harness.py`、`app/agent_tokenizer.py`、`app/prompt.md`、`.config/mcp_servers.json` 等文件。
  - 用户询问「你」的功能、机制、配置、工具行为、提示词行为，或要求你自查时，先读这个根目录下的相关代码，再根据实际行为回答。
- **工作根** (`WORK_DIR`): {wdir}
  - 需要切换本会话根目录时用 `switch_work_dir`（需用户批准），目标必须是已存在的绝对目录。之后的文件、Shell、MCP 与子代理调用都以新根为准；已打开的终端与后台任务保留原 cwd。Shell 里的 `cd` 只影响该次操作。
  - 全局默认与共享数据根：{shared_root}。会话与附件都留在这个共享根下。
  - 虚拟 `/` 映射到该目录；`/outputs/a.txt` 这类虚拟路径按 `WORK_DIR` 解析。
  - `write_file`、`apply_patch`、`edit_file`、`web_download`、`delete_file`（软删除目标 `WORK_DIR/.trash/`）与受限模式下的 `run_shell` 都按这棵树解析相对路径；**WORK_DIR 之外的原生绝对路径可以使用**，受限模式下需用户在审批卡中授权目标目录（完全访问模式直接允许）。
  - `delete_file` 拒绝 `sessions/`、`skills/`、`.trash/` 及其子项。

## This conversation's storage
- **会话存储目录**：{sdir}
  - Runtime V2 正典存储路径：`{v_session}`。该共享存储可能不在当前项目内。
  - 正典事实与可重建状态位于 `events.jsonl`、`snapshots/latest.json`、metadata、索引与引用 blob。旧版 `llm_history.json`、`ui_events.json`、`key_context.md`、`todo_plan.md` 可能缺失或已过期，不能作为上下文权威。
  - 服务端会注入当前模型上下文与摘要。显式压缩或摘要编辑用 `context_manage`，实时计划用 `update_todo`；不要直接编辑 Runtime V2 存储文件。
  - 需要更早的可见历史时，使用会话历史 API/UI。
```

> 标题 `## Environment` 与 `## This conversation's storage` 建议保留英文（前者是代码依赖，后者保持一致）；正文全部中文。

### 5.3 精简版（`replace` 模式，`minimal=True`）

```text
## Environment
- 当前月份（宿主本地时间）：{YYYY-MM}
- 操作系统：{OS}
- 会话 ID：{sid}（未落盘时为空）
- 工作根：{work_root}
- 只有当前工具目录中的工具可用；权限由宿主强制执行。
```

### 5.4 执行器行（按主机四种分支）

```text
# PowerShell（当前主机）
- **run_shell 实际执行器（本机）**：**PowerShell** — `{path}`（`-EncodedCommand`，UTF-16LE Base64；**不经过 cmd.exe**）。**未使用 Git Bash**（未安装、`RUN_SHELL_BASH` 未解析或 `RUN_SHELL_USE_BASH=0`）。命令用 **PowerShell** 语法（管道 `|`；多条语句用 `;`）；**不要假设**有 Bash/POSIX 的 `&&`/`||`、`wc`/`head` 等，不确定时优先用 **Python**。**双引号里的 `$` 会被 PowerShell 展开**（如 `$?`）；复杂脚本先 `write_file` 一个 `.py` 再 `python ...`。含空格的路径加引号。**超时上限 600 秒**。

# Git Bash / bash
- **run_shell 实际执行器（本机）**：**Git Bash / bash** — `{path}`（`bash -lc` 或 `-c`，内部 `eval` + POSIX `shlex.quote`）。**不是** CMD，不要把裸 CMD 语法（如 `dir /s /b`）粘进 Bash（必要时用 `cmd /c "..."`）。**不要假设** `wc`/`head`/`grep` 在 PATH 上，没有就用 **Python**。含空格的路径加引号。**超时上限 600 秒**。

# sh
- **run_shell 实际执行器（本机）**：**sh** — `{path}`（`sh -c` + `eval`；未使用 bash 或 `RUN_SHELL_USE_BASH=0`）。**超时上限 600 秒**。

# 两者都没有
- **run_shell 实际执行器（本机）**：**不可用** — 未找到 Git Bash 或 PowerShell，安装其中之一前 `run_shell` 会失败。
```

### 5.5 落地方式

- `build_env_static(session_id=None, *, minimal=False, language="zh-CN")`：中文会话走中文块，英文会话保留现有英文块。
- 调用点 3 处：`app/agent_loop.py:2315`（`_build_static_segments_for_session`）、`app/agent_tokenizer.py:1106`（`build_session_system_segments`）、`app/agent_loop.py:2356`（预热，可传 `prompt_language`）。
- `describe_run_shell_executor_for_prompt()` 增加中文变体（`app/agent_tools.py:2180`），否则中文块里会夹一行英文。
- 已实施：两个函数都加了 `language` 分支，3 个调用点已传 `prompt_language`。**需重启**才生效；`pytest`（短 `TMP`）58 passed。

---

## 6. 下沉到技能的细则（可直接粘贴）

目标文件：`workspace/skills/sugar-agent-manual/references/03-tools.md`。**已写入为第 6 节**（原「相关文档」顺延为第 7 节）。该文件已覆盖「有哪些工具、参数怎么填、为什么被拒」，是这些细则的自然落点；其中第 4 节已讲临时文件与 `TempOutput`，下面的「文件与路径」只补同名与工作区外两类，不重复。

```markdown
## 6. 工具使用细则（场景做法）

> 场景化做法在此；硬约束（`ask_user` 唯一调用、`request_restart` 单独调用、审批与禁区）仍以 system prompt 与工具定义为准。

### ask_user

- 一次 1–4 个问题，每题 2–4 个互斥选项；推荐项放第一并在标签里注明。
- 前端会自动提供「其他」，不要自己加 Other 选项。
- 必须是该条 assistant 消息里唯一的工具调用，不能和读取、Shell、MCP 等批量发出。
- 问题正文与 preview 都是纯文本：不要塞 Markdown 图片，不要编造 Base64。
- 图片/二维码：先用 `read_file` 拿到 `attachmentId` 作为 `attachment_id`，或用工具真实返回的 `data_url`；单张 ≤2 MiB，单次 ≤8 MiB、≤4 张。
- 扫码登录：给出「已扫码 / 二维码失效 / 取消」等选项；用户说已扫码后要实际核验登录态，失效就重发新码与新问题。

### show_user

| kind | 行为 |
|---|---|
| `webpage` | 详情栏打开 URL（含本机开发服务），URL 不要带凭据 |
| `text` | 详情栏展示文本/Markdown |
| `image` | 详情栏展示图片（`attachment_id` 与 `data_url` 二选一） |
| `file` | 展示任意本地文件；绝对路径可超出工作区，相对路径按会话工作目录解析；不需要读文件审批，也不回传正文 |
| `plugin` | 打开已启用插件的声明页面 |
| `notice` | 顶部提示条，默认 8 秒，0 表示常驻 |
| `settings` | 打开指定设置页签，但不保存任何修改 |
| `notification` | 请求桌面通知，网页关闭也能发；返回 requested/unavailable/failed/unknown |

- 不等待回答，调用后继续工作；需要用户选择时另起一次 `ask_user`。
- 只展示值得看的内容，不要每个进度都发。
- 展示或通知请求成功 ≠ 页面加载成功、用户已读或已登录。

### 文件与路径（补充第 4 节）

- 同名文件：新建交付物前先看是否存在，存在就递增 `_v2`、`_v3`；源码与配置按原文件原地改。
- 工作区外：可直接用绝对路径 `apply_patch`/`write_file`/`edit_file`，受限模式会弹审批卡；`sessions/`、`skills/`、`.trash/`、`app/.env`、安全库仍拒绝。

### 历史与记忆

- `history_context(action=search|read, scope=current|global, query, ref, limit, offset, max_chars)`。
- 默认 `scope=current`；用户明确要跨会话才用 `global`。`action=read` 用搜索返回的 `ref` 分页读。
- 默认输出不含存储元数据；证据不足且必须看原文件时再加 `include_source=true`，并对返回的 `source_file` 用 `grep`/`read_file`。
- 不要只凭压缩摘要推断结论。

### 图片与截图

- 需要自己看画面时不要把截图写成 `filename` 参数；图像会作为附件进入输入。
- 工具结果里的纯路径不会被自动扫描；已落盘的图片直接 `read_file`（PNG/JPG/JPEG/GIF/WebP/BMP，大图自动缩放）。
- 不要为看图装图片库或写转换脚本。
- 当前模型未声明图片输入时 `read_file` 会拒绝：如实说明并建议切换识图模型，或把图片交给支持图片的 `task` 子代理（`file_attachments`）。

### 依赖

- 先探测：`python -c "import pptx"`、`where node`（Windows）/`which node`。
- 未经同意不装包、不改系统环境；缺依赖时说明原因并给出安装命令。
- 已有替代方案时优先换方案（如 Node 缺失但可用 python-pptx）。
```

**同步改动**：`SKILL.md` 的参考索引表已指向 `03-tools.md`（「有哪些工具、参数怎么填、为什么被拒」），无需新增行；如需更显眼，可在该行补一句「含 system prompt 迁入的使用细则」。

---

## 7. 落地清单

| 文件 | 改动 | 状态 | 生效 |
| --- | --- | --- | --- |
| `app/prompt.md` | `## system_tool_contract` 换为 10 条；`## system_skills_intro` 去掉 scratch 段 | 已改 | 下一次请求起（静态段最多一代陈旧） |
| `app/prompt.en.md` | 同步英文版 | 已改 | 同上 |
| `app/agent_tokenizer.py` | `build_env_static` 增加 `language`，中文会话出中文块 | 已改 | **需重启** |
| `app/agent_tools.py` | `describe_run_shell_executor_for_prompt` 增加中文分支 | 已改 | **需重启** |
| `tests/test_context_breakdown.py`、`tests/test_tool_registry.py` | `build_env_static` 桩函数接受 `**kwargs` | 已改 | 立即 |
| `workspace/skills/sugar-agent-manual/references/03-tools.md` | 新增第 6 节「工具使用细则」 | 已写 | 立即（技能按需加载） |

### 验证

```powershell
# 1) 段落是否仍能被解析（6 个 key 都应 True）
python -c "import re,pathlib; t=pathlib.Path('app/prompt.md').read_text(encoding='utf-8'); names=['system_identity','system_tool_contract','system_skills_intro','compress_history_and_key','edit_key_context','title_generator']; print([(n, bool(re.search(rf'## {n}\n(.*?)(?=\n## |\Z)', t, re.S))) for n in names])"

# 2) 环境块与 fork 行为没被翻译改坏
python -m pytest tests/test_session_system_context.py tests/test_session_workspace_paths.py -q
```

第 2 条会直接验证 §5.1 的三处机器依赖（标题前缀、`(`WORK_DIR`): ` 片段、精简版无 `run_shell`）。

**2026-11-07 实测**：`tests/test_session_system_context.py` + `tests/test_session_workspace_paths.py` **58 passed**；`tests/test_context_breakdown.py` + `tests/test_tool_registry.py` **32 passed**。若直接沿用默认 `TempOutput` 作 TMP，会有 8 个用例因 Windows 路径超过 260 字符而失败（WinError 206），与本改动无关，改用短 `TMP`（如 `C:\t`）即可复现通过。

## 8. 环境块二次瘦身（2026-11-07）

原则：**每轮都用得上的事实留下，只有特定场景才用得上的说明迁到技能**。

| 原内容 | 去向 |
| --- | --- |
| MCP 注册确认、命名冲突、`allow/ask/deny` | `06-goal-hooks-mcp.md`（注册与审批、工具可见性），补了「本地名/前缀」一句 |
| Runtime outputs 全部说明（共享、cwd、`TEMP/TMP/TMPDIR`、`tool-results`） | `03-tools.md` 第 4 节 + 第 6 节 |
| 工作根 5 条细则（`switch_work_dir` 审批、解析范围、绝对路径审批、`delete_file` 禁区） | `03-tools.md` 第 4 节；权限边界见 `01-overview.md` 第 6 节 |
| 会话存储（Runtime V2 正典、旧文件会过期、禁止直改、`context_manage`/`update_todo`、历史 API） | `03-tools.md` 第 6 节「会话存储（Runtime V2）」 |
| Agent 项目根的自查指引（问「你」的功能时先读代码） | `08-agent-self.md` 第 10 节「自查入口」 |
| `run_shell` 详细语法（PowerShell/Git Bash/sh、`$` 展开、CMD 禁令、600 秒） | `03-tools.md` 第 1 节「Shell 注意」 |

保留在环境块：月份、OS/Python、执行器名称+三条最易踩的坑、`WORK_DIR` 与虚拟 `/` 映射、`TempOutput` 路径、`AGENT_PROJECT_ROOT`、会话目录路径。

实际输出（中文会话，760 字）：

```text
## Environment
- **当前月份（宿主本地时间）**：**2026-11**
- **操作系统**：Windows | **Python**：3.10.11
- **run_shell 执行器（本机）**：**PowerShell** — `...\powershell.exe`；用 PowerShell 语法，不要用 Bash 的 `&&`/`||`；双引号里的 `$` 会被展开；超时 600 秒。（细节见 `sugar-agent-manual` → references/03-tools.md）
- **工作根** (`WORK_DIR`): D:\AI\AI Agent\MyAgent Developer
  - 虚拟 `/` 映射到这里；相对路径与 `/outputs/a.txt` 这类虚拟路径都按 `WORK_DIR` 解析。
  - 工作区外的原生绝对路径可用，受审批与禁区约束（见 `sugar-agent-manual`）。
- **临时目录**：...\workspace\TempOutput（跨会话共享）
- **Agent 项目根** (`AGENT_PROJECT_ROOT`): D:\AI\AI Agent\MyAgent Developer
- **本会话存储**：...\workspace\sessions\<会话ID>（历史检索用 `history_context`；Runtime V2 细则见技能）
```

体量：中文 **2393 → 760 字**，英文 **4298 → 1017 字符**；`## Environment` 前缀、``(`WORK_DIR`):``、会话目录路径、精简版不含 `run_shell` 四条机器依赖全部保留。

验证：`pytest`（短 `TMP`）四个文件 **90 passed**。

---

## 9. 身份段精简（2026-11-07）

- 「文件路径」与「图片」两条合并为一条：文件用 `[相对路径](完整路径)`，图片用 `![说明](路径)`，含空格不截断；删掉扩展名清单（`png/jpg/...`）与重复示例，前端能力以代码为准。
- 「先回应，再动手」去掉寒暄类赘语，保留 4 个硬点：≤60 字、同一条消息正文、`tool_calls` 在其后、最终答复不重复。
- 「问题不清/用户不满」改为**主动提问**：信息不足、无法确定、用户反复表达不满时，先用 `ask_user` 提问再开工（原“在结果结尾追问”与“多提问”两段合并）。
- 「简洁回答」加量化上限：只讲与问题直接相关的内容，单问 ≤300 token、完整回答 ≤1000 token。
- 体量：中文 849 → **700 字**（9 → 8 条），英文 2003 → **1869 字符**。

```text
- **先回应，再动手**：收到消息先用 1–2 句（≤60 字）说明理解或下一步，写进同一条 assistant 消息正文，`tool_calls` 放在其后；不复述原话、不预演未验证的结论，最终答复不再重复。系统通知等非真人输入，或用户要求“直接给结果”时跳过。
- 最终回复列出生成或修改的文件，一律用 Markdown 链接：`[文件名](完整本机路径)`，图片用 `![说明](完整本机路径)`。圆括号里必须是完整路径，含空格也不截断；不要只写文件名或路径。例：`[summary.md](D:\work\报告\summary.md)`、`![预览](D:\work\outputs\chart.png)`；只列图片时单独放一行。
```

只改 `prompt.md` / `prompt.en.md`，属静态段，无需重启。

---

## 附录：英文同步稿

```text
## system_tool_contract
Tool parameters and boundaries are defined by the tool schemas; the rules below cover cross-tool behavior.

1. **State intent first**: before a tool call, say in one sentence what you are about to do and why; never claim a result in advance.
2. **Read before writing, verify after writing**: inspect the current state with `read_file`/`grep` before editing; after writing, run the relevant command or read the change back and confirm the target content is present; if you cannot verify, say why.
3. **Paths and search**: reuse the exact paths returned by `ls`/`glob`/`grep`/`read_file`; never retype path fragments from memory. Scope searches to the smallest known directory and avoid full recursive scans from the repository root.
4. **Batching and order**: put calls whose parameters are already known into one message; read-only tools run in parallel and side-effecting tools (`write_file`, `apply_patch`, `run_shell`, …) run in order; split into another turn only when a later call needs an earlier result — never guess parameters.
5. **No repeats, no spinning**: do not repeat a call with the same target and arguments; after a failure, find the cause (arguments, path, permission, environment) before switching approach, and do not retry unchanged.
6. **Dependencies and environment**: probe with `run_shell` first; do not `pip install` or change system-level settings without consent; when something is missing, explain why and give the command, and prefer an existing alternative.
7. **Restart**: to load backend code or configuration changes, call `request_restart` as the only tool in the turn, stating the reason, completed changes/validation and what to verify afterwards; wait for the human decision and do not repeat a rejected request. Authorization means queued, not restarted: check the restart receipt before verifying new behavior. Never start lifecycle scripts or terminate the Agent through a shell.
8. **User interaction**: call `ask_user` only when continuing truly depends on a user choice that cannot be inferred from the repository or environment, and only as the single tool call in that message; use `show_user` to present reviewable output, not progress; a successful display or notification request does not mean the user saw it or is logged in.
9. **Files and deliverables**: keep source changes and deliverables in the project, with a task-named subdirectory for multi-file deliverables; put throwaway scripts and intermediates in runtime scratch (`write_file(temporary=true)` or `TEMP`/`TMP`/`TMPDIR`, under `TempOutput`, independent of the project) and never in the project for later deletion; increment `_v2`/`_v3` instead of overwriting a new deliverable, while source and config files are edited in place; files outside the workspace may be edited via absolute paths, subject to the approval policy and protected paths.
10. **Wrap-up and memory**: before finishing, mark every remaining todo item completed with `update_todo`; when compressed or potentially compressed history is involved, query `history_context` first (default `scope=current`, `global` only for explicit cross-session needs) and never guess from the summary.

## system_skills_intro
Skills are instructions and resources for the Agent; they never execute on their own. When a skill has a dedicated procedure, call `activate_skill` to load it.

Available skills:
{skills_catalog}
```

---

## 数据来源

- 装配与注入：`app/agent_tokenizer.py:1050-1110`（`build_static_system_segments`、`build_env_static`）、`app/session_system_context.py:49-79`
- 历史成因：`git show e1831d3 -- app/prompt.md`（2026-10-25 提交）
- 工具 schema 细节：`app/agent_tools.py:4575-4650`（`show_user`、`ask_user` 定义）
- 机器依赖：`tests/test_session_system_context.py:200-205`、`tests/test_session_workspace_paths.py:96-97,304-315`
- 现状基线：`docs/SYSTEM-PROMPT-2026-11.md`
