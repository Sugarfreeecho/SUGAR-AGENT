# CHANGELOG 2026-10-25 · 插件四级分层、打包范围与 web_search 插件化

## 1. 提交清单

| 主题 | 范围 |
|---|---|
| 插件四级分层与逐插件环境开关 | `app/plugins/tiers.json`、`app/plugins/tiers.py`、`app/plugins/manager.py`、`app/plugins/host.py`、`app/agent_extensions.py`、`app/templates/static/settings/sections_ext.js` |
| `web_search` 移交插件 | `app/agent_tools.py`、`plugins/web-search-providers/host.py`、`plugins/web-search-providers/.myagent-plugin/plugin.json` |
| 打包范围 | `packaging/scripts/prepare-payload.mjs`、`packaging/scripts/build.mjs`、`packaging/package.json`、`packaging/skills.allowlist.txt`、`packaging/README.md`、`packaging/HOWTO-另一台电脑打包.md` |
| 设计稿 | `docs/Agent 设计（用户方案）/06-能力扩展加载/01-插件加载与清单方案设计-UseCase清单.md`（UC-6A10）、`03-工具系统/05-检索提速与Web工具方案设计-UseCase清单.md`（UC-3E1）、`03-工具系统/工具系统能力清单.md` |

## 2. 主题要点

### 2.1 四级分层（唯一口径）

`app/plugins/tiers.json` 把插件固定为四档，运行期与桌面打包共用：

| 分级 | 插件 | 进包 | 设置页 | 默认 | 工具 |
|---|---|---|---|---|---|
| `system` | agent-goal、agent-team、session-todo | 是 | 隐藏 | 启用 | 常驻 |
| `system-external` | web-search-providers、execution-tools | 是 | 可见可开关 | 启用 | 常驻 |
| `extension` | desktop-notifications、computer-use、thread-monitor、change-review | 是 | 可见可开关 | 启用 | 延迟 |
| `standalone` | voice-input、chatgpt-subscription、feishu-transport、game-arena、repo-engineering、sugar-bili-scroll | 否 | 可见可开关 | 停用 | 延迟 |

- `system_builtin` 降级为“原生渲染/信任”标志，不再决定设置页可见性；可见性只看分级表。
- 未登记插件：可见、默认启用、不打包（保护用户自装插件）；未登记的老式内置插件仍隐藏（兼容既有行为）。
- 分级表登记为前三档但目录缺失时构建失败，避免改名后静默漏打。

### 2.2 逐插件环境开关

- 变量名 `PLUGIN_<ID>_ENABLED`（`-` → `_`、大写），例如 `PLUGIN_AGENT_GOAL_ENABLED=0`、`PLUGIN_EXECUTION_TOOLS_ENABLED=0`。
- 优先级：环境变量 > `.config/plugins-state.json` > 分级默认值；非法值忽略并告警。
- 环境变量生效时，设置页开关置灰并显示变量名；`bundled_host_plugin_enabled` 同步走同一判定，工具/路由状态与目录一致。

### 2.3 `web_search` 改为插件注入

- 从 `agent_tools.py` 删除 schema、实现、`tools` 分发表项与结果上限 helper（`OPENAI_TOOL_DEFINITIONS` 18 → 17）。
- `plugins/web-search-providers/host.py` 新增 `tool_definitions()`：注册 `web_search` invoker（`effect=read`、并行安全、可中断），执行时调用 provider registry。
- 插件停用后工具不再出现在模型工具目录；`tool_search.RESIDENT_TOOLS` 保留同名占位，供启用时保持常驻。

### 2.4 打包范围

- 插件：按分级表收录前三档（9 个），`standalone` 6 个不进包；`npm run payload:plugins` 预览，`--all-plugins` 全量。
- 技能：只打包 `packaging/skills.allowlist.txt`（当前 7 个），与运行时启停无关；`npm run payload:skills` 预览，`--all-skills` 全量。
- `runtime-manifest.json` 增加 `plugins` 字段（`mode` / `tiersFile` / `packaged` / `skipped`），`skills` 字段改为 `allowlistFile`。

## 3. 验证

- `python -m py_compile`：`tiers.py`、`manager.py`、`host.py`、`agent_extensions.py`、`agent_tools.py`、`web-search-providers/host.py` 通过。
- `node --check`：`prepare-payload.mjs`、`build.mjs` 通过。
- `pytest`（`--basetemp` 缩短路径，规避 Windows 260 字符限制）：
  - `test_plugins_core / test_plugin_catalog_loading / test_bundled_host_extensions / test_tool_search / test_plugin_ui_contributions / test_plugin_compatibility_adapters / test_plugin_manager_path_cache`：81 passed，1 skipped；
  - `test_agent_extensions_integration / test_security_core`：113 passed，1 skipped；
  - `test_settings_center / test_plugin_toggle_performance / test_change_review_plugin`：81 passed；
  - `test_plugin_installer`：8 passed（首次 5 项失败为临时目录路径过长，非代码问题）。
- 手工核对：`web_search` 已不在 `agent_tools`；插件侧注册成功（owner=`web-search-providers`、effect=`read`）；`tier_of('game-arena')=standalone` 且默认停用，未知插件仍默认启用；`PLUGIN_*` 覆盖即时生效。
- 打包预览：插件 9 打包 / 6 跳过；技能 7 打包 / 14 跳过。

## 4. 交付与遗留

- 运行期改动需重启后端生效；桌面安装包需重跑 `npm run payload`（不可用 `--skip-deps`，会缺 `ijson`）。
- 升级安装不会删除旧版本已落盘的 `standalone` 插件目录；新装用户不再包含它们。
- 本机 `.config/plugins-state.json` 中 `chatgpt-subscription`、`game-arena`、`sugar-bili-scroll` 有历史 `enabled: true`，源码运行仍启用；要验证“默认停用”需清条目或加 `PLUGIN_*_ENABLED=0`。
- 未做：`extension` 档的 `computer-use` 工具仍依赖 `cua-driver`（桌面依赖缺口见 2026-10-25 打包分析 R3）。
