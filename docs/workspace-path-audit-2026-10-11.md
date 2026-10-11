# 工作目录路径审查（2026-10-11）

## 后续修复状态

用户授权“都同步起来”后已落实以下修复；下文的原始发现和复现统计描述的是修复前状态。

- 子代理继承父会话有效根，旧子代理按父链补齐；worktree 创建、合并、清理均使用所属项目的仓库，保留项目在仓库中的相对位置。
- 模型 Environment 提示与缓存、fork 子代理提示、用户终端空/相对 cwd、权限目录兜底统一到有效根。目录被删除时保留配置身份，浏览接口返回 404，不静默回到默认目录。
- `temporary=true` 在工具执行上下文中捕获实际文件路径，后处理按该文件清理，避免误动全局同名文件。
- **按用户后续要求，超长工具结果仍保存到全局 `.tool_results`**；结果提示改用完整绝对路径，后续自定义项目中的读取和清理可正确定位。
- 文件树、文件选择器、打开/定位、文本、图片尺寸、图片/音视频与 HTML 预览接口支持会话身份/草稿目录；前端保留完整原生路径。HTML 资源 URL 将会话身份放进路径，并绑定实际文件根，CSS/图片等兄弟请求仍保持目录身份。
- 文件树刷新/切换会话时忽略过期响应，子代理与父会话共享详情栏时也刷新有效文件根；媒体缓存按实际绝对路径区分同名文件。
- 历史图片从会话根读取、在共享存储保存；子代理相对附件按父会话根读取；原生选择器初始目录跟随当前会话/草稿。
- 普通 MCP/插件调用也对声明的 workspace 根参数和路径参数注入有效根；worktree 的边界限制继续生效。Hook 的执行 `project_root`、命令替换和审批使用同一根，同时提供 `app_root` / `shared_root`。
- 新增无应用启动副作用的 `app/workspace_paths.py`。Electron 启动/重启、技能模板来源、维护脚本默认会话库都复用配置路径解析；UI 验证脚本从目标服务的 `/api/workspace-info` 获取实际存储根。旧沙箱 ACL 脚本支持配置默认根或显式 `-WorkDir`。
- 路径样例改为工程根相对路径；空 `SKILLS_DIR` 跟随全局 `WORK_DIR/skills`，插件发现/状态配置的相对路径也统一以工程根解析。

会话库、上传、附件、Vision、历史图片、全局技能库和应用配置仍是共享职责；没有迁移真实数据，也没有因切换项目自动加载新的可执行插件/Hook。

验证：新增默认根 A / 自定义根 B、C 并存的路径回归，覆盖父子/旧子代理、同名文件、失效目录、真实临时 Git 仓库的 worktree 合并与清理、全局超长结果、MCP/插件契约、Hook 审批与执行根、终端 API 和前端路径缓存。FastAPI 测试使用真实应用及临时存储；终端、外部服务和插件调用使用替身。真实构建界面的浏览器测试验证文件树、文本请求和 HTML 兄弟 CSS 资源，但未启动真实外部 MCP、模型调用或已安装桌面包。

专项回归为 48 项通过，其中新增路径用例 18 项、真实浏览器用例 16 项。扩大回归结果为 330 通过、2 跳过、6 失败。失败项涉及工作树中此前已删除的 `plugins/session-todo/host.py` / `update_todo`，以及未改动的 SSE 测试桩缺少 `streamHistoryRecoveryBySession`、`shouldSkipRecoveredEphemeralEvent`；没有恢复用户已删除的插件或混入相关功能修改。前端生产构建与 Python/JS/PowerShell 语法检查通过。

后端改动在重启服务后生效；已安装桌面版需重新打包。本轮没有重启现有服务或改动运行中的会话。

## 结论与范围

会话自定义工作目录已接入工具执行的主链路，但还没有贯通模型提示、子代理、工具结果后处理、用户终端和文件浏览/预览。遗漏不止原计划文档列出的文件面板与目录选择器。

