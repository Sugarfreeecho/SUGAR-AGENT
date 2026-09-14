# 文件工具矩阵 · 功能方案设计（UseCase 清单）

- 版本：2026-09-13（覆盖至：HEAD `6acc6bf`）
- 用途：逐条审查（四字段格式）。
- 适用实现：`app/agent_tools.py`（read/write/edit/apply_patch/ls/glob/grep，L1956–3650）。
- 上级：`00-工具系统整体设计.md`

---

## 1. 功能定位

read / write / edit / apply_patch / ls / glob / grep 七个文件工具的行为契约——每个都有"快速失败、如实报告"的共同承诺。

## 2. UseCase

### UC-3D1 read_file
- **触发**：读取任意文本文件（含范围参数）。
- **预期现象**：支持行范围读取；超长行被"虚拟化"（换行展示但不失真信息）；不可读文本给出嗅探结论（如疑似二进制）。
- **依据**：`read_file / _virtualize_text_lines / _read_file_sniff_unreadable_text`。

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
- **预期现象**：带体积/行数/类型标注；条目数有上限；归档文件被识别；隐藏/内部目录按规则处理。
- **依据**：`ls / format_directory_listing / _ls_include_line_counts`。

### UC-3D6 glob / grep
- **触发**：按模式找文件 / 找内容。
- **预期现象**：优先使用加速器（Windows 搜索索引 / ripgrep），不可用自动回退；结果有行数/字节上限（防喷屏）。
- **依据**：`glob / _glob_with_windows_index / grep / _grep_with_ripgrep`。

## 3. 边界

- 所有路径先过工作区模型（见 ../04-工作区/01/02）。
- delete_file 不在本篇（独立成篇：06）。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-3D1 | `agent_tools.py` L2502–2586 |
| UC-3D2 | L2586–2614 |
| UC-3D3 | L2953–3033 |
| UC-3D4 | L3033–3276 |
| UC-3D5 | L2794–2927 |
| UC-3D6 | L3276–3650 |

## 5. 版本记录

- 2026-09-13 v1：拆分首版（承接 UC-308/309）。
