# SugarAgent 设置中心（单页集成）学习适配方案

> 分析对象：ZCode（`D:\AI\AI Agent\OpenAgent\ZCode-main`）、DeepSeek Harness 简称 DSH（`D:\AI\AI Agent\OpenAgent\Deepseek Harness\deepseek-harness`）
> 落地对象：SugarAgent（本仓库）
> 目标：**把当前散落在 5 个入口的设置活动全部集成到一个「设置中心」页面里**；`/setup` 配置向导保持现状不动。

---

## 1. 结论先行

1. **两家参考实现的形态不同，但收敛结论一致**：ZCode 是「应用内全屏设置页 + 左栏分类 + 右栏内容」（`packages/ui/src/SettingsPage.tsx`），DSH 是「主窗口内的模态对话框 + 左栏 188px 分类 + 右栏表单」（`ui-settings-general/src/client/SettingsRoot.tsx:76-84`、`SettingsRoot.module.css:89-90, 109-116`）。**都把全部设置收进一个页面/面板，用分类导航切换，而不是散成多个独立页面。**
2. **SugarAgent 当前恰恰是散页形态**：聊天页「界面设置」弹窗（`frontend/src/app/modules/settings.js`）+ `/setup/env`（`app/templates/advance_config.html`，114KB）+ `/setup/mcp`（`mcp_config.html`）+ `/setup/extensions`（`extensions_config.html`）+ 托盘两个菜单项（`tray_launcher.py:894-896`），其中 MCP、插件、权限在三处以上存在重复入口与重复实现。
3. **建议方案**：新增单一 `/settings` 设置中心页（无构建步骤的静态页，与现有 setup 页同源），采用**注册表驱动的分区（section）** 结构（学 DSH 的 `settings.section` 槽位），左栏分组导航 + 右栏内容 + 顶部全局搜索（学 ZCode 的导航/面包屑/作用域徽标），**统一保存语义与串行写队列**（学 ZCode 的 `settingsWriteQueue`），**显示"默认 / 已覆盖"来源三态与密钥只写不读**（学 DSH 的 `describe(value/base/user)` 与 `credential-ref`）。
4. 旧路由 `/setup/env`、`/setup/mcp`、`/setup/extensions` **不删除**，改为渲染同一个设置中心并按 section 预选（深链兼容），保证托盘、文档、现有测试与用户收藏链接不断。
5. `/setup` 配置向导**完全不动**：它只依赖"是否存在可用 model profile"这一门槛（`app/webui.py:7187-7223`），设置中心与它共享同一份 `.sugaragent/model_profiles.json`，互不侵入。

---

## 2. 分析基线与方法

| 项 | 内容 |
|---|---|
| 参考 A | ZCode 主仓，重点 `packages/ui/src/settings/*`、`packages/services/src/setting/*`、`lib/settingsNavigation.ts`、`settingsPageConfig.ts` |
| 参考 B | DSH 主仓，重点 `packages/client/ui-settings*/`（10 个包 + README.zh.md）、`packages/settings/settings/src/*`、`packages/client/AGENTS.md` |
| 本文对 SugarAgent 的证据 | 仓库内静态阅读，均给出「文件:行」引用；未运行任何修改 |
| 未验证项 | ZCode `migration` section 无入口（疑似 dead path）；DSH `navIcon` 里 `archived-sessions` 无注册方。两者均不影响本方案 |

---

## 3. 参考实现 A：ZCode 设置页

### 3.1 容器与入口

- 设置是 tabStore 里的**合成 tab**（`id: "__settings__"`，`packages/ui/src/store/tabStore.ts:24-31`），不是路由也不是对话框；有工作区时以 `absolute inset-0 z-10` 覆盖层压在 workspace 之上并把底层 `inert`（`root/RootWorkspaceContent.tsx:100-105, 181-200`），无工作区时整页渲染（`Root.tsx:1000-1010`）。
- 四个入口进同一页面：侧栏齿轮（`WorkspaceSidebarFooter.tsx:372-382`）、`Cmd/Ctrl+,`（`packages/shared/src/shortcutCommands.ts:68`）、命令中心两条命令（`quickpick/quickPickCommands.ts:96-103, 196-202`）、任务列表/输入框上下文入口。
- 布局：`grid-cols-[68px_minmax(0,1fr)]`，`lg` 起 `grid-cols-[268px_minmax(0,1fr)]`；右栏内容固定 `max-w-4xl` 且自身滚动（`SettingsPage.tsx:1375`、`settings/SettingsPageParts.tsx:19`、`SettingsPage.tsx:1616`）。窄屏左栏收成 icon rail（`:249-252`）。

### 3.2 信息架构

一级导航 **3 组 16 个 section**（`settings/settingsPageConfig.ts:30-128`）：基础设置（常规/外观/模型供应商/浏览器控制/电脑控制/快捷键/工作区搜索范围）、Agent 能力（记忆/子智能体/插件/MCP 服务器/技能/命令/定时任务/钩子）、数据与统计（使用统计）。含隐藏门控 `HIDDEN_SETTINGS_SECTIONS` 与旧 id 归一（`lib/settingsNavigation.ts:36-45, 90-97`）。

二级导航三种形态并存：页内 Tabs（插件/MCP/技能计数）、section 内左栏（provider 分组可拖拽排序）、详情页 + **面包屑**（`SettingsHeaderBreadcrumb.tsx:20-145`）。最深 3 层。

页面组织原语收敛为 4 个组件：`SettingsRow`（label/description 左、192px 或 280px 控件右，`SettingsPageParts.tsx:107-152`）、`SettingsGroupCard`、`SettingsResourceGroupHeader`（标题+计数+操作）、`SettingsResourceList`（行容器 + 行级点击但跳过内部控件，`settingsResourceRowInteraction.ts:5-24`）。

### 3.3 交互与保存语义

- **默认即时生效**：开关/下拉直接 `updateSharedSettings(...)`（`SettingsPage.tsx` 多处）→ `settingService.update` → 落盘 → 重新拉取。
- **显式保存的少数例外**：数据目录（脏值门控 + 明确"需重启"提示，`DataBaseDirControl.tsx:38-137`）、`.zcodeignore` 编辑器（dirty 文案 + `Ctrl/Cmd+S`）、provider 表单（草稿只写改动叶子，`model-provider-section/ProviderDraftSave.ts:46-101`）。
- 拖拽排序用**乐观更新 + 串行持久化**（`useOptimisticReorder.ts:20-75`）。
- **作用域徽标** `default | user | workspace`（`SettingsScopeBadge.tsx:7-34`）+ 作用域下拉（`PluginScopeMenu.tsx:14-31`）。
- 搜索**只在分区内**：插件/MCP/技能/命令、钩子、子智能体、记忆文件、快捷键各有一份过滤实现，且插件搜索带**中文拼音全拼 + 首字母**（`pluginSearch.ts:1-35`）。**没有全局设置搜索。**
- 校验：表单逐字段消息；服务端错误码兜底提示（`settings-errors.ts:4`）。

### 3.4 数据流与工程细节（最值得学的部分）

- 单一 Json 存储 `~/.zcode/v2/setting.json`（`settingService.ts:53-63`），读失败/校验失败回默认值，坏 JSON 连续重试 3×300ms 后改名隔离 `setting.json.corrupt-<ts>`（`:69-95`）。
- 写入 = 「读最新 → 合并 patch → schema 全量校验 → 原子写 + rename 提交」（`:200-345`）；**单写队列**，单次写 30s 超时（`settingsWriteQueue.ts:1`），且**超时只允许发生在提交（rename）之前**，进入提交临界区后必须收口（`settingsWriteQueue.ts:17-49`）——防"旧写晚到覆盖新设置"。`get()` 先 `await updateQueue` 避免读到写前值（`:284-290`）。
- 写前字段归一（`normalizeSettingsPatch.ts:3-93`，如 `locale → localePreference`、`mode:"auto"` 表示删除覆盖）。
- 提交后事件 `onDidUpdate({keys})`（`observableSettingService.ts:13-30`）；UI 侧以 service 实例为 key 的 WeakMap store 订阅（`hooks/useSettingService.ts:21-56`）。
- **两条持久化通道**（app 级 Json + theme/locale/字号走 localStorage，`store/index.ts:255-296`）——被 ZCode 侦察报告列为"反面"：同页同类设置保存机制不同。

