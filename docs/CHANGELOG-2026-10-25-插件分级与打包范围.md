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

### 2.5 修复：停用插件仍被加载（语音按钮/设置页签残留）

- **现象**：`voice-input` 在目录里显示 `configured_enabled=false`，但聊天页仍有语音按钮、设置页仍有“语音输入与朗读”页签。
- **根因**：`PluginManager._enabled_definitions()` 直接读 `.config/plugins-state.json`，无记录时按“启用”处理，绕过了分级默认值与 `PLUGIN_*` 环境变量。目录走 `is_enabled()`（false），加载器走旧逻辑（true），于是 `loaded=true`，`chat.extension` / `settings.section` 继续注入。
- **修复**：加载与目录改为同一优先级——环境变量 > 持久状态 > 分级默认值；新增回归 `test_tier_default_and_env_override_control_loading`，并把 `repo-engineering` 契约测试改为显式启用（standalone 默认停用）。
- **附带**：旧代码对 `system_builtin` 插件即使停用也保留 `settings.section`；`voice-input` 已归入 `standalone`，停用后不再保留任何 UI 贡献。
- **验证**：临时目录实测仅加载 9 个非 standalone 插件；`PLUGIN_VOICE_INPUT_ENABLED=1` 可恢复加载，`PLUGIN_AGENT_GOAL_ENABLED=0` 可停用内置；相关 pytest 118 passed / 1 skipped。

### 2.6 文案：插件的“已禁用”改为“未启用”

- `standalone` 插件是“默认未启用”，并未被用户主动禁用；聊天页技能选择器与设置页原先分别写“已禁用 / 已停用”，语义不一致。
- 统一为“未启用”（英文 `Not enabled`）；切换按钮仍保留“启用 / 停用”的动作语义，`已禁用` 继续用于用户主动关闭的 Skill / MCP 工具。
- `setup_i18n.js` 补充 `未启用`、`已停用` 的英文映射；`frontend/src` 与 `app/templates/dist` 同提交（vite build，9.66s）。

### 2.7 插件可用性体检与体检会话

- 每个插件行新增「检查可用性」按钮；**刚由未启用打开**（本地待检查标记）或**已启用但 `loaded=false`**（启用失败）时按钮高亮（橙色描边），刷新后仍保留待检查标记。
- 后端新增 `GET /api/plugins/{id}/availability`：静态检查全局开关、启用状态、清单兼容性、trusted_host 路径、`requirements.txt` 依赖、必填配置、Web/runtime 入口，返回 `ready / degraded / unavailable` 与逐项证据。
- 后端新增 `POST /api/plugins/{id}/diagnose`：建一个诊断会话，把报告写进首条提示词返回；设置页用一次性 localStorage 键把提示词交给主界面，`/?session=<id>` 打开后自动发送，Agent 实际调用工具/页面复核，再按阻塞项逐步引导（不自行改源码/配置）。
- 新增 `tests/test_plugin_availability.py`（5 项）；连同设置中心、插件核心与目录测试共 56 passed / 1 skipped。前端 `vite build` 13.48s，src 与 dist 同提交。

### 2.8 修复：体检会话多开一页、任务未发出

- **多开一页**：设置中心实际是应用内的 `iframe` 浮层（`settings.js:mountSettingsCenter`），体检按钮却用 `window.open('_blank')`，于是额外弹出一个完整应用页。改为先 `postMessage({type:'myagent:plugin-diagnose'})` 交给宿主：宿主关闭设置浮层、切换会话并发送；只有设置页被单独打开（无父窗口）时才在当前标签导航。
- **任务没发出**：深链 `/?session=<id>` 在 `layout-panels.init()` 里就被消费并清空 `pendingQuerySession`，`loadSessionList` 的深链分支永远看不到它，自动发送从未执行。现在 `init()` 恢复会话后直接调用 `maybeAutoSendPluginDiagnose(lastSessionId)`；同时把宿主入口收敛为 `window.myagentOpenPluginDiagnose(sessionId, prompt)`。
- **现场证据**：会话 `75e21c91-b14c-4d3a-9f68-9a4724e1e854` 的 `events.jsonl` 只有 `session_meta` 与 `extension_state_changed`，没有 user 事件，也没有 run。
- **验证**：`vite build` 5.89s；dist 含 `myagentOpenPluginDiagnose`（3 处）、`myagent:plugin-diagnose`（1 处）与 `pluginDiagnosePrompt`（8 处）。设置静态 JS 不再出现 `window.open`。

