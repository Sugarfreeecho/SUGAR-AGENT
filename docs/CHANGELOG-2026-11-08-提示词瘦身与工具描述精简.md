# CHANGELOG 2026-11-08 · 提示词瘦身、工具描述精简与 replace 语义修正

## 1. 提交清单

| 主题 | 范围 |
|---|---|
| 提示词重写 | `app/prompt.md`、`app/prompt.en.md` |
| 环境块中文化与瘦身 | `app/agent_tokenizer.py`、`app/agent_tools.py`、`app/agent_loop.py` |
| `replace` 只替换首段 | `app/session_system_context.py`、`app/agent_tokenizer.py`、`app/agent_loop.py` |
| 常驻工具描述精简（20 条） | `app/agent_tools.py`、`app/session_control/model_tools.py`、`app/session_workspace.py`、`app/tool_search.py`、`plugins/agent-goal/host.py`、`plugins/execution-tools/host.py`、`plugins/web-search-providers/host.py`、`plugins/web-search-providers/web_tools.py` |
| 细则下沉到技能 | `workspace/skills/sugar-agent-manual/references/03-tools.md`、`05-settings.md`、`06-goal-hooks-mcp.md`、`08-agent-self.md` |
| 测试对齐 | `tests/test_session_system_context.py`、`tests/test_context_breakdown.py`、`tests/test_tool_registry.py`、`tests/test_agent_tools_performance_paths.py`、`tests/test_agent_subagent_runtime_v2.py`、`tests/test_feature_flags.py` |
| 设计稿与对照 | `docs/SYSTEM-PROMPT-2026-11.md`、`docs/SYSTEM-PROMPT-2026-11-v2.md`、`docs/SYSTEM-PROMPT-2026-11-v3.md`、`docs/TOOL-DEFS-2026-11.md` |

## 2. 主题要点

### 2.1 系统提示词重写

| 段 | 之前 | 之后 |
|---|---|---|
| `system_identity` | 9 条 / 849 字 | 8 条 / 700 字 |
| `system_tool_contract` | 21 条 / 2989 字 | 10 条 / 1101 字 |
| `system_skills_intro` | 245 字（含临时文件段） | 86 字（只讲技能） |

- 身份段：合并“文件路径”与“图片”两条为一条 Markdown 交付规范（方括号文件名 + 圆括号完整本机路径）；“先回应再动手”去掉赘语；“问题不清”改为**主动用 `ask_user` 提问**；回答加量化上限（单问 ≤300 token、完整 ≤1000 token）。
- 契约段：改为“意图先行 / 先读后写写后必验 / 路径与搜索 / 批量与顺序 / 不重复不空转 / 依赖与环境 / 重启 / 用户交互 / 文件与交付 / 收尾与记忆”10 条；第 4 条明确“推荐同时调用 2–4 个参数已确定的工具”。
- 技能段：删除与契约重复的临时文件规则（该段是 2026-10-25 提交 `e1831d3` 的重复沉淀），只保留“技能不会自动执行 + `activate_skill` + 目录”。

### 2.2 环境块中文化与瘦身

- `build_env_static` 增加 `language` 参数：中文会话输出中文块，英文会话保留英文块；`describe_run_shell_executor_for_prompt` 同步增加中文分支。
- 只保留每轮都用得上的事实：月份、OS/Python、执行器 + 三个高频坑（`$` 展开、禁用 Bash `&&`/`||`、600 秒超时）、`WORK_DIR` 与虚拟 `/`、`TempOutput`、`AGENT_PROJECT_ROOT`、会话目录。
- 迁出：MCP 注册细节 → `06-goal-hooks-mcp.md`；Runtime V2 存储、`tool-results`、工作区外审批 → `03-tools.md`；自查入口 → `08-agent-self.md`。
- 体量：中文 2393 → **760 字**，英文 4298 → **1017 字符**。
- 机器依赖保持不变：`## Environment` 前缀、``(`WORK_DIR`):`` 与 ``(`AGENT_PROJECT_ROOT`):`` 的 ASCII 括号、精简版不含 `run_shell`。

### 2.3 `replace` 模式只替换首段

- 之前：`system_context_mode=replace` 丢弃静态段 1–3，只留自定义指令 + 精简环境，**技能目录一起消失**。
- 现在：只把第 1 段「角色与回答原则」换成会话自定义指令，工具契约、技能目录、环境照常保留；subagent 仍前置运行约束。
- 实现：`build_static_system_segments(..., include_identity=False)` + `assemble_session_system_segments` 的 replace 分支改为 `(自定义指令, *其余段)`；不再使用 `minimal=True` 环境块。

### 2.4 常驻工具描述精简（20 条）

- 37 个常驻工具的 `function.description` 合计 **14630 → 6659 字符（-54%）**；工具定义整体约 10561 token，description 占比从 49% 降到约 22%。
- 主要变化：`task` 2739 → 514、`run_shell` 1728 → 476、`apply_patch` 1048 → 381、`manage_scheduled_task` 755 → 329、`read_file` 745 → 300、`show_user` 664 → 337。
- 只改文字：工具名、参数名、类型、枚举、必填项全部未动；硬约束（唯一调用、审批、原子失败、禁区、不可凭回执宣称完成）逐条保留。
- 下沉内容：`task` 八种动作与媒体路由、`run_shell` 平台细节、`apply_patch` 补丁语法、`show_user` 各 kind → `03-tools.md`；定时任务 → `05-settings.md`；`update_goal` 四状态 → `06-goal-hooks-mcp.md`。

## 3. 验证

- `python -m py_compile`：`agent_tokenizer.py`、`agent_tools.py`、`agent_loop.py`、`session_system_context.py` 及 8 个工具定义文件全部通过。
- `pytest`（短 `TMP`）：`test_tool_registry` + `test_tool_search` + `test_agent_subagent_runtime_v2` + `test_session_system_context` **98 passed**；`test_session_system_context` 单独 **26 passed**；`test_session_workspace_paths` + `test_context_breakdown` + `test_tool_registry` **64 passed**；`test_agent_goal` + `test_goal_tool_continue` + `test_subagent_optimizations` + `test_subagent_parent_sync` **67 passed**。
- 重启后实测：37 个工具 description 合计 **6659 字符**，`task` 514 / `run_shell` 476 / `apply_patch` 381 / `grep` 192；中文环境块 760 字、英文 1017 字符；`replace` 会话 system 依次为「自定义指令 → 工具契约 → 技能目录 → 环境」。
- 已知无关失败（改动前即存在，已用 `git stash` 对照）：3 个 ripgrep 用例、`additionalProperties` 用例、3 个前端/子代理用例。

## 4. 注意

- 环境块与工具描述属后端代码，**需重启**才生效；提示词文件改动下一次请求即生效（静态段最多一代缓存陈旧）。
- 技能细则依赖 `sugar-agent-manual` 处于启用状态；禁用后只剩提示词里的原则。