### 3.5 可借鉴 / 不照搬

**借鉴**：写队列与提交临界区、坏配置隔离、section 意图 + 上次停留位置（`settingsNavigation.ts:23-33, 130-264`）、面包屑由外壳统一渲染（section 只上报 label）、乐观排序、作用域双表达、拼音搜索、行级交互三件套。

**不照搬**：单文件 1962 行 + 巨型 switch 的 section 分发；`plugin` 聚合页与 `mcp`/`skill`/`commands` 并列入口造成的**同一功能两个入口**；僵尸 section 与迁移别名长期共存；把插件商店/远端同步/外部 Agent 导入塞进设置页的"控制台化"膨胀。

---

## 4. 参考实现 B：DeepSeek Harness 设置面板

### 4.1 容器与入口

- **模态对话框**（`role="dialog" aria-modal="true"`），`createPortal` 到 `document.body`，遮罩点击/关闭按钮/`Escape` 三条关闭路径（`ui-settings-general/src/client/SettingsRoot.tsx:76-84`）。三个入口：侧栏底部齿轮、`settings.open`（默认 `Mod+,`，六套平台默认绑定，`ui-settings-general/src/client/index.ts:180-190`）、账号插件贡献的 `settings.launcher` 菜单。
- 尺寸：面板 `width:800px`、高 `min(800px, 100vh - 2*max(24px, 顶部拖拽区))`；左栏 188px 导航 + 右栏表单，两栏各自滚动（`SettingsRoot.module.css:89-90`、`:109-116`、`:173-222`）。注意 README 仍写 760×500（**文档漂移**）。
- 没有独立设置窗口；桌面与 Web 共用同一 React 模态（差异只在个别分区内容）。

### 4.2 信息架构与「设置即插件」

- 一级导航由 `settings.section` **账本投影**并 `order` 排序（`ui-settings-general/src/client/index.ts:139-160`）。实际注册 5 项：`account`(-10)、`general`(0)、`models`(10)、`plugins`(15)、`agent-presets`(20)。
- `general` 本身是**行槽位** `settings.general.item`（`GeneralSection.tsx:15-18`），注册顺序：language(0) / appearance(10) / font-size(11) / link-opening(14) / developer-tools(15) / shortcuts(20) / current-version(100)。
- **8 个 slot 类型集中声明**在 `ui-settings/src/client/contract/slots.ts:15-100`（launcher/trigger/header/action/close/section/plugins.tab/onboarding/general.item）；壳**零自带文案**，label 由注册方提供且是随语言变化的 thunk，账本 bump 兼作壳重渲染信号（`slots.ts:57-64`）。
- 新页注册成本：`ctx.slots.inject('settings.section', () => ctx.slots.register({name,id,order,label,locale,children}, Component))`；跨命名空间页用 `ctx.configForms.whileServed([ns], register)`，宿主不服务该命名空间时页面**完全消失**（`ui-settings/src/client/config-form.ts:317`）。
- 插件配置页挂在**核心 Plugins 页**而不是设置里（`ui-plugin-manager`），形成"只读清单一处、可改入口另一处"的**双入口问题**（其报告的反面清单第 2 条）。

### 4.3 交互与保存语义

- **保存双轨**：General 行即时生效；插件配置页是**暂存 + 显式 Save**，离开即丢弃草稿（`SettingsForm.tsx:60-72`）。
- 字段三态 `text / overridden / invalid`；**"已覆盖"按用户层是否含该字段判定，而不是比值**（`form-model.ts:52-56`），并提供单字段「恢复默认」（`resetField → unset`）。
- 客户端用序列化 schema 本地校验，非法草稿置灰 Save 并就地换文案（`schema.ts:59-68`、`fields.tsx:108`）；Host 端再整体校验，冲突返回 `settings/conflict` / `settings/rejected`。
- **每次写带 revision 栅栏**，冲突保留草稿而不是覆盖（`config-form.ts:140-150`）。
- **秘密只写**：密钥用 `credential-ref` 角色，远端强制 `redactSecrets`，响应只回 `{path, set}` 存在性。
- 无全局搜索、无导入导出、无整体重置；唯一"底层编辑"入口是「打开配置文件」（仅 loopback）。

### 4.4 数据流

- 分层：**schema 默认值 → 组合层(base) → 用户覆盖层(user)**；`describe` 同时下发 `value/base/user/revision/secrets`（`packages/settings/settings/src/types.ts:24-46`）——页面天然能显示"来源三态"。
- 持久化到当前 profile 的 `cordis.patch.yml`（`$DSH_HOME/profiles/<name>/`），改盘前校验完整候选值，支持原子替换并保留注释与 `!!js`。
- 客户端唯一读取方 `SettingsDescribeMirror` 订阅 `settings/document-updated`，写应答用 `acceptView` 折回，避免二次拉取（`settings-mirror.ts:76-122`）。
- **非 loopback 浏览器降级为 memory 模式**（不写 Host，刷新即回默认）——把"远程只读/降级"显式化。

### 4.5 可借鉴 / 不照搬

**借鉴**：槽位账本即导航（新增分区零改外壳）、`whileServed` 让页面随能力出现/消失、revision 栅栏 + 写应答折回、覆盖按"键存在性"判定、秘密只写只回存在性、统一表单模型 + 字段 spec、壳零文案（文案随 locale thunk）、portal 规避 macOS 拖拽区吞点击、连接/更新状态内联进标题栏。

**不照搬**：一个 host 命名空间一个 UI 包（settings 家族 10 包 + 插件 4 个伴生包，大量空 node 半侧）；插件配置双入口；无搜索/无导入导出/无整体重置；命名空间里"有 schema 无 UI"的字段（`web-search-deepseek` 的 `model`/`apiVersion`/`maxTokens`）。

---

## 5. 两家对照与共识

| 维度 | ZCode | DSH | 对 SugarAgent 的结论 |
|---|---|---|---|
| 容器 | 应用内全屏设置页（合成 tab + 覆盖层） | 主窗口模态对话框（portal） | 取"**一个页面**"；形态选静态页（见 §8 D1） |
| 导航 | 3 组 16 分区 + 面包屑 + 页内 Tabs | 5 分区（order 账本）+ 行槽位 | **注册表驱动 + 分组**，分组数控制在 5 以内 |
| 全局搜索 | ❌（仅分区内，带拼音） | ❌ | **要做**，且带拼音（抄 `pluginSearch.ts` 思路） |
| 保存语义 | 默认即时，例外显式（脏值门控 + 重启提示） | 双轨（即时 / 暂存+Save） | **按字段类型显式声明**，禁止"隐式整文件覆盖" |
| 并发写 | 单写队列 + 提交临界区不可超时 | revision 栅栏 + 冲突保留草稿 | 两者都要：**前端串行 + 后端版本/冲突语义** |
| 来源可见性 | 作用域徽标 default/user/workspace | value/base/user 三态 + 恢复默认 | **显示"默认 / 已覆盖" + 一键恢复默认** |
| 密钥 | — | 只写只回存在性（credential-ref） | 已有 `_env_key_sensitive`（`webui.py:7498`），升级为"只写 + 显示是否已配置" |
| 扩展贡献 | 固定 section 列表（config 驱动） | 完全槽位化，第三方可插 | SugarAgent 已有 `settings.section` 插件槽（`plugin-ui-slots.js:169`）→ **合并进同一页面** |
| 主要缺点 | 巨文件 + 双轨 IA + 双持久化通道 | 包膨胀 + 插件配置双入口 + 无搜索 | 都要在 SugarAgent 里提前规避 |

---

## 6. SugarAgent 现状清点

### 6.1 现有设置入口全景