本次审查的是当前工作树，包括已有的未提交修改。检查范围为 `app/`、`frontend/src/`、`plugins/`、`packaging/`、启动入口、相关维护脚本及现有测试/设计说明。只新增审查报告和本地复现材料，没有修改业务代码或迁移已有会话。没有启动应用、调用模型、创建真实终端或修改真实 Git worktree。

本地配置及磁盘抽样：

- `app/.env` 的 `WORK_DIR=./workspace`，源码以工程根目录为基准，解析为 `D:\AI\AI Agent\MyAgent Developer\workspace`。目前全局默认根仍是这个目录。
- 读取到 426 份根会话 metadata，其中 5 份设置了 `work_dir`，这些自定义目录当前均存在。
- 读取到 297 份直接子会话 metadata，2 份带工作根覆盖字段。这个统计包含默认目录会话，不能据此推断其余子会话全部有问题。
- 只读执行 `git -C workspace rev-parse --show-toplevel`，结果是 **MyAgent Developer 工程根**。因此从全局默认目录寻找 Git 仓库，会找到 Agent 自身的仓库。

## 三类目录的现有职责

| 根目录 | 当前用途 | 是否应随会话目录切换 |
|---|---|---|
| `PROJECT_ROOT` | Agent 源码、内置 Python、前端资产，以及工程 `.config` 中的模型/MCP/技能启停/插件启停配置 | 保持应用级 |
| 全局 `WORK_DIR` | 默认项目工作根，以及共享会话库、上传、附件、Vision、历史媒体、默认技能目录 | 共享数据保持全局；默认项目操作作为兜底 |
| 会话有效根 | `subagent_work_dir → git_worktree_path → work_dir → WORK_DIR` | 文件操作、Shell、项目浏览/预览、相对路径解析应使用它 |

会话库和附件继续保存在全局根，是 [现有设计的 D1/D2 决策](<D:/AI/AI Agent/MyAgent Developer/docs/per_session_workdir_plan.md:12>)。不能把所有出现 `WORK_DIR` 的地方直接替换成会话目录。

## 已接入自定义目录的部分

| 链路 | 当前实现 |
|---|---|
| 新建根会话 | 校验存在的绝对目录；写入 `metadata.work_dir`，初始授权目录也跟随；显式选择默认根等同未覆盖。`agent_harness.py:6919` |
| 内置文件工具和模型 Shell | `agent_loop.py:7002/7042` 在工具调用期间设置 ContextVar；`agent_tools.py:80` 从执行上下文取根，读写、下载、Shell 使用该根 |
| 工具内软删除/长 Python 命令临时脚本 | `.trash` 使用 `active_tool_work_dir()`；`.run_shell_temp` 使用当前工具根。`agent_tools.py:2580/2956` |
| 中央权限判定与变更审计 | `security_workspace`、审计根、early-tool 授权根使用 `session_work_root()`。`agent_loop.py:6150/7307/7661` |
| 变更审查锁 | 默认、普通自定义根及 worktree 按实际根区分。`plugins/change-review/host.py:62` |
| Hook 事件载荷 | 自定义根进入 `workspace_root`。`agent_loop.py:675`；但传统 `project_root` 仍是全局根，见扩展边界 |
| 普通根会话的目录显示/分组 | 会话列表投影、分组及多数路径显示读取 `work_dir`。`frontend/src/app/config.js:34` |
| 本机绝对路径的后端读取 | 预览解析器可以读取存在的工作区外绝对文件。问题主要出现在绝对路径被前端降成相对路径后 |

## 确认遗漏的链路

P1 表示应优先处理：可能选错项目、读写错目录或影响临时清理。P2 表示功能遗漏、显示/恢复偏差或配置维护问题。下面的独立编号是修复边界，不代表逐个硬编码出现次数。

### A1 · P1 · 子代理没有继承父会话有效工作根

位置：[创建子会话](<D:/AI/AI Agent/MyAgent Developer/app/agent_harness.py:6595>)。

