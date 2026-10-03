# CHANGELOG — 根目录状态/临时文件迁移至 .sugaragent（2026-10-03）

把工程根目录的运行时状态与临时产物统一收进 `.sugaragent/`（该目录已在 `.gitignore` 中排除），根目录只保留源码、配置与脚本。

## 一、运行时状态文件（默认路径调整 + 旧文件自动迁移）

- `skill_states.json`（技能启停）：默认路径改为 `.sugaragent/skill_states.json`（`app/agent_tools.py`）。
- `mcp_tools_state.json`（MCP 工具启停）：默认路径改为 `.sugaragent/mcp_tools_state.json`（`app/agent_mcp.py`）。
- 读取状态时若发现旧版根目录文件且新路径不存在，自动移动迁移；技能状态迁移失败（如文件被占用）记录警告并继续读取旧文件，保留禁用状态。若旧文件也无法读取或解析，则显式报错，避免按全部启用处理。
- 两个旧文件已实际移入 `.sugaragent/`。

## 二、缓存与调试产物

- pytest 缓存：`pytest.ini` 增加 `cache_dir = .sugaragent/pytest_cache`；根目录 `.pytest_cache` 与 `frontend/.pytest_cache` 已移入 `.sugaragent/`（后者为 `pytest_cache_frontend`）。
- Playwright MCP 输出：`mcp_servers.json` 的 playwright 服务器增加 `--output-dir .sugaragent/playwright-mcp`；原 `.playwright-mcp/` 已移入。
- 原 `.tmp-change-review-dist/` 已移入 `.sugaragent/tmp-change-review-dist/`。

## 三、测试与文档

- `tests/test_sugaragent_state_paths.py` 新增 3 例：技能状态迁移、MCP 工具状态迁移、默认路径断言。
- 同步更新：`README.md`、`docs/settings_hub_adaptation_plan.md`、`docs/settings_center_verification.md`、`docs/Agent 设计（用户方案）/06-能力扩展加载/` 两处路径引用。
- `.gitignore`：注释更新，并补充忽略 `mcp_tools_state.json`（旧版遗留保护）。

## 四、注意事项

- 正在运行的实例需重启后才会使用新路径；重启前界面中的技能/MCP 启停可能显示为默认值（全部启用）。
- 若旧实例在重启前又写回根目录文件，新版本不会覆盖 `.sugaragent/` 中的状态，可手动删除根目录残留。