| 入口 | 目的地 | 代码位置 |
|---|---|---|
| 聊天页侧栏齿轮「界面设置」 | 弹窗：字体大小 / 界面风格 / 会话目录 / 语言 / 「高级设置」按钮 / 插件设置分区 | `frontend/src/shell-body.html:211-247`（按钮在 `:243`）、`frontend/src/app/modules/settings.js:49-102, 141-198` |
| 弹窗「高级设置」 | `/setup/env` | `settings.js:181-196` |
| 聊天页 composer：模型下拉 | 模型档案切换/启停 | `frontend/src/app/modules/model-profiles.js` |
| 聊天页 composer：权限下拉 | 权限模式（会话级） | `frontend/src/app/modules/permissions.js:1-41` |
| 聊天页 composer：Skill 弹层 | 技能 / MCP 工具与服务器 / 插件 三个页签的启停 | `frontend/src/app/modules/skill-picker.js:534-680` |
| 托盘菜单 | 「高级设置」→ `/setup/env`；「MCP 配置」→ `/setup/mcp` | `app/tray_launcher.py:894-896`；`app/platform_tray_macos.py:70-73`；`app/platform_tray_linux.py:91-92` |
| 页面互链 | advance_config → `/setup/extensions`（"安装 / 完整管理"）；mcp_config → `/setup/env#mcp` | `advance_config.html:666`、`mcp_config.html:397` |
| 配置向导 | `/setup`（**本次不动**） | `app/webui.py:7221-7234`、`app/templates/first_time_config.html` |

### 6.2 设置活动清单（现状 → 目标分区）

| # | 设置活动 | 现状位置 | 存储 / API | 目标分区 |
|---|---|---|---|---|
| 1 | 界面风格、字号、会话目录密度、语言 | 聊天弹窗 | localStorage：`myagent-theme` / `myagent-font-level` / `myagent-session-list-mode` / `myagent-language`（应用逻辑 `settings.js:88-102`） | 常规 › 外观与语言 |
| 2 | 新会话默认权限模式 | 聊天页权限下拉 | localStorage `myagent-new-session-permission-mode`（`permissions.js:4-41`） | 常规 › 新会话默认 |
| 3 | 新会话默认模型档案 | 聊天页模型下拉 | localStorage `myagent-new-session-model-profile`（`model-profiles.js:10-36`）+ `/api/model_profiles` | 常规 › 新会话默认 |
| 4 | 模型档案 CRUD / 排序 / 启停 / 上下文探测 | `/setup/env`「模型配置」 | `.sugaragent/model_profiles.json` + `/api/model_profiles*`（`webui.py:3684-3798`） | 模型与连接 › 模型档案 |
| 5 | 环境变量分组编辑（7 组 + 其他） | `/setup/env`「环境变量」 | `app/.env` + `/api/env`（`webui.py:7249-7370` 分组表、`:8093` 读、`:8189` 写） | 运行时与环境 › 环境变量 |
| 6 | MCP 服务器配置（JSON 文本） | `/setup/env`「MCP」、`/setup/mcp` | `.sugaragent/mcp_servers.json` + `/api/mcp_config`（`webui.py:8045-8092`） | 能力与扩展 › MCP |
| 7 | MCP 工具开关 / 服务器注册 | 聊天页 Skill 弹层「MCP」页签 | `/api/mcp/tools`、`/api/mcp/servers/{name}/register`、`/api/mcp/tools/{fn}/enabled` | 能力与扩展 › MCP |
| 8 | 插件启停 | 聊天页 Skill 弹层「插件」、`/setup/env` 插件表 | `/api/plugins/{id}/enabled`（`webui.py:7828`） | 能力与扩展 › 插件 |
| 9 | 插件安装 / 更新 / 删除 / 依赖 | `/setup/extensions` | `/api/plugins/install`、`DELETE /api/plugins/{id}`、`/dependencies` | 能力与扩展 › 插件 |
| 10 | 插件设置表单（schema 驱动） | 聊天弹窗底部 `#plugin-settings-sections` | slot `settings.section`（`plugin-ui-slots.js:169,364,1175`）+ `/api/plugins/{id}/settings` GET/PATCH | 能力与扩展 › 插件 |
| 11 | Hooks 开关状态与注册列表 | `/setup/env`、`/setup/extensions` | `hooks.json` + `/api/extensions`（`webui.py:7615`） | 能力与扩展 › Hooks |
| 12 | 扩展重新发现 / 热重载 | 上述页面按钮 | `/api/extensions/reload`（`webui.py:7911`） | 能力与扩展（各区头部动作） |
| 13 | 技能启停 | 聊天页 Skill 弹层 | `.sugaragent/skill_states.json` + `/api/skills/{name}/enabled` | 能力与扩展 › 技能 |
| 14 | 权限规则（allow / ask / deny） | `/setup/env`「安全与权限」、审批卡片"始终允许" | `/api/security/rules`（`webui.py:3839-3902`） | 安全与权限 › 权限与规则 |
| 15 | 扩展信任与注册审批（MCP + 可执行插件） | 同上 + 审批卡片 | `/api/security/extensions*`、`/api/security/mcp/{id}/registration` | 安全与权限 › 扩展信任 |
| 16 | web_fetch 预批准域名 | `/setup/env`「安全与权限」 | `/api/security/web-fetch-domains` | 安全与权限 › 网页抓取 |
| 17 | 工作区范围许可 / 自动审查开关 | 同上 | `/api/security/settings`（`webui.py:3799-3827`，字段 `auto_review_enabled`、`allow_external_workspace_ops`） | 安全与权限 › 工作区与自动审查 |
| 18 | Ask User 功能开关 | **无 UI（后端已就绪）** | `/api/features/ask-user` + `.env ASK_USER_ENABLED`（`webui.py:8140-8186`） | 常规 › 功能开关 |
| 19 | 其它总开关（SECURITY / EGRESS_HELPER / HOOKS / PLUGINS / EXTENSION_REGISTRATION_APPROVAL / AGENT_TEAM） | 混在环境变量文本里 | `.env`（默认注入见 `webui.py:8099-8106`；`AGENT_TEAM_ENABLED` 见 `app/agent_team/config.py:9`） | 常规 › 功能开关 |
| 20 | 托盘 / 文档 / 面板互链 | 见 §6.1 | — | 统一收敛到「设置中心」+ 深链 |

> 说明：会话级设置（当前会话的模型与权限模式）**不进设置中心**，中心只提供"新会话默认值"，避免把"当前状态"和"默认配置"混在一页（ZCode 用作用域徽标表达同类区分，SugarAgent 用分区归属表达）。

### 6.3 现存问题（单页集成的动因）

1. **同一功能有两套以上入口**：MCP 在 `/setup/env` 的 MCP 页签、`/setup/mcp`、聊天弹层三处可改；插件在 `/setup/env`、`/setup/extensions`、聊天弹层三处可改（与 DSH 的"插件配置双入口"同病）。
2. **功能开关没有一手界面**：`/api/features/ask-user` 有完整 GET/POST（含测试 `tests/test_human_interaction.py:670` 断言该端点），但**全仓库没有任何前端调用它**；`HOOKS_ENABLED`/`PLUGINS_ENABLED` 等只能去环境变量大表单里找原始键名。
3. **主题键值不一致**：设置页只区分 dark / light（`advance_config.html:12`、`mcp_config.html:12` 都是 `!== 'dark'` 就加 `theme-light`），而聊天页有 light / purple / deep-dark 三态（`settings.js:49-53` 判定、`:88-102` 应用）→ **紫色主题在设置页显示成浅色**。
4. **无全局搜索、无来源提示、无统一保存语义**：环境变量是"整表单保存"，MCP 是"保存并重载"，模型是"保存为新配置"，插件设置是 form PATCH，四种语义混在一个入口链路里。
5. **三个设置页各自复制一套主题/导航/按钮样式**（advance_config 114KB / mcp_config 19KB / extensions_config 11.6KB），改一处要同步三处。
6. **契约测试与模板强耦合**：`test_feature_flags.py:152`、`test_enablement_ui_contract.py:9/84`、`test_model_profiles.py:860/897`、`test_llm_transport.py:930`、`test_agent_extensions_integration.py:151/155/166`、`test_plugin_installer.py:222` 都直接读模板文本断言 → 任何结构调整都必须同步这批测试（这是本次改造的主要"隐藏成本"）。

---

## 7. 目标架构：设置中心 `/settings`