`create_subagent_session()` 继承父会话的语言和 `authorized_dirs`，却没有继承 `work_dir` 或父会话的有效工作根。共享目录的 explore、readonly、关闭 worktree/隔离失败后的子代理，以及通过该方法创建的团队成员，会回退到全局 `WORK_DIR`。

隔离复现：父会话在 `project-b`；子会话的授权目录是 `project-b`，实际 `session_work_dir(child)` 却是全局 `workspace`。授权目录的继承不能代替工作根的继承。

修复方向：子会话创建时保存父会话有效根；成功创建独立 worktree 时由 worktree 覆盖。嵌套子代理应继承当前父代理所在 worktree。已有子会话的补全需沿父链解析，不能统一填全局根。

### A2 · P1 · 子代理 Git worktree 定位、记录和清理仍使用全局根

位置：[仓库定位](<D:/AI/AI Agent/MyAgent Developer/app/agent_subagent.py:1443>)、`_git_worktree_add:1400`、`_git_worktree_remove:1519`、`_persist_managed_worktree:1614`。

`git rev-parse`、best-of-n 创建、worktree 清理/分支删除使用 `cwd=WORK_DIR`；`_create_managed_worktree()` 调用的仓库定位函数没有会话参数。即使父会话选中另一个项目，自动隔离仍会从全局根找仓库。

在当前目录布局下，它可能基于 **Agent 自身仓库** 创建 worktree。持久化的 `git_worktree_main_root` 同样来自这次全局定位；后续合并使用该记录，不能只改首次创建的 cwd。

隔离复现记录了仓库定位命令的 cwd，确认为默认 `workspace`。真实 Git 只执行了只读的仓库根查询，没有实际创建或合并 worktree。

修复方向：显式传入父会话有效根及所属 Git 根；创建、记录、合并、清理使用同一所属仓库。

### A3 · P1 · 模型的环境提示仍宣称全局根是当前工作根

位置：[环境提示](<D:/AI/AI Agent/MyAgent Developer/app/agent_tokenizer.py:915>)、`agent_loop.py:2187`。

`build_env_static(session_id)` 虽有会话 ID，`wdir` 仍直接取 `WORK_DIR.resolve()`。模型被告知“相对路径和虚拟 `/` 映射到默认 workspace”，实际工具却映射到自定义目录。会话存储提示还把全局会话库描述成可用的 `/sessions/...` 虚拟路径，这在自定义项目根下不成立。

隔离复现：自定义父会话的 `Work root` 提示仍是默认根。

修复方向：环境提示分别写出应用根、当前有效项目根、全局会话存储根；工作区外会话库使用绝对路径/API。还需处理 fork 继承的 `system_segments` 和静态提示缓存，缓存键应包含有效工作根/worktree 状态，避免丢弃 worktree 后提示继续引用旧根。

### A4 · P1 · `temporary=true` 的登记与清理丢失工具目录上下文

位置：[登记函数](<D:/AI/AI Agent/MyAgent Developer/app/agent_loop.py:4601>)、登记调用 `:9319`、清理 `:4707/9780`。

文件写入发生在 `tool_work_dir_override()` 内；成功后的 `_record_temporary_write_file()` 在该作用域外，再以 `safe_work_path(raw)` 解析一次相对路径，得到全局目录下的文件名。清理随后消费这个错误的绝对路径。

隔离复现：实际临时文件写在 `project-b/audit-temporary.py`，登记的却是 `workspace/audit-temporary.py`。真实临时文件会残留；默认根若有同名且可删除的文件，可能被误移入默认 `.trash`。没有实际删除用户文件。

修复方向：工具结果携带实际已解析的文件路径，登记直接使用该路径；清理显式使用所属会话根及对应权限上下文。

### A5 · P1 · 超长工具结果落盘到全局 `.tool_results`，后续读取却去自定义根

