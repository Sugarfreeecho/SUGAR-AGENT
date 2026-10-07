# 路径模型与安全解析 · 功能方案设计（UseCase 清单）

- 版本：2026-10-07 v4（覆盖至：当前工作区；会话工作目录与工具、安全、审计根）
- 用途：逐条审查（四字段格式）。
- 适用实现：`app/agent_harness.py`（WORK_DIR 与会话目录）、`app/agent_loop.py`（执行根接线）、`app/agent_tools.py`（路径解析）、`app/session_authorized_dirs.py`（规范化）、`app/webui.py::create_session`。
- 上级：`00-工作区整体设计.md`

---

## 1. 功能定位

路径的"普通话"：虚拟 `/`、相对语义、规范化与越界判定——一切文件操作的最底层。

## 2. UseCase

### UC-4A1 虚拟路径模型
- **触发**：任意写类/读类工具使用相对路径。
- **预期现象**：工具统一按「`/` = 当前会话的工具工作根」解析；回执呈现该工作区的相对语义。未指定会话目录时取全局 `WORK_DIR`，默认 `PROJECT_ROOT/workspace`（可用 `WORK_DIR` 环境变量改）；会话目录规则见 UC-4A7。
- **依据**：`_env_path("WORK_DIR", ...)`、`session_work_root`、`tool_work_dir_override`、系统提示路径模型段。

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

### UC-4A6 隔离子进程的 WORK_DIR 优先级
- **触发**：测试、验证或迁移工具启动第二个应用进程，并显式传入一次性 `WORK_DIR`。
- **预期现象**：设置 `MYAGENT_DOTENV_OVERRIDE=0` 后，显式子进程环境优先；`app/.env` 只补齐缺失配置，不把临时工作区覆盖回生产目录。未设置开关的正常应用启动继续保持历史上的 `.env` 覆盖行为。
- **规则与边界**：该开关不能隐式全局启用；调用方必须同时负责临时目录的所有权、会话清理和进程退出顺序。仅设置 `WORK_DIR` 而未关闭 dotenv override 不构成隔离。
- **依据**：`agent_harness.load_app_dotenv`、`scripts/subagent_ui_verify.py`。

### UC-4A7 创建时指定会话工作目录

- **触发**：新会话创建请求携带 `work_dir`，或用户从已有自定义目录会话进入新会话。
- **预期现象**：服务端只接受已存在的绝对目录；非法目录返回 HTTP 422，创建层也校验并拒绝。有效自定义目录写入会话元数据与会话索引，`authorized_dirs` 初值取该目录；创建响应和会话查询返回 `work_dir / work_dir_label / work_dir_is_default`。未指定时使用全局默认目录。
- **规则与边界**：目录创建后固定，换目录通过新建会话完成。显式选择全局默认目录时归入默认目录语义，避免重复分组。执行根按 `subagent_work_dir → git_worktree_path → work_dir → WORK_DIR` 取值，工具根、安全策略根、审计根及 early-tool 授权根共用 `session_work_root`；hook 工作根与改动审查锁随该根。会话库、附件/上传与识图对象仍集中保存在默认工作区；会话目录选择不迁移这些数据。
- **依据**：`agent_harness.py::normalize_session_work_dir / session_work_root_raw / session_work_root / session_work_dir_projection / SessionManager.get_or_create_session`、`webui.py::create_session`、`agent_loop.py::_react_node_once` 的 `worktree_root / security_workspace / audit_root` 接线、`session_authorized_dirs.py`、`plugins/change-review/host.py`；前端入口见 [05/06 · UC-5F11~5F13](../05-WebUI对话界面/06-会话档案与技能面板方案设计-UseCase清单.md)。

## 3. 边界

- 读类工具（read/ls/glob/grep）**可**访问工作区外路径（按工具规则），写类需授权——这是刻意的非对称规则。
- 授权目录的生成与存储见 02。
- 工作区文件列表、文件内容与媒体浏览接口当前继续以全局 `WORK_DIR` 解析；会话执行目录和集中存储/浏览根分别按上述契约使用。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-4A1 | `agent_harness.py` L127–136 |
| UC-4A2 | `agent_tools.py` L233–264 |
| UC-4A3 | L282–345、`session_authorized_dirs.py` L13–49 |
| UC-4A4 | L398–445 |
| UC-4A5 | `agent_tools.py` L1070、L1244–1454；`security/runtime.py` L201、L224 起 |
| UC-4A6 | `agent_harness.load_app_dotenv`；`scripts/subagent_ui_verify.py` |
| UC-4A7 | `webui.create_session`、`SessionManager.get_or_create_session`、`session_work_root* / session_work_dir_projection` 与执行根接线 |

## 5. 版本记录

- 2026-10-07 v4：新增 UC-4A7，记录会话目录创建校验、不可变语义、默认目录归并、执行/安全/审计根统一和全局集中存储边界；UC-4A1 改为按会话工具工作根描述。

- 2026-09-20 v3：新增 UC-4A6，明确隔离子进程必须显式关闭 dotenv 覆盖，防止临时 `WORK_DIR` 回落到生产 workspace。
- 2026-09-14 v2：新增 UC-4A5（Shell 路径解析以生效工作目录为基准），UC-4A3 补充交叉引用（配合当日路径基准修复）。
- 2026-09-13 v1：拆分首版（承接 UC-401）。