### 7.1 设计原则（由两家借鉴收敛而来）

1. 一个页面，一份导航账本；**新增一个分区=注册一个 section，不改外壳**（学 DSH 槽位）。
2. **全局唯一归属**：同一个配置键只允许有一个"可编辑"分区，其它分区只做只读引用 + 深链跳转（防 ZCode/DSH 的双入口问题）。
3. 保存语义必须显式声明：`instant`（即时）/ `explicit`（显式保存）/ `readonly`（只读展示）。
4. 写入串行化 + 冲突可见（学 ZCode 写队列 + DSH revision）。
5. 来源可见：`默认 / 已覆盖（.env 或本地）/ 会话级生效` 三态；一键恢复默认。
6. 秘密只写：API Key 类字段显示"已配置 / 未配置"，永不回显明文（现有 `_env_key_sensitive` 已有判定基础）。
7. 危险操作统一二次确认（删除模型档案、覆盖 MCP JSON、清空权限规则、卸载插件、撤销工作区范围许可）。
8. 语言与主题与聊天页**共用同一 localStorage 键**，并修掉 purple 的处理差异。

### 7.2 页面骨架

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ← 返回聊天   设置中心            [🔍 搜索设置项…]      [中/EN] [配置向导]   │
├──────────────────┬──────────────────────────────────────────────────────────┤
│ 常规             │  外观与语言                              [已保存 ✓]      │
│   外观与语言     │  ┌────────────────────────────────────────────────────┐  │
│   新会话默认     │  │ 界面风格   [浅色][紫色][深色]                      │  │
│   功能开关       │  │ 字号       [小][标准][大]                          │  │
│ 模型与连接       │  │ 会话目录   [紧凑][详细]                            │  │
│   模型档案       │  │ 语言       [中文][English]                         │  │
│   联网搜索       │  └────────────────────────────────────────────────────┘  │
│   网络与代理     │  ※ 本区即时生效；与聊天页「界面设置」共享同一偏好        │
│ 能力与扩展       │                                                          │
│   技能           │                                                          │
│   插件           │                                                          │
│   Hooks          │                                                          │
│   MCP            │                                                          │
│ 安全与权限       │                                                          │
│   权限与规则     │                                                          │
│   扩展信任       │                                                          │
│   网页抓取       │                                                          │
│   工作区与审查   │                                                          │
│ 运行时与环境     │                                                          │
│   环境变量       │                                                          │
│   目录与路径     │                                                          │
│   上下文与性能   │                                                          │
│   数据与维护     │                                                          │
└──────────────────┴──────────────────────────────────────────────────────────┘
```

### 7.3 信息架构（5 组 / 18 分区）

| 组 | 分区 id | 中文标题 | 包含的设置项 |
|---|---|---|---|
| 常规 | `appearance` | 外观与语言 | 主题（浅/紫/深）、字号（3 档）、会话目录密度、语言（中/EN） |
| | `defaults` | 新会话默认 | 默认权限模式、默认模型档案 |
| | `features` | 功能开关 | `SECURITY_ENABLED`、`ASK_USER_ENABLED`、`HOOKS_ENABLED`、`PLUGINS_ENABLED`、`EXTENSION_REGISTRATION_APPROVAL_ENABLED`、`EGRESS_HELPER_ENABLED`、`AGENT_TEAM_ENABLED`（每项含说明、依赖关系、"立即生效 / 需重启"标记） |
| 模型与连接 | `models` | 模型档案 | 档案列表（排序、启停、编辑、删除）、新增（含高级参数）、上下文探测、模型表来源提示 |
| | `search` | 联网搜索 | `WEB_SEARCH_PROVIDER`、`TAVILY_API_KEY`、`BRAVE_API_KEY`、`SEARXNG_BASE_URL`、`JINA_API_KEY`、`WEB_SEARCH_MAX_RESULTS` |
| | `network` | 网络与代理 | `HTTPS_PROXY`/`HTTP_PROXY`、超时与重试、`WEB_DOWNLOAD_MAX_BYTES`、`OPENAI_*` 预算类 |
| 能力与扩展 | `skills` | 技能 | 技能清单 + 启停（`/api/skills`） |
| | `plugins` | 插件 | 安装/更新/删除、启停、兼容性、组件、诊断、依赖 + **插件设置表单**（现有 slot 迁移） |
| | `hooks` | Hooks | `HOOKS_PATH`、已注册 Hook 表（事件、匹配器、来源、策略/超时） |
| | `mcp` | MCP | 服务器配置（表单 + JSON 双模）、工具开关、注册状态、`MCP_SERVERS_JSON` 优先级提示 |
| 安全与权限 | `security` | 权限与规则 | 工作区范围许可、权限规则表 + 新增规则、会话规则清理 |
| | `trust` | 扩展信任 | MCP / 插件注册审批与信任状态、撤销 |
| | `webfetch` | 网页抓取 | web_fetch 预批准域名（含华为域名默认可信说明） |
| | `review` | 工作区与自动审查 | `auto_review_enabled`、`allow_external_workspace_ops` |
| 运行时与环境 | `env` | 环境变量 | 现有 7 组 + 「其他变量」全量编辑（**逐步**用策展表单接管常用键） |
| | `paths` | 目录与路径 | `WORK_DIR`（改动后提示需重启）、`SKILLS_DIR`、`PLUGINS_DIR(S)`、`HOOKS_PATH`、`LOG_DIR`、`NODE_HOME`… 带路径选择器 |
| | `runtime` | 上下文与性能 | 上下文压缩阈值、重复输出检测、日志/结果截断、并发与 CPU 压力 |
| | `maintenance` | 数据与维护 | 会话存储修复/同步（`/sessions/index/repair`、`/sessions/runtime-v2/subagent-storage/repair`）、日志目录、版本与路径信息、诊断自检 |

> 环境变量分区的"策展接管"规则：`WEB_SEARCH_*`、代理类、路径类键一旦在 `search`/`network`/`paths` 分区出现，`env` 分区对应行改为**只读 + 跳转链接**，避免同一键两个编辑面。

### 7.4 分区注册表契约

```js
// app/templates/static/settings/core.js
MyAgentSettings.registerSection({
  id: 'models',                 // 唯一 id，深链 /settings#models
  group: 'model',               // 分组 key
  order: 20,                    // 组内排序
  label: { zh: '模型档案', en: 'Model profiles' },
  icon: 'sparkles',
  keywords: ['模型', 'API', 'key', 'base url', '上下文'],   // 供全局搜索（含拼音）
  scope: 'app',                 // 'app' | 'local'（localStorage 偏好）
  saveMode: 'explicit',         // 'instant' | 'explicit' | 'readonly'
  dirty: () => bool,            // explicit 才有
  mount(el, ctx),               // ctx: { store, i18n, confirm, toast, navigate, api }
  unmount(),
  headerActions: [{ id, label, kind, run }],   // 刷新 / 热重载 / 导入导出
});
```

外壳（`settings_center.html` + `core.js`）负责：导航渲染与排序、分组折叠、搜索索引、面包屑/标题、脏值离开拦截、全局 toast / 确认弹窗、主题与语言、深链解析。分区只负责自己的表单与数据。

### 7.5 保存语义与写队列

| 类型 | 例子 | 行为 |
|---|---|---|
| `instant` | 主题、字号、会话目录、功能开关、技能/插件/MCP 工具启停 | 改动即写，成功后 toast；失败回滚 UI 并提示原因 |
| `explicit` | 模型档案表单、MCP JSON、环境变量批量、权限规则新增、插件设置表单 | 底部固定操作条「保存 / 放弃更改」，脏值高亮，离开前拦截 |
| `readonly` | 密钥现值、插件安装来源、路径解析结果、诊断信息 | 只读展示 + 复制按钮 |

统一写入管道（前端）：

```
patch(key, value) → 域内写队列（env / models / mcp / plugins 四个域互不阻塞，域内严格串行）
                  → 提交前合并最新快照（防"旧写覆盖新写"）
                  → 服务端保存 → 返回 {ok, applied, restart_required}
                  → 刷新受影响的缓存（扩展键变更需 invalidate + MCP reload）