### 2.9 体检会话带上插件目录并主动命名

- 原提示词只给插件 id / 名称 / 版本，Agent 不知道插件装在哪；会话工作目录也停在默认 workspace。
- `diagnosis_prompt` 新增「插件位置」段：插件目录、清单文件、`requirements.txt`（存在时）、插件页面、设置接口与可用性接口。
- `POST /api/plugins/{id}/diagnose` 创建会话时把 `work_dir` 设为插件目录（路径不可用时回退默认目录，并在提示词里省略工作目录行）。
- 会话创建后立即 `set_session_name` 为「插件体检 · <插件名> v<版本>」，不再等首轮结束后的自动命名。
- 验证：`tests/test_plugin_availability.py` 断言提示词含插件目录与工作目录行，工作目录为空时省略。

### 2.10 Standalone 插件依赖清单与获取方式

- 6 个 `standalone` 插件都补了 `requirements.txt`：`voice-input`（sherpa-onnx、numpy）、`chatgpt-subscription`（PyJWT[crypto]、pywin32）、`sugar-bili-scroll`（aiohttp、bilibili-api-python、pillow、faster-whisper）；`feishu-transport`、`game-arena`、`repo-engineering` 为“无第三方依赖”的注释清单。
- 新增 `docs/standalone-plugin-dependencies.md`：依赖总表、安装目标（应用内置运行时 / 插件 venv）、外网 PyPI、华为云镜像、华为内网 `PIP_INDEX_URL`、离线 wheel 与自检命令。
- 安装器识别“仅注释”的 `requirements.txt`，不再为无依赖插件创建 `.myagent-runtime` venv。

### 2.11 安装包补入 agent-client-protocol

- 新增的 `acp-agents` 插件（`extension` 档，随包）依赖 `agent-client-protocol`，但桌面依赖清单缺失，冒烟日志报 `ModuleNotFoundError: No module named 'acp'`。
- `packaging/requirements.desktop.txt` 加入 `agent-client-protocol==0.12.1`，载荷自检增加 `from acp.schema import HttpMcpServer, McpServerStdio`。
- 重跑全量载荷：6,640 文件 / 229.8 MB / **72 个依赖**；`smoke-payload` 健康检查通过，日志不再出现插件安装失败。

### 2.12 飞书 SDK 改为按需安装、删除重复词表

- 核心的飞书远程控制实现留在 `app/remote_control/transports/feishu/`，`feishu-transport` 插件只负责启停；`lark_oapi` 在 `FeishuSDKTransport.build()` 内懒加载，`FEISHU_ENABLED` 默认关闭。安装包此前无条件内置整个 SDK（`lark_oapi.zip` 45.4 MB + `pycryptodome` 4.5 MB + `websockets` + `requests-toolbelt`）。
- `requirements.desktop.txt` 移除 `lark-oapi`；`archive-runtime.py` 在 SDK 不存在时返回 `sdk: null`，`runtime-archives.cjs` 允许空 SDK 并拒绝残留归档；自检仅在检测到 `lark_oapi` 时校验 zip。飞书指南补充桌面版手动安装命令。
- `app/tools/deepseek_v3_tokenizer/` 下重复的嵌套副本（含 7.5 MB `tokenizer.json`）无任何引用，删除；`agent_tokenizer.py` 只读顶层 `tokenizer.json`。
- 重跑全量载荷：**6,239 文件 / 171.6 MB / 68 个依赖**（-58.2 MB）；`runtime-archives.json` 为 `{"sdk": null, "pptIcons": null}`，`smoke-payload` 健康检查通过。

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
