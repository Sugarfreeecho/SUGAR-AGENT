# 文件工具矩阵 · 功能方案设计（UseCase 清单）

- 版本：2026-10-23 v7（grep 有界独立队列与排队取消）
- 用途：逐条审查（四字段格式）。
- 适用实现：`app/agent_tools.py`（read/write/edit/apply_patch/ls/glob/grep 与路径恢复）、`app/tool_text_range.py`、`app/tool_glob.py`、`app/file_read_signature.py`、`app/grep_runtime.py`、`app/grep_worker.py`。
- 上级：`00-工具系统整体设计.md`

---

## 1. 功能定位

read / write / edit / apply_patch / ls / glob / grep 七个文件工具的行为契约——每个都有"快速失败、如实报告"的共同承诺。

## 2. UseCase

### UC-3D1 read_file
- **触发**：读取任意文本文件（含范围参数）或图片文件（PNG/JPEG/WebP/GIF/BMP）。
- **预期现象**：文本路径支持行范围读取；超长行被"虚拟化"（换行展示但不失真信息）；不可读文本给出嗅探结论（如疑似二进制）；路径只有一个目录片段拼错时，错误回执附带最接近的现有路径建议。图片路径忽略行范围参数，返回"文本信封 + 图片块"（信封含路径/媒体类型/显示尺寸/字节数；归一化缩放时附坐标乘数提示）；**当前模型未声明图片输入时在加载前返回可解释错误**（不入库、不产生图片块），提示切换识图模型或交给子代理 `task` `file_attachments`。
- **规则与边界**：文本范围索引以打开文件的身份、大小、mtime、ctime 及 Windows NTFS ChangeTime 校验，文件变化后自动失效；`ls` 的既有行数缓存仍按 `(mtime_ns, size)` 校验。路径建议只查看第一个缺失组件所在目录的直接子项，不递归扫描。图片走统一附件准入（字节/像素/边长上限、BMP→PNG、EXIF 修正、8-bit sRGB 归一化、内容寻址去重）；扩展名非图片但内容为图片字节时，嗅探回执提示改名/复制后重读；模型能力未知（直接调用/测试未注入）时保持既有行为。
- **依据**：`read_file / _virtualize_text_lines / _read_file_sniff_unreadable_text / _missing_path_hint / _read_file_image_output / tool_model_media_context`；回归 `tests/test_read_file_image.py`。

### UC-3D2 write_file
- **触发**：写文件。
- **预期现象**：原子落盘（断电/失败不产生半截内容）；`temporary=true` 走临时生命周期（见 ../04-工作区/03）。
- **依据**：`write_file / _atomic_write_text`。

### UC-3D3 edit_file
- **触发**：替换指定文本段。
- **预期现象**：精确匹配优先；允许时用模糊定位（缩进/空白差异容忍）；无法定位则明确失败（不乱改）。
- **依据**：`edit_file / _fuzzy_find_replacement_segment`。

### UC-3D4 apply_patch
- **触发**：应用 Codex 风格补丁。
- **预期现象**：多文件补丁**整体校验后**才写入（原子）；上下文不匹配即整体失败并给出行级诊断；成功回执列出各文件 ± 行。
- **规则与边界**：补丁文本的行数计数与"内容最小差异"口径不同（重写未变化行对差 2）——对账时净增一致。
- **依据**：`_parse_apply_patch / _apply_update_hunks / apply_patch`。

### UC-3D5 ls
- **触发**：列目录。
- **预期现象**：默认快速返回名称、体积与类型标注；条目数有上限；归档文件被识别；隐藏/内部目录按规则处理。只有显式 `include_line_counts=true` 或 `LS_INCLUDE_LINE_COUNTS=1` 时才打开文本文件统计行数。
- **规则与边界**：行数统计默认关闭，避免把目录发现退化为"逐文件读取"；显式启用后与 `read_file` 共享 `(mtime_ns, size, line_count)` 缓存并加锁支持并行只读调用。
- **依据**：`ls / format_directory_listing / _ls_include_line_counts / _line_count_file`。

### UC-3D6 glob / grep
- **触发**：按模式找文件 / 找内容。
- **预期现象**：优先使用加速器（Windows 搜索索引 / ripgrep）；结果有行数/字节上限；ripgrep 使用行缓冲并在达到任一上限时停止，stderr 同时持续读取，最多保留 8KiB 诊断。兼容正则通过同范围候选进入 Python worker；rg 不可用时，默认目录搜索明确报告无法保证 ignore 规则，显式单文件仍可检索，只有明确 `include_ignored=true` 才启用不解析 ignore 文件的目录回退。
- **规则与边界**：grep 默认遵守 `.gitignore` 等 ignore 文件与 rg 的隐藏规则；调用方可显式放宽。include/exclude 历史字符串输入按完整一个模式兼容，数组逐项校验；不拆字符、逗号或空格。既有默认排除目录在所有深度生效，显式把该目录作为目标时仍能搜索。搜索应限定到已知的最小相关目录。
- **依据**：`glob / _glob_with_windows_index / grep / _grep_with_ripgrep`。