```

服务端已有现成行为可直接复用：`POST /api/env` 在扩展相关键（`HOOKS_*`/`PLUGINS_*`/`MCP_ENABLED`/`EXTENSION_REGISTRATION_APPROVAL_ENABLED`）变更时会 `invalidate_extension_caches()` + `invalidate_skills_cache()` + `agent_mcp.force_reload()`（`webui.py:8245-8256`），`WORK_DIR` 变更会回 `restart_required`（计算在 `:8217-8219`，返回在 `:8257`）。**统一为页面顶部横幅 + 分区内状态条**。

### 7.6 来源三态、密钥、校验、危险操作

- **来源三态**：每行右侧显示 `默认 → 已覆盖`（`.env` 中存在该键即"已覆盖"，与 DSH 的"按键存在性判定"一致），悬停给出文件路径；`恢复默认` = 从 `.env` 移除该键（复用 `_apply_env_updates` 的写法，新增 `remove` 语义需在后端实现）。
- **密钥**：沿用 `_env_key_sensitive`（`webui.py:7498`）判定；输入框空值表示"不修改"，占位显示 `已配置（••••1234）/ 未配置`；保存只提交改动字段。
- **校验**：字段级（数字范围、枚举、路径存在性 `_env_key_path_kind` 已有 `file`/`directory` 判定，`webui.py:7485`）+ 保存前 JSON/依赖校验（如 `WEB_SEARCH_PROVIDER=searxng` 需要 `SEARXNG_BASE_URL`）；错误就地展示，不静默丢弃。
- **危险操作**：删除模型档案 / 清空规则 / 覆盖 MCP JSON / 卸载插件 / 撤销工作区范围许可 → 统一 confirm 组件（现有 `confirm-mask` 可复用）。

### 7.7 搜索

- 索引来源：section 的 `label` + `keywords` + 各字段标签（注册时声明），**带拼音全拼与首字母**（ZCode `pluginSearch.ts:1-35` 的做法）。
- 命中跳转：切到该 section → 滚动到字段 → 2 秒高亮。
- 搜索框只在顶部一个（不像 ZCode 分散在 5 个组件里）。

### 7.8 路由与兼容

| 路由 | 行为 |
|---|---|
| `/settings`（新） | 渲染设置中心，默认落在上次访问的 section（`sessionStorage`），无记录则 `appearance` |
| `/settings#env`、`/settings#mcp` … | 深链到指定 section；`?section=` 同样支持 |
| `/setup/env`（保留） | 渲染**同一个**设置中心，预选 `env`；保持查询参数透传（现有 `session_id`/`workspace` 参数 `settings.js:186-189`） |
| `/setup/mcp`（保留） | 预选 `mcp` |
| `/setup/extensions`（保留） | 预选 `plugins` |
| `/setup`（**不动**） | 配置向导原样保留；向导完成后跳转 `/settings#models` |

托盘与文档同步：`tray_launcher.py:894-896`、`platform_tray_macos.py:70-73`、`platform_tray_linux.py:91-92` 的「高级设置」「MCP 配置」两项合并为一个「设置中心」（旧项可保留但指向深链）。

### 7.9 i18n 与主题

- 语言：沿用共享键 `myagent-language` 与 `app/templates/static/setup_i18n.js` 的机制，设置中心新增命名空间键（`settings.*`），中/EN 全覆盖。
- 主题：读取同一 `myagent-theme` 键，并**修正 purple**：`light | purple | dark` 三态映射（现有 setup 页只判 dark）。要求设置中心与聊天页切换后互不"看起来不一致"。

### 7.10 与配置向导、聊天页、托盘的边界

- **配置向导（`/setup`）不改**：不改 `first_time_config.html`，不改 `_is_configured()` 门槛逻辑（`webui.py:7187-7223`）。设置中心在"尚未配置模型"时依然可打开，但模型分区会给出"去配置向导"的引导链接。
- **聊天页弹窗降级为"快捷设置"**：保留字号/主题/会话目录的快速切换 + 「打开设置中心」按钮（替代现在的「高级设置」按钮）；插件设置分区**迁移**到设置中心，弹窗不再重复渲染。
- **不引入构建依赖**：设置中心仍是无构建静态页（见 §8 D1/D4）。

---

## 8. 关键决策与备选方案

| 编号 | 决策 | 推荐 | 备选与代价 |
|---|---|---|---|
| D1 | 设置中心宿主形态 | **独立静态页 `/settings`**（同 setup 页体系，无构建，`.env`/MCP/插件表格等重内容零迁移成本） | 备选：并入 Vite 聊天 SPA 做全屏覆盖层（学 ZCode）——共享样式更好，但要移植 145KB 模板、需要 `npm run build`、`scripts/check_frontend_dist_sync.py` 与 8 个契约测试同步，风险与工期显著上升 |
| D2 | 旧路由 | **保留**，渲染同一页面并预选 section | 备选：302 重定向——会打断托盘/收藏链接与 `test_platform_lifecycle.py:137` 的路径断言 |
| D3 | 插件设置（slot）是否迁入 | **迁入**，与内置分区同一渲染器（`plugin-ui-slots.js` 的 `renderPluginSettingsSections` 改为向 registry 注册 section） | 备选：留在聊天弹窗——继续"插件设置与插件管理两处"的割裂 |
| D4 | 是否引入前端框架/构建 | **不引入**，vanilla + 分文件（`static/settings/*.js`） | 备选：上 React——与"改一个模板即时生效"的现有开发体验冲突 |
| D5 | 环境变量与策展表单的关系 | 策展键**只读化**在 env 分区，编辑面唯一 | 备选：两处都可编辑——立即复现 ZCode/DSH 的双入口问题 |

---

## 9. 分阶段实施计划

### Phase 0：外壳与契约（可独立验收）

- 新增 `/settings` 路由与 `settings_center.html` 外壳、`core.js` 注册表、导航/搜索/确认/toast/深链。
- 先迁两个"零后端改动"的分区：**外观与语言**（localStorage）、**功能开关**（复用 `/api/env`、`/api/features/ask-user`）。
- 旧路由渲染同一页面并预选 section（内容暂仍指向老实现，保证不断链）。
- **验收**：`/settings` 可用、语言与主题与聊天页一致（含 purple）、`ASK_USER_ENABLED` 有了开关 UI、旧路由与托盘行为不变。

### Phase 1：核心迁移（一次性消除三处重复）

- 迁移 `models` / `env` / `search` / `network` / `paths` / `runtime`（来自 advance_config）、`mcp`（advance_config + mcp_config 合并）、`plugins` / `hooks`（advance_config + extensions_config 合并）、`security` / `trust` / `webfetch` / `review`（advance_config 的"安全与权限"页签）。
- 引入四域写队列与脏值拦截；统一保存条与状态提示；密钥只写。
- 托盘两个菜单项收敛；文档（`docs/hooks_plugins.md:29` 等）更新为"设置中心 → …"。
- **验收**：`/setup/env`、`/setup/mcp`、`/setup/extensions` 全部渲染设置中心且落到正确分区；原功能无回退；契约测试同步。

### Phase 2：体验补齐

- 全局搜索（含拼音）+ 结果高亮；来源三态 + 一键恢复默认；分区内头部动作（刷新 / 热重载 / 导入导出）；空态与错误态统一；i18n 全覆盖。

### Phase 3：可选增强

- 数据与维护分区（会话修复/日志/诊断自检）、设置导入导出（脱敏）、远程客户端只读模式（对齐 DSH 的 memory 降级思路）、`Ctrl/Cmd+,` 快捷键入口。

---

## 10. 文件级改造清单（预计）