位置：[落盘函数](<D:/AI/AI Agent/MyAgent Developer/app/agent_loop.py:4624>)、结果转换 `:6660`、工具上下文 `:7042`、转换调用 `:7131`。

结果转换在工具执行上下文退出后调用 `_save_result_to_tempfile()`，其 `safe_work_path()` 回退全局根。提示返回的仍是 `/.tool_results/...`；下一次自定义会话 `read_file` 将这个虚拟路径映射进自定义根。

隔离复现：结果保存在默认 `workspace/.tool_results`，按提示从 `project-b/.tool_results` 读取时文件不存在。

修复方向：将会话有效根显式传入结果落盘，或返回稳定的绝对路径/结果引用；结果转换、登记、清理形成完整的目录闭环。

### A6 · P1 · 用户终端默认 cwd 未读取普通会话 `work_dir`

位置：[用户终端 API](<D:/AI/AI Agent/MyAgent Developer/plugins/execution-tools/host.py:183>)、`plugins/execution-tools/web/session-panel.js:217`。

界面提示“留空使用会话工作区”，API 取根却是 `subagent_work_dir or git_worktree_path or active_tool_work_dir()`。普通 HTTP 请求没有模型工具的 ContextVar，且表达式漏掉 `work_dir`，因此落到全局根。手填绝对 cwd 可以避开这个遗漏；模型通过工具打开终端的链路已使用执行上下文。

修复方向：默认和相对 cwd 都从 `session_work_dir(session_id, meta)` 解析。

### A7 · P2 · 文件树、检索和聊天文件选择面板仍浏览全局根

位置：[目录/检索后端](<D:/AI/AI Agent/MyAgent Developer/app/webui.py:2575>)、`list_workspace_files:2655`；[聊天选择面板](<D:/AI/AI Agent/MyAgent Developer/frontend/src/vendor/myagent_path_picker.js:229>)；`right-column.js:928`。

`/api/workspace-files` 没有会话参数，目录枚举、搜索及响应 `root` 都是 `WORK_DIR`。前端只发送 `q/dir`；选择面板的树根名称、根路径和目录选择也读取 `window.__WORK_DIR__`。切换会话不会改变这套接口的根。

修复方向：请求绑定会话 ID，服务端从会话解析根；目录树、搜索状态和缓存也按会话/根区分。

### A8 · P1 · 打开文件、媒体和文档预览存在“前端自定义根、后端全局根”错配

位置：[后端路径解析](<D:/AI/AI Agent/MyAgent Developer/app/webui.py:2041>)、`workspace-file-text:2392`、`workspace-assets:2445`；[文件链接转换](<D:/AI/AI Agent/MyAgent Developer/frontend/src/app/modules/message-rendering.js:3117>)；`workspace-media.js:20/66/121`；`right-column.js:1105/1136/1171`。

受影响接口包括 `/api/open-workspace-file`、`open-workspace-dir`、`workspace-media`、`workspace-image`、`workspace-image-metadata`、`workspace-file-text`、`workspace-assets`。相对/虚拟路径仍按全局 `WORK_DIR` 解析。

这不意味着所有绝对路径都不能打开：后端可直接读取存在的本机绝对路径。但 `pathTokenToWorkspaceOpenRel()` 把自定义目录下的 Windows 绝对文件降为相对路径，再交给全局解析器。复现 `D:/Projects/project-b/report.txt → report.txt`；后端相对预览读到 DEFAULT，同一文件用完整绝对路径读取则是 CUSTOM。没有默认同名文件时通常表现为 404。

图片尺寸/版本缓存只以 `rel` 为键，不区分项目；以后让接口跟随会话时还需同步修正缓存身份。HTML/CSS/JS、Markdown 引用也必须共享同一项目根；只给 HTML 首次请求添加 `session_id` query，浏览器加载兄弟资源时不会自动继承该 query。

修复方向：请求/文档页绑定所属会话，保留准确路径身份。HTML 资源宜使用包含会话 ID 的路径前缀，让兄弟资源自然落在同一根。

