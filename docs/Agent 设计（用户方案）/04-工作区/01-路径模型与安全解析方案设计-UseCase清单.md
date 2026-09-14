# 路径模型与安全解析 · 功能方案设计（UseCase 清单）

- 版本：2026-09-14 v2（覆盖至：HEAD `6acc6bf` + 9-14 路径基准修复）
- 用途：逐条审查（四字段格式）。
- 适用实现：`app/agent_harness.py`（WORK_DIR 等）、`app/agent_tools.py`（路径解析）、`app/session_authorized_dirs.py`（规范化）。
- 上级：`00-工作区整体设计.md`

---

## 1. 功能定位

路径的"普通话"：虚拟 `/`、相对语义、规范化与越界判定——一切文件操作的最底层。

## 2. UseCase

### UC-4A1 虚拟路径模型
- **触发**：任意写类/读类工具使用相对路径。
- **预期现象**：统一按"`/` = 工作区根（WORK_DIR）"解析；回执与界面呈现工作区相对语义；工作区根默认 `PROJECT_ROOT/workspace`（可用 `WORK_DIR` 环境变量改）。
- **依据**：`_env_path("WORK_DIR", ...)`、系统提示路径模型段。

### UC-4A2 路径文字预处理
- **触发**：路径含重复斜杠/混合分隔符/盘符字面量。
- **预期现象**：连续斜杠折叠、虚拟路径消歧；Windows 盘符/UNC 字面量被正确保护（不被误当相对路径）；无歧义解析。
- **依据**：`prepare_agent_workspace_path_literal / _collapse_adjacent_slashes`。

### UC-4A3 解析与越界判定
- **触发**：受限模式下解析任意路径。
- **预期现象**：得出结论 = 工作区内 / 已授权目录内 / 越界；越界给出**申请审批**路径而不是硬报错；规范化（resolve + normcase + 去尾斜杠）保证判定稳定；Shell 命令的相对路径按**生效工作目录**（`workdir`）解析后再判定（见 UC-4A5）。
- **依据**：`safe_work_path / resolve_unrestricted_path / _is_within / _normalize_dir`。

### UC-4A4 敏感资源拒访
- **触发**：路径指向凭证类敏感资源。
- **预期现象**：拒访并给统一话术；不泄露文件内容。
- **依据**：`_path_is_sensitive_tool_resource / _sensitive_tool_resource_error`。

### UC-4A5 Shell 路径解析基准（workdir）
- **触发**：run_shell 命令使用相对路径（含 `..`），或显式传入 `workdir`。
- **预期现象**：相对路径 token 按**生效工作目录**解析（`workdir` 参数；未指定 = 工作区根），与命令实际执行语义一致；`workdir` 在子目录时，`..` 回到工作区其他目录不误判为越界；按基准解析后仍逃出工作区的删除维持强制单次审批（红框，见 ../07-权限审批/02 UC-7B3）。
- **规则与边界**：Windows 虚拟根 `/foo` → 工作区根（不随 `workdir` 变）；只读 git `-C`/`--git-dir`/`--work-tree` 白名单不受影响；含空格但未加引号的绝对路径视为歧义输入，保持保守（按越界处理）；分类与后续 `required_dirs` 复核使用同一基准，避免二次判定反转。
- **依据**：`agent_tools._resolve_shell_working_dir` L1070、`_resolve_shell_token_for_workspace_restrict` L1244、`_outside_workspace_tokens` L1288；`security/runtime._effective_shell_base` L201。

## 3. 边界

- 读类工具（read/ls/glob/grep）**可**访问工作区外路径（按工具规则），写类需授权——这是刻意的非对称规则。
- 授权目录的生成与存储见 02。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-4A1 | `agent_harness.py` L127–136 |
| UC-4A2 | `agent_tools.py` L233–264 |
| UC-4A3 | L282–345、`session_authorized_dirs.py` L13–49 |
| UC-4A4 | L398–445 |
| UC-4A5 | `agent_tools.py` L1070、L1244–1454；`security/runtime.py` L201、L224 起 |

## 5. 版本记录

- 2026-09-13 v1：拆分首版（承接 UC-401）。
- 2026-09-14 v2：新增 UC-4A5（Shell 路径解析以生效工作目录为基准），UC-4A3 补充交叉引用（配合当日路径基准修复）。
