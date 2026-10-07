# CHANGELOG — MCP 服务器配置与模型档案迁移至 .sugaragent（2026-10-06）

把工程根目录的两份**用户配置文件**也收进 `.sugaragent/`（该目录已在 `.gitignore` 中排除），根目录只保留源码、示例与脚本。延续 2026-10-03「根目录状态/临时文件迁移」的做法。

## 一、默认路径调整 + 旧文件自动迁移

- `mcp_servers.json`（MCP 服务器配置）：默认路径改为 `.sugaragent/mcp_servers.json`（`app/agent_mcp.py::_config_path`）。`MCP_SERVERS_PATH` / `MCP_SERVERS_JSON` 的优先级不变。
- `model_profiles.json`（模型档案）：默认路径改为 `.sugaragent/model_profiles.json`（`app/model_profiles.py::profile_store_path`）。
- 读取时若发现旧位置文件且新路径不存在，自动移动迁移（MCP 复用 `_migrate_legacy_state_path`，模型档案用 `_migrate_legacy_profile_store`）。模型档案的旧位置依次为项目根目录 `model_profiles.json` 与更早的 `app/model_profiles.json`；迁移失败（文件占用等）记警告并保留原文件。
- 两份文件已实际移入 `.sugaragent/`。
- 写盘前的目录创建沿用既有逻辑（`save_store` 与 `POST /api/mcp_config` 都会 `mkdir -p`）。

## 二、行为边界

- 配置内的**相对路径**（如 playwright 的 `--output-dir .sugaragent/playwright-mcp`、stdio 服务器未声明 `cwd` 时）仍相对**进程工作目录**解析，不随配置文件位置改变。
- API 与界面不变：`GET/POST /api/mcp_config`、`agent_mcp.get_config_path()`、设置中心展示的 `config.path` 会自动反映新位置。
- `.gitignore`：`.sugaragent/` 已整体忽略；根目录 `mcp_servers.json`、`model_profiles.json` 的忽略条目保留为遗留保护。

## 三、测试与文档

- `tests/test_sugaragent_state_paths.py` 新增 3 例：默认配置路径断言、MCP 配置迁移、模型档案迁移。
- `tests/test_model_profiles.py`：默认路径断言改为 `.sugaragent/`；原「读取 app/ 遗留位置」用例改为断言**迁移完成**（旧文件消失、新文件存在），并新增根目录遗留迁移用例；一处直接写 store 的用例补 `mkdir`。
- `tests/test_model_settings_controls.py`：能力预览不落盘的断言改为新路径。
- 同步更新：`README.md`、`SPEC.md`（11.4 与 11 配置规格）、`app/.env.example`、`app/agent_tokenizer.py`（环境说明文本）、设置中心前端文案（`sections_ext.js` / `sections_basic.js`）、`docs/settings_center_verification.md`、`docs/settings_hub_adaptation_plan.md`、`docs/execution_services.md`、`docs/hooks_plugins.md`、`docs/Agent 设计（用户方案）/`（MCP 接入、工具按需披露、启动与进程卫生、设置中心）、`plugins/repo-engineering/skills/repo-engineering/references/myagent.md`。

## 四、注意事项

- **正在运行的实例需重启后才会使用新路径**。重启前旧实例仍按根目录位置读写；若旧实例在重启前又写回根目录，新版本不会覆盖 `.sugaragent/` 中的文件，可手动删除根目录残留（与 2026-10-03 迁移的口径一致）。
- 重启前，运行中的实例可能读不到模型档案（`/api/model_profiles` 为空、发起对话会报缺少可用 profile），以及读不到 MCP 服务器配置（工具列表为空）。需要立即生效请重启服务（托盘图标「重启」或 `RUN.bat`）。