### A9 · P2 · 历史图片快照的源文件查找仍是全局根

位置：[调用入口](<D:/AI/AI Agent/MyAgent Developer/app/agent_loop.py:2643>)、`workspace_media_snapshots.py:29/58`。

历史快照保存在全局 `.config/history-media` 符合 D2。遗漏是源文件查找也用同一个 `WORK_DIR` 参数：自定义项目中的 `![plot](chart.svg)` 会在默认根找图，同名图可能被错误固化，没有同名图则无法固化。完整绝对图片路径能绕过源查找错配。

隔离复现：自定义与默认目录放不同内容的同名 SVG，快照内容是 DEFAULT。

修复方向：拆分 `source_root=会话有效根` 与 `storage_root=全局共享根`，保留共享存储决策。

### A10 · P2 · 交给子代理的相对文件附件仍从默认根读取

位置：[附件解析](<D:/AI/AI Agent/MyAgent Developer/app/agent_subagent.py:1065>)、`load_file_attachments_block:1084`、调用 `:2808`。

`task.file_attachments=['report.txt']` 用全局 `WORK_DIR` 解析；只要默认根存在同名文件，就可能把错误内容注入子代理。完整绝对路径或 durable attachment 引用可以避开这个相对路径问题。附件对象保存在全局根本身仍符合共享设计。

修复方向：相对项目文件按发起任务的父会话有效根解析，先固化成绝对路径/附件引用，再交给子代理。

### A11 · P2 · 原生聊天文件选择器初始目录仍使用全局根

位置：[聊天入口](<D:/AI/AI Agent/MyAgent Developer/frontend/src/vendor/myagent_path_picker.js:1174>)、`app/path_picker_util.py:78`。

Shift 文件选择入口直接传 `window.__WORK_DIR__`。原生选择器的 `initial` 本来可接收任意现有目录；缺省兜底还会优先使用用户主页，其次才考虑全局目录，所以不能简单描述成“后端永远从 workspace 开始”。真正需要改的是聊天调用方提供的当前目录。

修复方向：聊天传当前会话/草稿目录；应用设置中的路径选择继续按对应设置字段起步。

### A12 · P2 · 目录投影、草稿根和按目录名猜路径仍有边界偏差

位置：[目录投影](<D:/AI/AI Agent/MyAgent Developer/app/agent_harness.py:230>)、`session_work_root_raw:190`、`frontend/src/app/config.js:34`、[Dock 猜路径](<D:/AI/AI Agent/MyAgent Developer/frontend/src/app/modules/dock/embedder/right-column.js:200>)。

- 有效执行根支持 worktree 优先级，但目录投影只认 `work_dir`；前端访问器也只读投影 `work_dir`，不能完整表示 worktree。
- 自定义目录在创建后被移走/删除：UI 投影会因“不存在”回退默认根，执行根却仍保留 metadata 中的绝对路径。本地 5 个自定义根当前均存在，这一项是隔离边界复现。
- 无激活会话的自定义草稿，`getActiveWorkDir()` 不读取 `newSessionWorkDir/pendingNewSession`，仍回退默认根；欢迎目录显示另有实现，容易出现标题正确、路径辅助解析仍用默认根。
- `dockRightRelPath()` 搜索字符串 `workspace/` 并截取后半段，没有比较实际根。`D:/Projects/project-b/workspace/report.txt` 被变成 `report.txt`，丢掉项目中的真实 `workspace` 子目录。
- 授权目录写入/修复的缺省分支仍调用全局 `_get_work_dir()`，见 `session_authorized_dirs.py:157/207`。正常新建会话已经初始化授权；缺失授权列表的旧/异常 metadata 仍需统一会话根。

修复方向：服务端提供统一 `effective_work_dir` 投影；失效目录显式报告失效；草稿有独立目录访问器；相对路径通过实际根边界计算。

## 全局默认目录改动、扩展和维护脚本的残留

