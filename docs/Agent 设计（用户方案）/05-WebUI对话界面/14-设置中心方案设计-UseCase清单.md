# 设置中心（/settings）· 功能方案设计（UseCase 清单）

- 版本：2026-10-05 v2（覆盖至：当前工作区；遮罩/Esc 层级与 MCP 工具披露）
- 用途：逐条审查（四字段格式）；核对散落在多处的设置入口是否统一收敛为一个「设置中心」页面，以及分区注册、保存语义、缓存与脏数据保护的边界。
- 适用实现：`app/templates/settings_center.html`（无构建步骤的静态页）、`app/templates/static/settings/{core.js,sections_basic.js,sections_ext.js,sections_ops.js,plugin_sections.js,package_import.js,settings.css}`、`app/webui.py`（静态服务与设置相关路由）、`app/plugins/settings.py`（插件设置 schema）、`frontend/src/app/modules/settings.js`（聊天页齿轮入口与浮层接线）。
- 上级：`00-WebUI对话界面整体设计.md`｜相关：`06-会话档案与技能面板方案设计-UseCase清单.md`（模型档案管理）、[`../../settings_plugin_api.md`](../../settings_plugin_api.md)（插件设置页签声明接口）、`../../settings_hub_adaptation_plan.md`（参考实现学习与适配方案）、`../../settings_center_verification.md`（逐分区验证报告）。

---

## 1. 功能定位

把聊天页「界面设置」弹窗、`/setup/env`（`advance_config.html`，114KB）、`/setup/mcp`、`/setup/extensions` 与托盘两个菜单项这 **5 个散落入口**收敛为单一 `/settings` 设置中心：左栏分组导航（宿主 9 分区 + 插件声明页签）+ 右栏内容 + 顶部搜索；`/setup` 配置向导保持现状不动。旧路由 `/setup/env`、`/setup/mcp`、`/setup/extensions` 不删除，改为渲染同一页面并按 section 预选（深链兼容）。旧模板 `advance_config.html`、`mcp_config.html`、`extensions_config.html` 及其加载器删除，控件迁入各分区脚本。

## 2. UseCase

### UC-5N1 单一入口与深链兼容
- **触发**：从聊天页齿轮、`/settings`、旧路由 `/setup/env|mcp|extensions`、托盘菜单或插件页签进入设置。
- **预期现象**：都落到同一设置中心；旧路由按对应 section 预选展示；聊天页只保留齿轮入口与浮层（`#settings-center-overlay`），原 `settings-modal-root` 界面设置弹窗移除。
- **规则与边界**：不改 `/setup` 向导（它只依赖"是否存在可用 model profile"门槛）；旧路由只做预选重定向，不保留第二份实现。
- **依据**：`settings_center.html`、`webui.py::setup_page/settings 路由`、`frontend/src/app/modules/settings.js`、`shell-body.html / index.html`；回归 `tests/test_frontend_theme_variants.py`。

### UC-5N2 分区注册表与插件设置声明
- **触发**：打开设置中心；插件声明 `settings_schema` 或 `capabilities.ui.settings.section`。
- **预期现象**：宿主分区（常规/模型/技能/插件/Hooks/MCP/安全与权限/环境变量/目录与路径）与插件页签统一登记；插件页签标识为 `plugin:<id>:<section>` 并可用 `/settings#plugin:example.settings:main` 深链；`target: "settings"` 走宿主表单（读写 `/api/plugins/{id}/settings`），`target: "plugin-page"` 由宿主构造 `/plugins/{id}` 入口；未显式声明的 `settings_schema` 插件获得默认设置入口，显式空数组可关闭。
- **规则与边界**：名称按文本渲染不接受自定义跳转；安装/启停/热重载后同步入口，旧异步响应不覆盖新注册结果；schema 字段支持 `text/multiline/file/directory/secret` 控件与 `file/directory` 选择按钮。
- **依据**：`app/plugins/settings.py`、`app/plugins/ui.py`、`static/settings/plugin_sections.js`、`tests/test_plugin_settings.py`、`tests/test_settings_center.py`；接口文档见 `docs/settings_plugin_api.md`。