| 文件 | 动作 |
|---|---|
| `app/webui.py` | 新增 `/settings` 路由；`/setup/env`、`/setup/mcp`、`/setup/extensions` 改为渲染设置中心并传 `initial_section`；**新增单键删除/恢复默认的 env 写语义**（服务端支持） |
| `app/templates/settings_center.html`（新） | 设置中心外壳（导航 + 内容 + 顶部工具条 + 确认/toast） |
| `app/templates/static/settings/core.js`（新） | 注册表、导航渲染、搜索、深链、写队列、i18n/主题、confirm/toast |
| `app/templates/static/settings/section-*.js`（新，约 14–18 个，对应 §7.3 的 18 个分区） | 各分区实现（环境变量、模型、MCP、插件、Hooks、技能、安全…） |
| `app/templates/static/setup_i18n.js` | 扩充 `settings.*` 文案（中/EN） |
| `app/templates/advance_config.html` | 逐步退役；保留为兼容壳（或下线，由 `/setup/env` 直接返回新页） |
| `app/templates/mcp_config.html`、`extensions_config.html` | 同上（内容并入设置中心后退役） |
| `frontend/src/app/modules/settings.js` | 弹窗改为"快捷设置"，「高级设置」→「打开设置中心」深链 |
| `frontend/src/app/plugin-ui-slots.js` | `settings.section` 贡献改为注册到设置中心（`renderPluginSettingsSections` 迁出弹窗） |
| `frontend/src/shell-body.html` | 删除 `#plugin-settings-sections` 容器（迁移后） |
| `app/tray_launcher.py`、`app/platform_tray_macos.py`、`app/platform_tray_linux.py` | 菜单项收敛为「设置中心」（Windows 枚举与文案同步） |
| `docs/hooks_plugins.md` 等 | 入口描述更新 |

---

## 11. 测试与回归矩阵

| 类别 | 现有测试（须同步更新） | 新增测试建议 |
|---|---|---|
| 模板契约 | `tests/test_enablement_ui_contract.py:9/84`、`tests/test_feature_flags.py:152`、`tests/test_model_profiles.py:860/897`、`tests/test_llm_transport.py:930`、`tests/test_agent_extensions_integration.py:151/155/166`、`tests/test_plugin_installer.py:222` | 改为对**注册表/分区模块**断言（如"存在 `id='models'` 的 section 且含 `data-toggle-profile-id`"），降低文本耦合 |
| 路由 | `tests/test_platform_lifecycle.py:135-137`（`/setup/env` 打开行为）、`tests/test_human_interaction.py:670`（`/api/features/ask-user` 存在） | 新增 `/settings` 与三个旧路由均返回 200 且含 `initial_section` |
| 功能开关 | `tests/test_feature_flags.py`（ASK_USER / SECURITY 注入） | 新增"设置中心功能开关 → `/api/env` 写 → 立即生效"链路测试 |
| 主题/语言 | 无 | 新增：i18n 键齐备性（中/EN 成对）、主题三态在设置中心与聊天页一致（purple 不再是 light） |
| 写入语义 | 无 | 新增：env 单键删除（恢复默认）、并发保存串行（同域两支写不互相覆盖）、`restart_required` 横幅显示 |

---

## 12. 风险与不做清单

**风险**
1. 模板契约测试面大（8 个测试文件直接读模板）——Phase 1 必须与测试同步改，否则 CI 全红。
2. `advance_config.html` 的模型表单逻辑量大（含探测、排序、模态），迁移时易丢细节 → 建议**先整体搬移再拆分**，不要重写。
3. 环境变量"整文件读-合并-写"（`webui.py:8189+`）在并发保存下会互相覆盖 → 必须上写队列或服务端加版本号。
4. 主题/字号在聊天页与设置中心双写同一 localStorage 键：需监听 `storage` 事件或统一由一处写入，反之会出现"切完没生效"。

**不做**
1. 不改 `/setup` 配置向导与其门槛逻辑。
2. 不改权限模型、审批链路与安全策略语义（只做 UI 归集）。
3. 不引入前端框架与构建步骤。
4. 不删除 `/setup/env`、`/setup/mcp`、`/setup/extensions` 路由（只换实现）。
5. 不做"设置云同步"（ZCode 的 settings-sync 只做跨 Agent 导入，DSH 无导入导出；本方案把导入导出放到 Phase 3 可选）。

---

## 13. 首个开发切片（建议立即开工）

1. `app/webui.py`：新增 `/settings` 路由 + 三个旧路由改为 `initial_section` 渲染。
2. `app/templates/settings_center.html` + `static/settings/core.js`：外壳、注册表、左栏导航、搜索框（先空实现）、深链、主题/语言。
3. `section-appearance.js`（外观与语言，localStorage，即时生效）+ `section-features.js`（功能开关，`/api/env` + `/api/features/ask-user`）。
4. `frontend/src/app/modules/settings.js`：「高级设置」按钮改为打开 `/settings#features`（或 `/settings`），保留原有深链参数。
5. 更新 `tests/test_platform_lifecycle.py` 邻近的路径断言，新增"`/settings` 200 + 含 appearance/features 两个导航项"的契约测试。

验收口径：打开 `/settings` 能改主题/字号/语言/Ask User 开关，行为与聊天页一致；`/setup/env` 仍能打开且落到"环境变量"分区；配置向导与托盘行为无变化。

---

## 14. 数据来源

- ZCode：`packages/ui/src/SettingsPage.tsx`、`settings/*`（`settingsPageConfig.ts`、`SettingsPageParts.tsx`、`SettingsHeaderBreadcrumb.tsx`、`SettingsScopeBadge.tsx`、`PluginScopeMenu.tsx`、`pluginSearch.ts`、`shortcuts/*`）、`lib/settingsNavigation.ts`、`store/tabStore.ts`、`hooks/useSettingService.ts`、`packages/services/src/setting/*`、`packages/services/src/settings-sync/*`、`packages/shared/src/{protocol,settings-errors,shortcutCommands}.ts`。
- DSH：`packages/client/ui-settings*/`（含各自 `README.zh.md`）、`packages/client/ui-plugin-manager/src/client/slot-contract.ts`、`packages/settings/settings/src/{types.ts,index.ts}`、`packages/boot/{app-boot,config-editor}`、`packages/util/home-paths`、`packages/client/AGENTS.md:130-141`、`docs/subsystems/settings.zh.md`。

---

## 15. 实现记录（v1 · 已落地）

> 第 7 章的 18 分区 IA 已被 **9 分区版**取代（与用户确认的原型一致）：
> `常规 / 模型 / 技能 / 插件 / Hooks / MCP / 安全与权限 / 环境变量 / 目录与路径`。
> 下文是 v1 实际落地的文件与行为，作为后续迭代的基线。

### 15.1 新增与改动

| 文件 | 作用 |
| --- | --- |
| `app/templates/settings_center.html` | 单页外壳：左栏 188px 导航 + 右栏内容 + 底部保存条 + 确认框/表单弹窗（无构建，占位符由后端注入） |
| `app/templates/static/settings/settings.css` | DSH/ZCode 对齐的样式与三主题 token（`--st-*`），字号跟随 `myagent-font-level` |
| `app/templates/static/settings/core.js` | 注册表、导航、深链、i18n（中/EN）、主题/字号、`api()` 封装、组件（card/row/lrow/seg/sw/btn/chip/input/note/adv/search）、toast、确认框、表单弹窗、脏值保存条 |
| `app/templates/static/settings/sections_basic.js` | 常规（外观/语言/新会话默认）、模型（列表/启停/删除/新增与编辑弹窗/从接口获取）、技能（列表/启停/搜索/添加技能弹窗） |
| `app/templates/static/settings/sections_ext.js` | 插件（安装/启停/移除/设置表单/热重载）、Hooks（总开关/配置路径/列表/热重载）、MCP（服务器与工具开关/注册/添加服务器/JSON 高级编辑） |
| `app/templates/static/settings/sections_ops.js` | 安全与权限（模式/规则/其它安全项/网页抓取白名单/扩展信任）、环境变量（分组 + 恢复默认 + 保存条）、目录与路径（路径选择器 + 保存条） |
| `app/webui.py` | `/settings` 路由；`/setup/env`、`/setup/mcp`、`/setup/extensions` 改为同页预选分区；`/static/settings/{asset}` 白名单静态资源；`POST /api/env` 新增 `remove: []`；新增 `POST /api/skills/create`、`POST /api/skills/install`（dir/zip/git）；`_config_check` 白名单放开 `/settings` 与设置页所需 API |
| `tests/test_settings_center.py` | 新增 8 个契约测试（路由预选、静态资源白名单、env 删键、技能新建/安装、9 分区注册） |