这些与普通会话的 `work_dir` 覆盖不同，也需要纳入后续同步工作。

| 项目 | 位置与当前行为 | 判断/建议 |
|---|---|---|
| Electron 打开工作目录/状态/技能铺设 | `packaging/electron/main.js:103/137/144/536/558/568` 固定 `runtime或userDir/workspace`，缓存 layout；后端 `.env` 可覆盖它 | 全局自定义目录后，桌面菜单、IPC、状态报告和技能铺设可能仍指向安装版默认目录。应从后端获得实际全局根；托盘菜单可保持“全局默认目录”的语义 |
| `.env.example` 的旧相对路径 | `app/.env.example:48/49/50/99/100` 使用 `../workspace`、固定 skills/plugins/state 路径 | `_env_path()` 现在以工程根解析，样例 `WORK_DIR=../workspace` 会落到工程上一级；显式 `SKILLS_DIR` 也不会随着只改 `WORK_DIR` 自动跟随。样例插件路径按进程 cwd，行为又与 host 规范不一致；`PLUGINS_DIR` 会覆盖内置插件发现列表。应更新样例并让衍生路径缺省自动派生，保留用户显式覆盖 |
| 全局配置保存与数据迁移 | `webui.py:9497/9519` 返回 `restart_required`，`agent_harness.py:147/361` 启动时绑定根 | 全局目录修改需要重启；不是自动迁移 `sessions/uploads/attachments`。旧数据和已保存绝对路径不会自动重定位，需要另行制定迁移流程 |
| MCP cwd 与普通自定义会话参数 | `agent_mcp.py:759` 的 stdio cwd 按应用根/服务器配置；`:1310/1329/1349` 仅在 worktree 隔离分支注入工作根和规范化路径参数 | 普通会话虽然向调用层传入 `work_dir`，服务器最终参数不因此自动改变。是否仍操作旧目录取决于具体服务器配置与参数，未调用外部服务器确认；应给声明 workspace 契约的工具补齐普通会话根语义 |
| 插件命令/传统 Hook 根 | `agent_loop.py:668/10330` 的 `project_root` 保持全局根；`agent_extensions.py:892/896` 构建全局 Hook manager；插件 tool 的 `workspace_root` 已传递 | Hook 事件已有额外 `workspace_root`；只用传统 `project_root` 或 `${MYAGENT_PROJECT_ROOT}` 的扩展仍访问默认根。应区分应用/共享配置根与项目执行根，不能盲改所有 Hook 的配置发现目录 |
| 项目本地 skills/hooks/plugins 自动发现 | `agent_tools.py:254` 只扫描全局 `SKILLS_DIR`；`agent_extensions.py:112` 默认全局 `hooks.json`；`plugins/manager.py:96` 项目+用户插件发现 | 当前是应用级配置，不会因切换会话自动加载自定义项目里的技能/Hook/插件；属于尚未支持的项目级发现能力，不能直接当成某次写文件落错根 |
| 维护/修复脚本默认会话库 | `scripts/audit_runtime_versions.py:323`、`benchmark_runtime_versions.py:198`、`compare_runtime_v2_session.py:87`、`repair_runtime_v2_root_event_logs.py:45` | 默认都硬编码 `ROOT/workspace/sessions`；已提供 `--sessions-dir`，更换全局默认根后需手动传参。建议共享纯路径解析配置；修复脚本尤其应显示实际目标目录 |
| UI 验证脚本 | `verify_ui_fixes.py:124/348`、`verify_dot_colors.py:124/234`、`verify_scroll_culprit.py:135/220`、`verify_stream_layout.py:303`、`verify_capsule_new_session.py:36/124`、`browser_smoke_runtime_v2.py:117/122`、`subagent_ui_verify.py:169` | 多处种子/读取/清理硬编码默认 workspace；全局改根后可能验证与清理不同目录。应从隔离实例根或 CLI 参数派生，测试固定路径不算线上功能根遗漏 |
| 打包模板和旧沙箱权限脚本 | `packaging/scripts/prepare-payload.mjs:308` 从固定 workspace/skills 打包模板；`scripts/build_egress_helper_windows.ps1:24` 给固定 workspace 授 ACL | 前者会漏掉放在自定义 SKILLS_DIR 的模板；后者是可选旧沙箱权限处理，并不能覆盖自定义工作根。模板来源宜独立配置，权限脚本需按其实际启用范围处理 |
| 安装/卸载保护及默认兜底字符串 | `packaging/nsis/installer.nsh:114`、`patch-nsis.mjs`、attachments 默认根、setup 的 `./workspace` 缺省值 | 安装目录中默认工作区的保护、未设置时的兜底和示例 API URL 是有意保留，不能机械替换 |