### UC-5N3 保存语义与写队列
- **触发**：任意分区点「保存」。
- **预期现象**：**只提交改动项**（环境变量/目录与路径不写空键）；`.env` 保存使用进程锁 + 唯一同目录临时文件 + flush/fsync + `os.replace`，保留文件权限，失败保留旧文件并清理临时文件（含 Windows 只读属性）；恢复默认会同步删除 `os.environ` 对应键（删除优先于同时提交的更新）。同值保存 `.env` 字节不变。
- **规则与边界**：写操作串行、失败明确报错；保存条常驻；密钥只写不读（`secret` 只显示配置状态）。
- **依据**：`sections_ops.js`、`webui.py::save_env_snapshot / set_ask_user_feature / _apply_env_updates`；回归 `tests/test_settings_review_safety.py`、`tests/test_settings_center.py`。

### UC-5N4 模型与推理强度控件
- **触发**：设置中心「模型」分区增删改/排序/启停/发现/探测；对话区模型选择器调整推理强度。
- **预期现象**：档案列表拖拽排序 + ↑↓ 键换位（顺序写回服务端可还原）；探测失败显示真实原因（HTTP 状态/响应体片段/异常文本）；推理强度随会话独立保存并按协议转换（详见 05/06·UC-5F9 与 01 模块）。
- **规则与边界**：档案业务语义归 01 模块；设置中心只承载控件与保存回环。
- **依据**：`sections_basic.js`、`model-profiles.js`、`tests/test_model_profiles.py`、`tests/test_settings_center_browser.py`。

### UC-5N5 搜索、缓存与资源版本
- **触发**：在设置中心搜索框输入；打开/切换分区。
- **预期现象**：搜索 150ms 防抖、仅隐藏现有行、保留焦点与未保存字段与 dirty 状态，重载后保留查询；慢分区响应不能覆盖已切换页面。静态资源：HTML 保留 `no-store`；白名单资源 `no-cache` + 内容 ETag（304），版本号用纳秒 mtime。
- **规则与边界**：未使用 `immutable`（同一资源 URL 服务端内容仍可更新）。
- **依据**：`static/settings/core.js`、`webui.py` 静态服务段；回归 `tests/test_settings_center.py`。

### UC-5N6 脏数据保护与关闭
- **触发**：返回、子页面 Esc/遮罩、宿主 Esc/遮罩与公共关闭 API；语言切换。
- **预期现象**：共用 dirty 检查——有未保存内容时取消关闭并保留输入，确认后才销毁 iframe；语言切换使用同一检查。
- **规则与边界**：关闭保护只针对脏状态；无改动时行为不变。
- **依据**：`sections_ops.js` / `core.js`、`tests/test_settings_center_browser.py`（无头 Edge 实测）、`tests/test_settings_modal_sections.py`。

## 3. 边界

- `/setup` 配置向导不动；与设置中心共享同一份 `.sugaragent/model_profiles.json`，互不侵入。
- 技能/插件安装区支持本地路径与目录或 ZIP/TAR 拖入（`/api/skills/install-upload`、`/api/plugins/install-upload`；≤5000 文件/≤200 MiB，拒绝非法路径与特殊文件）。
- 防脏写：验证流程逐分区比对 `.sugaragent/model_profiles.json`、`.sugaragent/mcp_servers.json`、`.sugaragent/skill_states.json`、`app/.env` 的 SHA256（见验证报告）。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-5N1 | `settings_center.html`、`settings.js`、`webui.py` |
| UC-5N2 | `plugins/settings.py`、`plugins/ui.py`、`static/settings/plugin_sections.js` |
| UC-5N3/5N6 | `sections_ops.js`、`core.js`、`webui.py` |
| UC-5N4 | `sections_basic.js`、`model-profiles.js` |
| UC-5N5 | `core.js`、`webui.py` 静态段 |

## 5. 版本记录

- 2026-10-05 v2：内编辑窗口支持遮罩关闭、Esc 优先关确认框/编辑窗（遮罩关闭不触发保存/确认）；MCP 页新增「工具按需披露」开关与按服务器批量启停/常驻按钮。
- 2026-10-03 v1：拆分首版——设置中心（/settings）落地：5 入口收敛单页、分区注册表与插件设置声明、只提交改动的保存语义（.env 原子写）、搜索/缓存/脏数据保护；旧模板与加载器移除，`/setup` 向导与旧路由深链兼容不变。待提交后补提交号。
