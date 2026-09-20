# 文件工具矩阵 · 功能方案设计（UseCase 清单）

- 版本：2026-09-20 v2（覆盖至：当前工作区）
- 用途：逐条审查（四字段格式）。
- 适用实现：`app/agent_tools.py`（read/write/edit/apply_patch/ls/glob/grep 与路径恢复）。
- 上级：`00-工具系统整体设计.md`

---

## 1. 功能定位

read / write / edit / apply_patch / ls / glob / grep 七个文件工具的行为契约——每个都有"快速失败、如实报告"的共同承诺。

## 2. UseCase

### UC-3D1 read_file
- **触发**：读取任意文本文件（含范围参数）。
- **预期现象**：支持行范围读取；超长行被"虚拟化"（换行展示但不失真信息）；不可读文本给出嗅探结论（如疑似二进制）；路径只有一个目录片段拼错时，错误回执附带最接近的现有路径建议。
- **规则与边界**：行数缓存以解析后的完整路径及 `(mtime_ns, size)` 校验，文件变化后自动失效；路径建议只查看第一个缺失组件所在目录的直接子项，不递归扫描。
- **依据**：`read_file / _virtualize_text_lines / _read_file_sniff_unreadable_text / _missing_path_hint`。

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
- **预期现象**：优先使用加速器（Windows 搜索索引 / ripgrep），不可用自动回退；结果有行数/字节上限（防喷屏）；ripgrep 达到任一上限即停止子进程，不再扫描完整棵目录树。
- **规则与边界**：grep 默认遵守 `.gitignore` 等 ignore 文件且不扫描隐藏目录；只有调用方显式设置 `include_ignored=true` / `include_hidden=true` 才放宽。搜索应限定到已知的最小源码目录，避免无目的仓库根全扫。
- **依据**：`glob / _glob_with_windows_index / grep / _grep_with_ripgrep`。

### UC-3D7 路径复用与错误恢复
- **触发**：模型连续调用 `ls / glob / grep / read_file`，或传入不存在的路径。
- **预期现象**：工具描述要求直接复用上一步返回的完整路径；发生轻微拼写错误时返回 `Did you mean` 建议，减少一次重新定位路径的模型轮次。
- **规则与边界**：建议只是候选，不自动改写或访问另一路径；找不到高相似度兄弟项时保持普通失败语义。
- **依据**：`_missing_path_hint`、`OPENAI_TOOL_DEFINITIONS`、`app/prompt.md::system_tool_contract`。

## 3. 边界

- 所有路径先过工作区模型（见 ../04-工作区/01/02）。
- delete_file 不在本篇（独立成篇：06）。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-3D1 | `read_file`、`_missing_path_hint` |
| UC-3D2 | `write_file`、`_atomic_write_text` |
| UC-3D3 | `edit_file`、`_fuzzy_find_replacement_segment` |
| UC-3D4 | `_parse_apply_patch`、`_apply_update_hunks`、`apply_patch` |
| UC-3D5 | `ls`、`format_directory_listing`、`_line_count_file` |
| UC-3D6 | `glob`、`_glob_with_windows_index`、`grep`、`_grep_with_ripgrep` |
| UC-3D7 | `_missing_path_hint`、工具 schema、`prompt.md` |

## 5. 版本记录

- 2026-09-20 v2：grep 改为流式达到上限即终止，默认遵守 ignore/隐藏规则；ls 行数统计改为按需并共享缓存；补充路径复用和相似路径恢复。
- 2026-09-13 v1：拆分首版（承接 UC-308/309）。
