# CHANGELOG — 2026-08-13

本批次来自 2026-08-13 的 3 个 Codex 会话：上下文估算修复、扩展注册审批泛化、深色主题与 UI 优化。

## 一、上下文估算修复（00:35）

- 根因：新会话发送前估算约 4k tokens，发送"你好"后突跳至 10k——发送前估算未计入工具 Schema。
- 修复（`agent_tokenizer.py` / `agent_loop.py`）：
  - 发送前估算现在包含内置、MCP 与插件工具 Schema（`compute_context_tokens_for_session`）。
  - ReAct 请求与右上角统计共用同一份工具列表（`build_combined_tool_definitions_for_session`）。
  - Provider token 缓存加入工具指纹，工具启停后不再误用旧缓存。
  - 效果：20 个内置工具约 6,271 tokens 提前计入，首发不再突跳。

## 二、扩展注册审批泛化（22:53）

- `MCP_REGISTRATION_APPROVAL_ENABLED` 泛化为 `EXTENSION_REGISTRATION_APPROVAL_ENABLED`：可执行 Plugin 首次启用/内容摘要变化、MCP 首次注册/配置摘要变化均受同一开关控制（默认 0 直接注册，设 1 需用户确认；旧开关无需兼容）。
- 输入框加号弹窗优化：MCP 页按服务器名称分类折叠，Plugin 页按插件名称分类折叠（`settings.js` / `skill-picker.js`）。
- 新增示例插件 `plugins/repo-engineering`（含 SKILL.md、agents、references）。
- MCP SDK 升级 `mcp==1.6.0 → 1.28.1`；README/hooks_plugins 文档同步。

## 三、深色主题与 UI 优化（23:39）

- 新增**深色主题**（`data-theme="deep-dark"`），原深色版本更名为紫色版本；前端配色参考 deepseek-harness-master 分析。
- 侧边栏/面板优化：因重叠自动收起后，手动展开保持开启不再自动收起；左右面板分别记录手动状态；窗口恢复安全宽度时解除手动覆盖。
- 设置弹窗分节、主题变体、注意力通知（UI 注意力通知初始化接入 `main.py` lifespan）、侧栏页脚、composer 侧控对齐等打磨。
- 设计示意稿（`frontend/ux-optimization-concept.html`、`extension-picker-demo.html`）保留在工作区，不入库。

## 其他

- `skill_states.json` 技能开关状态更新。
- 本地 MCP 配置（根目录 `mcp_servers.json`）与设计示意稿加入 `.gitignore`（本地文件，不入库）。
- `app/templates/dist` 已重建。