### UC-3D7 路径复用与错误恢复
- **触发**：模型连续调用 `ls / glob / grep / read_file`，或传入不存在的路径。
- **预期现象**：工具描述要求直接复用上一步返回的完整路径；发生轻微拼写错误时返回 `Did you mean` 建议，减少一次重新定位路径的模型轮次。
- **规则与边界**：建议只是候选，不自动改写或访问另一路径；找不到高相似度兄弟项时保持普通失败语义。
- **依据**：`_missing_path_hint`、`OPENAI_TOOL_DEFINITIONS`、`app/prompt.md::system_tool_contract`。

### UC-3D8 apply_patch 工作区外路径
- **触发**：补丁文件段使用工作区外的本机绝对路径，或使用相对路径中的 `..` 越出运行时 `WORK_DIR`。
- **预期现象**：`apply_patch` 正常解析并应用该补丁，不因目标位于工作区外而在工具路径解析层硬失败；绝对路径按本机路径解析，相对路径仍以运行时 `WORK_DIR` 为基准。
- **规则与边界**：`apply_patch` 自身不施加工作区包含边界，但正常 Agent 调用仍先经过中央权限策略；受限权限模式可以要求目录审批，`full_access` 直接放行。`enforce_leaf` 继续校验实际目标必须与已裁决的补丁路径一致，敏感资源保护、删除规则和多文件原子校验保持不变。
- **依据**：`apply_patch / resolve_unrestricted_path / security.runtime.classify_tool / enforce_leaf`；回归测试 `test_apply_patch_path_resolution_is_not_contained_to_work_dir`。

### UC-3D9 连续范围读取复用文件偏移
- **触发**：对同一文本连续读取不同片段，尤其接近文件尾的片段。
- **预期现象**：首次读取统计准确总行数，并按每 128 个物理行保存文本 cookie；后续从请求附近 seek，避免反复读取整个前缀。只对返回范围生成虚拟行，仍每 1000 字符拆分，准确总行数和输出文本保持一致。
- **规则与边界**：索引为最多 128 个文件的进程内 LRU；UTF-8 替换解码和通用换行模式一致；读取前后验证同一文件来源。Windows 使用已打开句柄查询 ChangeTime，查询失败时禁用索引复用；恢复 mtime 的改写和同大小替换必须失效。仍受原范围读取大小上限、二进制嗅探、权限及敏感资源检查约束。
- **依据**：`app/tool_text_range.py`、`app/file_read_signature.py`、`read_file`；`tests/test_tool_efficiency.py` 覆盖换行、Unicode、坏字节、长行、偏移复用及来源失效；[实测及限制](../../performance/tool-efficiency-implementation-2026-10-23.md)。

### UC-3D10 递归 glob 避免重复后缀探测
- **触发**：Windows 索引未接管的 `**/suffix` 模式，包括 `**/.config/plugins*.json`。
- **预期现象**：每个递归目录使用一次 scandir 列表同时匹配后缀和发现子目录，在下降前剪除工具原本就排除的 TempOutput；减少逐目录额外探测固定子路径。
- **规则与边界**：复杂递归、多重 `**`、`..` 等模式继续由 pathlib 处理；保留路径过滤、目录链接规则、顺序与精确省略数量。仍收集完整匹配集合，未用结果上限提前停止。真实 workspace 对照中热缓存后新旧接近，不能宣称已消除所有秒级 glob。
- **依据**：`app/tool_glob.py`、`glob`；与 pathlib 对照及目录链接回归见 `tests/test_tool_efficiency.py`；[实测及限制](../../performance/tool-efficiency-implementation-2026-10-23.md)。

### UC-3D11 grep 统一预算、兼容正则和取消

- **触发**：目录表达式不被 bundled rg 支持，或搜索被取消、超时、达到输出上限。
- **预期现象**：目录回退先用同一组 rg 参数执行 `--files --null` 枚举，再在独立 Python 进程匹配，保持 include/exclude、隐藏、ignore、深度和默认排除范围。普通单文件在不超过 64KiB、表达式不超过 128 字符且无重复/断言/引用时使用进程内快路径；其余使用可终止 worker。主代理与 task 子代理共用该入口与每次调用的取消事件。
- **规则与边界**：`GREP_TIMEOUT_SEC` 默认仍为 30 秒，从 worker 提交前开始覆盖队列、启动、枚举和匹配；切换后端不重置。取消/超时后终止并等待自有子进程、关闭管道，部分结果附明确未完成错误，不能报告完整无命中；启动前已过预算不得再启动扫描。进程启动本身不能被 Python 定时器跨平台强行打断，终止和资源清理有额外短尾，不能把预算描述为绝对墙钟上限。目录匹配跳过前 8KiB 含 NUL 的候选；显式文件保留原 Python 的 UTF-8 ignore 和二进制读取行为。大小、输出、权限、敏感文件与清洗规则保留；不自动排除浏览器 profile 等新增用户目录。
- **依据**：`grep_runtime`、`grep_worker`、`_grep_with_ripgrep / _grep_python`、`agent_loop._invoke_plain_tool / _await_steerable`；`tests/test_grep_runtime.py`；[实施与剩余成本](../../performance/grep-optimization-2026-10-23.md)。