### 15.2 与原型一致的交互口径

- 9 分区、单页、`#section` 深链；旧路由落到对应分区（`/setup/env → #env`、`/setup/mcp → #mcp`、`/setup/extensions → #plugins`）。
- 保存语义：只有「环境变量」「目录与路径」是显式保存（底部常驻保存条，脏值提示优先）；其余分区即时生效。
- 危险操作（删除模型 / 移除插件 / 清空会话规则）先弹确认；密钥字段只写不回显。
- 图标来源：常规 / 模型 / 技能 / Hooks / 环境变量 / 目录与路径 取自 DSH `ui-primitives/src/icons/index.tsx`（16px 网格、1.3px 描边：Settings / Data / Skill / Link / Code / FolderOpen）；**插件（插头）、安全（盾牌 + 对勾）、MCP（双条服务器）沿用 v0.3 原型的手绘图标**（24px 网格、1.6px 描边），渲染器按图标自带的 `viewBox/stroke-width` 出图。

### 15.3 未做（明确留到后续）

- 本页仍是独立静态页，**未**并入 Vite SPA；插件 `settings.section` 槽位尚未迁移到本页（聊天页插件设置入口保持原样）。
- `frontend/src/app/modules/settings.js` 的齿轮弹窗、托盘菜单路径未改（都还能用）。
- 权限模式切换依赖真实 `session_id`，从托盘直接打开 `/settings` 时该行只读。
- 分组搜索、拼音匹配、来源三态徽标（default/user/workspace）未做。

> 说明：15.3 的前两条已在 15.4 落地，保留原文以记录当时的范围。

### 15.4 入口收敛（第二轮）

**左上角齿轮 → 应用内浮层打开设置中心**，旧的「界面设置」弹窗整体移除：

| 项 | 变更 |
| --- | --- |
| 齿轮入口 | `#sidebar-settings-btn` → `openSettingsCenter()`，用 `<iframe id="settings-center-frame">` 载入 `/settings?embedded=1&session_id=…&workspace=…`；聊天页状态（含流式输出）不中断 |
| 关闭方式 | 浮层内「返回聊天」（`postMessage('myagent:settings-close')`）、ESC、点遮罩；关闭后回到 `about:blank` 并重放一次主题/字号偏好 |
| 删除的旧 UI | `#settings-modal-root` 整块（字体大小 / 界面风格 / 会话目录 / 环境与 API 的「高级设置」按钮 / 插件设置槽）+ `frontend/src/app/modules/settings.js` 中的弹窗开关与同步逻辑 |
| 「额外标签页」 | 原「高级设置」会 `window.open('/setup/env','myagent-env')` 开一个新标签页，已随弹窗移除；托盘菜单改指 `/settings` 与 `/settings#mcp`（Win/Linux/macOS 三处） |
| 保留的公共逻辑 | `applyUiTheme` / `applyFontLevel` / `applySessionListMode` / `restoreUiPreferences` 仍在 `settings.js`，聊天页继续即时生效 |
| 插件设置槽位 | `#plugin-settings-sections` 宿主移除；设置中心「插件」分区新增「插件自带设置」卡片，按 `/api/extensions` 的 `ui_contributions`（`slot=settings.section`）列出条目与插件页链接 |
| 内嵌适配 | 设置中心自查 `window.self !== window.top`（不依赖后端重启）进入内嵌模式：背景透明，遮罩由宿主浮层提供；ESC / 点空白同关浮层 |
| 兼容兜底 | 首次点齿轮会先探活 `/settings`（该服务不支持 HEAD，405 也算存在）；探活失败提示「重启 Agent 后可用」而不是弹空白浮层 |
| 构建 | `frontend/` 两处 shell（`index.html` 与 `src/shell-body.html`）同步替换；`npm run build` → `app/templates/dist/` 已同步（`npm run verify:dist` 通过） |

新增/改写的契约测试：

- `tests/test_settings_modal_sections.py`：新增 `test_gear_entry_opens_the_settings_center_overlay`（弹窗标记消失、浮层存在、`settings.js` 只走 `/settings`、不再引用 `/setup/env`）与 `test_settings_center_page_closes_itself_when_embedded`。
- `tests/test_frontend_theme_variants.py`：三档主题断言从聊天页弹窗改为设置中心资产（`sections_basic.js` 的 light/dark/purple + `settings.css` 的 `:root.theme-dark/.theme-purple`）。
- `tests/test_plugin_ui_frontend.py`：`#plugin-settings-sections` 宿主断言改为「宿主已移除 + 由设置中心 `ui_contributions` 承载」。

旧模板退役完成：`app/templates/{advance_config,mcp_config,extensions_config}.html` 均已删除；`app/webui.py` 的旧加载函数（`_load_mcp_config_html`、`_load_extensions_config_html`）一并移除。三个旧路由（`/setup/env`、`/setup/mcp`、`/setup/extensions`）保留——只「深链到设置中心对应分区」。插件生命周期契约测试改为直接断言设置中心插件分区（`app/templates/static/settings/sections_ext.js`）与后端路由。

### 15.5 浮层「背景是假的」两处修复（第三轮）

用户反馈「浮窗像个假的，背景不会实时变化」。查下来是两个独立缺陷叠加：

**① 偏好只回推了一半（背景不变）**

| 环节 | 原状 | 现状 |
| --- | --- | --- |
| 设置中心 → 宿主 | `core.js` 里 `notifyHostPrefs()` 定义了却**从没被调用**（常规分区改主题/字号/会话列表/语言只写自己的 localStorage） | 新增 `MyAgentSettings.setPref(name, value)`：写共用偏好键 + 立即回推；常规分区的 theme/font/list/lang 全部改走它 |
| 宿主监听 | `settings.js` 只认 `myagent:settings-close`，`myagent:settings-prefs` 被丢弃，主题要等**关闭浮层**才由 `restoreUiPreferences()` 补上 | 新增 `applyHostPrefs(prefs)`：收到消息立即 `restoreUiPreferences()` + 切语言；另加 `storage` 事件兜底（别的窗口/标签页改了同一批键也跟随） |
| 语言 | 只重载设置中心自己那一帧 | 先 `setPref('lang', …)` 把消息发出去，再延时 50ms 重载本页刷新文案 |

**② 深色/紫色主题下 iframe 画布不透明（背景被整块盖住）**

父页面 `:root.theme-purple { color-scheme: dark }` 会被 `<iframe>` 元素继承，Chromium 随即给 iframe 文档画一层**不透明的底**（实测深色主题下屏幕两侧取到纯白 `#FFFFFF`，聊天页完全不可见）；浅色主题恰好是白底，肉眼看不出来，所以只有主题一深就"露馅"。
修复：`.settings-center-frame { color-scheme: normal; }`（`frontend/src/styles/app.css`）。修完三个主题下取到的两侧像素分别变成 `(187,188,189)`(浅) / `(20,20,22)`(深) / `(17,17,27)`(紫)——都是"聊天页 + 遮罩"的真实合成值。

**验证方式**：Playwright 打开浮层 → 在浮层里点「紫色/深色/更大字号/紧凑列表/English」→ 不关浮层直接读宿主 `<html>`（`theme-purple` / `data-font-level=2` / `data-session-list-mode=compact` / `lang=en` 全部当场变化）；再对截图两侧条带取像素，确认背景确实随主题变深变浅。
新增契约测试：`tests/test_settings_modal_sections.py::test_settings_center_pushes_prefs_to_host_in_realtime` 与 `::test_overlay_iframe_keeps_a_transparent_canvas`（共 6 例，防回归）。

证据截图：`workspace/设置中心原型/shot-live-before-fix.png`（修前：浮层已是深色、背景还是浅色）、`ab-light.png` / `ab-purple.png`（修后：同一处浮层、背景实时跟着变）。

本轮改动文件：`app/templates/static/settings/{core.js,sections_basic.js}`、`frontend/src/app/modules/settings.js`、`frontend/src/styles/app.css`、`tests/test_settings_modal_sections.py`（源码依据：`app/webui.py` 路由与分组表 `7249-7374`、env 读写 `8093-8257`、plugins/mcp/extensions `7615-8092`；`frontend/src/app/modules/{model-profiles.js,permissions.js,skill-picker.js}`；`app/templates/static/*.js`；`tests/*`）。