工程根 `.config` 中的 `model_profiles.json`、`mcp_servers.json`、`mcp_tools_state.json`、`skill_states.json`、`plugins-state.json` 保持应用级。权限数据库默认位于 OS 用户状态目录，见 `security/store.py:18`，也不应随每个项目移动。

## 修复顺序与验证要求

1. 先建立统一的有效根契约，补 A1/A2/A3/A6：父子代理、worktree、模型提示与用户终端一致。
2. 修复 A4/A5 的执行后处理：传递实际文件身份/有效根，避免错误清理和结果读取断链。
3. 补全文件浏览/预览 API 及前端所属会话、缓存、HTML 兄弟资源；一并修 A7/A8/A11/A12。
4. 分离历史图片“源根”与“存储根”，按父根处理子代理相对附件，补 A9/A10。
5. 更新默认配置样例、Electron 与维护脚本；按各扩展契约核查 MCP/Hook，而后决定项目级 skills/hooks/plugins 发现是否另行实现。

验证至少覆盖：默认根 A、自定义根 B/C 含同名文件；父代理/readonly 子代理/共享子代理/worktree/嵌套子代理；超长结果后续读取；`temporary=true` 不误动全局同名文件；用户终端空/相对/绝对 cwd；会话切换后文件树和媒体尺寸缓存；HTML 兄弟资源；重启后的全局自定义根；删除/移动后的失效目录。

现有 `test_webui_paths.py` 主要 monkeypatch 全局 `WORK_DIR`；`test_subagent_optimizations.py` 的 worktree 测试也将全局 `WORK_DIR` 改成测试仓库。这些能验证默认根行为，无法证明“全局根 A、会话根 B 同时存在”时的贯通。原计划中的每会话验收脚本没有随补丁包提供，本轮以独立复现补充证据。

## 本次复现材料与限制

Python 执行了 18 项定向函数级比较，其中 4 项确认现有正确行为，14 项暴露路径/配置偏差；这些是为核查疑点选择的场景，不是整套应用的故障比例。Node VM 另外确认绝对路径被降为相对路径、请求缺少会话身份、Dock 按 `workspace` 字符串错误截断，以及草稿/worktree 根投影问题。

- [Python 复现代码](<D:/AI/AI Agent/MyAgent Developer/.config/audits/workspace-paths-2026-10-11/probe.py>) / [JSON 证据](<D:/AI/AI Agent/MyAgent Developer/.config/audits/workspace-paths-2026-10-11/evidence.json>)。
- [前端函数复现代码](<D:/AI/AI Agent/MyAgent Developer/.config/audits/workspace-paths-2026-10-11/probe.cjs>) / [前端 JSON 证据](<D:/AI/AI Agent/MyAgent Developer/.config/audits/workspace-paths-2026-10-11/frontend-evidence.json>)。

复现从当前源码抽取函数，在临时目录中运行；应用服务、外部扩展和状态服务用最小替身隔离，终端默认根验证执行了 API 的取根表达式而未启动终端。前端验证的是现有路径辅助函数，未做真实浏览器端到端。Electron、维护脚本和外部扩展边界是源码确认，未对已安装桌面包或外部服务器执行联合验收。