#### UC-3D11 历史复核后的验收补充

现存历史有251个执行段≥30秒，其中204个明确超时，只有11个超时使用字符串include；9/25～10/23的48个长执行段有21个来自子代理。参数、管道修复不能被描述成已经解释所有历史长尾。复核发现的“仅在worker入口检查预算、等待原future延后回执”已由下述队列补修处理；逐周、旧格式和外围配对见[复核报告](../../performance/grep-history-review-2026-10-23.md)。

#### UC-3D11 有界搜索队列

- **触发**：默认线程池被其他任务占用、多个主/子代理同时搜索，或搜索在准入/排队期间到期和取消。
- **预期现象**：grep 独立使用4个工作线程；运行及已接受排队项合计最多16个。预算从等待准入前开始，在事件循环侧也检查；未开始的搜索可在到期/取消时返回，原子放弃门保证以后不会迟到扫描。
- **规则与边界**：被放弃的占位项在worker实际取走后才释放配额，避免反复取消堆积物理队列；已经开始的搜索仍等待进程回收和管道关闭。重复取消不越过清理边界。工作目录、安全范围和身份复制到worker，主/子共用；超过容量仍会等待，并可能明确超时。event loop调度、Popen及清理尾部不保证绝对墙钟上限。
- **依据**：`grep_runtime._SearchExecutor / _SearchJob / invoke / SearchRun.request_stop`；`tests/test_grep_queue.py`、`tests/test_grep_runtime.py`；[对照与剩余范围](../../performance/grep-queue-and-tool-preparation-2026-10-23.md)。

## 3. 边界

- 所有路径先过统一路径模型（见 ../04-工作区/01/02）；`apply_patch` 的路径解析不强制包含于工作区，权限边界由中央策略负责。
- delete_file 不在本篇（独立成篇：06）。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-3D1 | `read_file`、`_missing_path_hint`、`_read_file_image_output`、`tool_model_media_context` |
| UC-3D2 | `write_file`、`_atomic_write_text` |
| UC-3D3 | `edit_file`、`_fuzzy_find_replacement_segment` |
| UC-3D4 | `_parse_apply_patch`、`_apply_update_hunks`、`apply_patch` |
| UC-3D5 | `ls`、`format_directory_listing`、`_line_count_file` |
| UC-3D6 | `glob`、`_glob_with_windows_index`、`grep`、`_grep_with_ripgrep` |
| UC-3D7 | `_missing_path_hint`、工具 schema、`prompt.md` |
| UC-3D8 | `apply_patch`、`resolve_unrestricted_path`、`classify_tool`、`enforce_leaf`、`test_apply_patch_path_resolution_is_not_contained_to_work_dir` |
| UC-3D9 | `tool_text_range.read_range`、`file_read_signature.signature`、`read_file` |
| UC-3D10 | `tool_glob.recursive_glob`、`glob` |
| UC-3D11 | `grep_runtime.py`、`grep_worker.py`、`_grep_with_ripgrep / _grep_python`、`_invoke_plain_tool / _await_steerable` |

## 5. 版本记录

- 2026-10-23 v7：搜索与默认线程池隔离，有界准入、排队deadline、放弃门与重复取消收敛；占位项实际排空后释放配额，保留已运行进程清理边界。

- 2026-10-23 v6：修正字符串过滤、并发排空 stderr、行缓冲与所有深度目录排除；增加同范围候选回退、可终止正则 worker、队列起算的总预算和主/子取消传递；明确 rg 缺失时不能静默忽略 ignore 文件及大范围扫描剩余成本。

- 2026-10-23 v5：增加范围读取稀疏偏移及来源守卫、递归 glob 单次目录枚举与 TempOutput 剪枝；保留真实 glob 未证明稳定倍数收益的限制。

- 2026-10-02 v4：UC-3D1 扩展图片直读（信封 + 图片块、归一化与伪装嗅探）与模型能力门（未声明图片输入时执行前拒绝、零残留）；依据映射同步。

- 2026-09-21 v3：新增 UC-3D8，明确 `apply_patch` 路径解析不受工作区包含边界限制，并保留中央权限裁决与叶子资源校验。
- 2026-09-20 v2：grep 改为流式达到上限即终止，默认遵守 ignore/隐藏规则；ls 行数统计改为按需并共享缓存；补充路径复用和相似路径恢复。
- 2026-09-13 v1：拆分首版（承接 UC-308/309）。