### 15.6 功能验证（第四轮）

「9 个分区里有很多功能需要验证」→ 做了一轮**对照真服务**的验证，详见 [`settings_center_verification.md`](./settings_center_verification.md)：

- **渲染层**：9 个页签依次打开，卡片/行/开关/按钮均渲染，**0 条 console 错误、0 个 ≥400 的 `/api/*` 响应**（截图 `workspace/设置中心验证/tab-*.png`）。
- **接口层**：36 项检查全绿——端点、状态码、前端渲染取用的字段名，以及 5 类**可还原写入回环**（模型档案开关、技能开关、MCP 工具开关、安全规则增删、env 同值保存），每步后比对 4 个配置文件哈希。
- **修掉一个真问题**：`环境变量`/`目录与路径` 的「保存」原本一次提交整屏控件，后端对空串的语义是写成 `KEY=`，于是**什么都没改点一次保存也会往 `.env` 写空键**（连默认注入的 `SECURITY_ENABLED=1` 一起）。现改为**只提交改动**，清空 = `remove`（与「恢复默认」同语义），密钥仍是留空即不改；补 2 个契约测试。
- **UI 层**（Playwright + 系统 Edge，17 项全绿）：真鼠标拖拽排序、↑↓ 键换位、模型编辑弹窗预填、删除确认框、技能添加弹窗三分段、插件/Hooks 热重载、MCP 与安全表单校验、搜索过滤、路径选择器、齿轮浮层。

### 15.7 两处能力回退修复（第五轮）

用户反馈「模型的顺序现在没法拖拽调整了」。核对下来是**平移旧页面时丢的能力**，一并修掉：

| 问题 | 根因 | 修法 |
| --- | --- | --- |
| 模型列表不能拖拽排序 | 旧 `advance_config.html` 有完整 drag-drop（手柄 + `animateProfileRowShift` + `POST /api/model_profiles/reorder`），设置中心只搬了列表没搬交互 | `sections_basic.js` 补 `wireProfileReorder()`：手柄拖拽、`dragover` 实时让位 + 位移动画、拖出列表=取消并恢复原序、`drop` 后提交 `ordered_ids`；键盘聚焦手柄按 ↑/↓ 同样换位；`settings.css` 加手柄与拖拽态样式 |
| 技能 / 环境变量的搜索框「敲字就清空」 | `core.js` 的 `showSection()` 无条件 `state.search = ''`，而这两个分区的 `onSearch()` 正是 `reload()`（同分区重绘）→ 输入被自己清掉、列表不筛选 | 只有真正换分区才清搜索词：`if (previousSection !== id) state.search = '';` |

实测证据：`workspace/设置中心验证/verify_settings_ui.py`（A1–A6 模型排序、B1–B11 交互，17/17 通过）与 `ui-models-drag.png`、`ui-dialog-*.png`；接口层证据 `verify_model_reorder.py`。新增 2 条契约测试（`test_models_section_wires_drag_and_keyboard_reordering`、`test_section_search_survives_same_section_reload`），防止再次被搬丢。

### 15.8 字号改成 DSH 式可输入步进器（第六轮）

用户要求「字号学习 dsh 做成可输入字号大小的」。DSH 的做法是 `ui-theme` 的 **FontSizeRow**：
「通用」分区里一颗药丸式步进器（数值居中、悬停显出贴在右侧的上下箭头列），后面跟 `px` 单位，
取值是**整数 12–17 px**、默认 14，落到正文轴 `--dsh-content-font-size`（`packages/client/ui-theme/src/{theme-settings.ts,client/FontSizeRow.tsx}`）。

| 项 | SugarAgent 落地 |
| --- | --- |
| 控件 | 同样式药丸：药丸内是**可直接输入的数值**（DSH 那里只读、只能点箭头），右侧悬浮上下箭头（悬停/聚焦显出），尾巴 `px`；行下加一句「12–20 px，可直接输入数字，或点右侧箭头逐级调」 |
| 范围 | 12–20 px、整数、默认 16（DSH 是 12–17/默认 14；SugarAgent 原来的「标准」= 16px，保持观感不动，上限放宽到 20） |
| 存储 | 新增 `myagent-font-size-px`；旧的 `myagent-font-level`（0/1/2 = 14/16/17）仍然同步维护，老读者不受影响；缺 px 键时按档位回落 |
| 应用 | 聊天页 `applyFontSize(px)` 设 root 字号 + `data-font-size`（保留 `data-font-level`），`restoreUiPreferences()` 以 px 为准；设置中心把 `--st-fs*` 按「px − 2」为基准等比换算 |
| 实时 | 走 §15.5 的偏好回推：输入/点箭头立刻写 localStorage 并 postMessage，浮层背后聊天页当帧跟变 |

实测（`verify_font_size_ui.py`，8/8 通过）：输入 18 → 设置中心 `data-font-size=18`、localStorage `18`、**聊天页 root 18px**；箭头 ±1 生效；99→20、3→12 且到界箭头禁用；清空再离焦退回上一个有效值；跑完还原 16px。
新增契约测试 `test_font_size_is_a_dsh_style_stepper_with_px_preference`（同时钉住「不许退回小/标准/大三档」）。原型 v0.3 同步改成同款控件（README 与截图 `proto-font-stepper.png`）。

### 15.9 技能说明改走悬停浮框（第七轮）

用户要求「已安装的技能不用把 description 里的内容都写出来，description 用 hover 时的浮框就好了」。

- 新增通用浮框组件（`core.js`）：`W.tip(label, text)` 把详情挂到 `data-tip` 上，配套一个单例气泡
  `.st-tip` —— 悬停或键盘聚焦时显示，移开/失焦/滚动/换分区即收；定位跟随目标，超出视口自动翻到上方，
  反色底（浅色主题深气泡、深色主题浅气泡），最高 `52vh` 防超长说明铺满屏。
- 技能行改为 `W.tip(技能名, description)` + 空副标题：**列表不再铺说明**，行内只留名字、启用状态与开关；
  搜索仍按 name + description 过滤（说明没丢）。卡片提示补「悬停技能名看说明」。
- 实测（`verify_settings_ui.py` 的 B12）：agent-browser 的 925 字说明只在浮框里出现、行内不出现、移开即隐藏。
- 原型 v0.3 同步（`.tip` 同款实现 + 技能页改法），冒烟脚本 `_smoke_prototype_skill_tip.py` 通过。
- 契约测试 `test_skill_description_lives_in_a_hover_tip_only`。

> 同类候选（本次未动，等用户点头）：MCP 工具列表、插件列表的说明也还是行内铺开，同样可以走浮框。

### 15.10 MCP 工具 / 插件说明一并走浮框（第八轮）

用户答复「都改了」——把剩下两处也平移到同一套浮框：

| 位置 | 改法 |
| --- | --- |
| MCP 工具行（27 条） | 主标签 `function_name`（等宽字体）挂浮框＝完整 description，**副标题留空**；行内只剩名字 + 开关，长度从"每条 3–5 行"压回一行 |
| 插件行（6 个） | 名字（含版本）挂浮框＝description，副标题只留组件汇总（`skill×1 · hook×2`）或命名空间 |
| 插件自带设置（`ui_contributions`） | 标题挂浮框＝description，副标题只留 `plugin_id` |

统一小工具 `tipIf(label, text, cls)`：有说明才包成浮框目标，没说明就原样输出（不留空泡）。
两处卡片提示同步改成「悬停工具名看说明 / 悬停插件名看简介」。

实测（`verify_settings_ui.py` B12–B14，20 项全绿）：技能 925 字、MCP 453 字、插件 64 字说明均只在浮框出现、行内不含、移开即隐藏；浮框目标数分别为 27（MCP 工具）与 6（插件）。
原型 v0.3 的 MCP / 插件页同步（并补了一小段 MCP 工具行示例），冒烟 `_smoke_prototype_skill_tip.py` 3/3 通过。契约测试 `test_mcp_tools_and_plugins_keep_descriptions_in_hover_tips`。
