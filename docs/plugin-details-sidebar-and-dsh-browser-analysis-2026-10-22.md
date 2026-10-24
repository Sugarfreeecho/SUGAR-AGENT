# 插件独立页面迁入右侧详情栏与 DSH 浏览器实现分析

日期：2026-10-22。本文是源码分析与实施建议，文中的新增 API 和 manifest 字段尚未实现。

分析基线：SugarAgent 当前工作树（HEAD `43cdeaf`）；本地 DSH 工作树 `D:\AI\AI Agent\OpenAgent\Deepseek Harness\deepseek-harness`（HEAD `477b4f4205`）。已有工作树改动纳入阅读，本文不改动业务代码。

## 1. 结论

1. **DSH 有完整的右侧浏览器标签页**，插件名为 `ui-sidebar-browser`。Web 载体是 iframe；Desktop 载体是 Electron `<webview>`。两端共用导航控制器和右栏类型注册机制。
2. **SugarAgent 可以复用现有 Dock 完成插件页面迁入，但现有扩展链路没有接通。** `MyAgentDock.registerTabType()` 和注册表中的 `bodyFor()` 已存在，右栏正文却硬编码四种内置页面，未调用注册表的正文渲染器。只改入口链接不足以开放插件接口。
3. **插件页面与通用浏览器应使用两种内容类型，共用右栏外壳。** 插件页面需要访问应用自身 `/plugins/{id}` 和 API；DSH 通用浏览器明确禁止应用自身地址，不能直接承载这种插件页面。
4. 先实现右栏插件扩展点并迁移现有独立页面；再按需要接入 DSH 式浏览器。插件迁移本身不依赖新增浏览器内核，也不需要新增 TCP 监听端口。

## 2. SugarAgent 当前页面与打开链路

### 2.1 当前具有 Web 入口的插件

按当前磁盘上的 manifest 盘点，不代表这些插件运行时全部启用：

| 插件 | 当前入口 | 迁移建议 |
|---|---|---|
| `agent-goal` | `ui.navigation`、独立 Web 页 | 右栏 Goal 页，接收绑定的会话 ID |
| `agent-team` | `ui.navigation`、独立 Web 页 | 右栏 Team 页，接收绑定的会话 ID |
| `game-arena` | `ui.navigation`、独立 Web 页 | 右栏棋局页，棋盘按面板宽度适配，可用现有全屏 |
| `sugar-bili-scroll` | `ui.navigation`、独立 Web 页 | 右栏 B 站插件页；日报、二维码、设置仍由插件提供 |
| `thread-monitor` | `ui.navigation`、独立 Web 页 | 右栏线程监控页，数据属于应用，隐藏时暂停采样轮询 |
| `chatgpt-subscription` | `settings.section`，`embedded: true` | 保留设置页内账号配置；统一处理从其他位置打开其完整页面的请求 |

`session-todo`、`change-review`、`execution-tools`、`voice-input` 目前声明的是 Web 资源目录，没有 `web.entry`，不能仅凭拥有 Web 资源就当成独立页面迁移。`session.panel` 是现有会话卡片扩展点，也不能与完整页面混为一类。

### 2.2 需要统一的打开入口

| 位置 | 源码依据 | 当前行为 |
|---|---|---|
| 聊天区插件选择器 | `frontend/src/app/modules/skill-picker.js:332,394,582` | 检查插件页面声明，输出 `_blank` 链接；点击仅阻止冒泡 |
| 设置中心插件列表 | `app/templates/static/settings/sections_ext.js:76` | 导航贡献、页面型设置贡献显示 `_blank` 打开链接 |
| 设置中心独立插件分区 | `app/templates/static/settings/plugin_sections.js:111` | `embedded: true` 用设置内 iframe，其余页面型入口开新页 |
| 旧设置渲染器 | `frontend/src/app/plugin-ui-slots.js:414` | 页面型贡献输出 `_blank` 链接 |
| 输入框插件动作 | `frontend/src/app/plugin-ui-slots.js:659` | 页面动作调用 `globalThis.open()` |
| Electron 新窗口处理 | `packaging/electron/main.js:574` | 应用地址前缀匹配时允许原生新窗口；其他地址交系统浏览器 |

因此目前桌面端插件页面也可能开成独立 Electron 窗口。统一改造需要覆盖上述实际调用方，单独修改 `normalizePluginNavigationContributions()` 不会覆盖所有入口。

插件页面地址由 `app/plugins/ui.py:252` 生成，导航贡献固定为 `/plugins/{plugin_id}`。页面路由 `app/webui.py:10282` 返回 HTML，并设置 `frame-ancestors 'self'`，已经允许同源右栏 iframe 嵌入；现有插件 HTTP 和静态资源网关可以继续使用。

### 2.3 右栏目前的三个缺口

**注册与正文渲染脱节。** `right-column.js:1942` 公开注册接口，`tab-registry.js:163` 提供 `bodyFor(kind)`，但 `right-column.js:781` 仅分支渲染 `guide/files/document/changes`，其他类型显示兜底文本。开始页 `right-column.js:843` 也只生成文件和改动入口，没有从注册表读取插件入口。

**缓存 DOM 对象不等于页面保活。** `dock-surface.js:302` 切换正文时执行 `replaceChildren(bodyEl)`，旧正文离开文档；布局树重建和浮动切换也可能移除正文。iframe/webview 的浏览上下文不能依赖这种缓存方式维持。需要明确的 `keepMounted` 机制：访问过的页面保留连接，隐藏时控制可见性和焦点，真正关闭时销毁。分栏、切会话、浮动等路径也必须遵守同一规则。

**销毁规则只服务现有内置页面。** `right-column.js:1909` 只清理其已知的事件监听和请求取消器。开放插件正文后，需要统一的关闭、注销、禁用、页面崩溃与异步挂载取消回收机制。特别是当前 `renderFloatsRemovedTabs()` 使用当前布局判断标签是否移除，不能直接拿来管理跨会话保活页面，否则切会话会被当成关闭。

## 3. DSH 的浏览器具体如何实现

### 3.1 注册、打开和 UI

核心包是 `packages/client/ui-sidebar-browser/`。在 `packages/bundle/web-app/cordis.patch.yml:272` 中，浏览器条目只有 Desktop profile 默认启用；Web 可以显式启用。

插件通过 `ctx.sidebarRightTabs.register()` 注册 `kind: 'browser'`，再向 `sidebar.right.pane.tab` 注册正文，向 `sidebar.right.pane.tab.title` 注册标题。Browser 定义允许多个页面，并贡献开始页入口。

打开 API 为：

```ts
ctx.sidebarRight.openTab('browser', { params: { url } })
```

聊天链接在“应用内侧边栏”偏好生效且 Browser 类型可用时调用同一 API（`packages/client/ui-chat/src/client/apply.ts:228`）。工具栏提供地址、后退、前进、刷新和系统浏览器打开；Browser 自己拥有新建标签快捷键。

### 3.2 共用控制器，两种页面载体

```text
开始页 / 聊天链接 / 插件调用
             ↓
sidebarRight.openTab('browser', { params: { url } })
             ↓
BrowserController：地址校验、打开/恢复、生命周期
             ↓
BrowserPage = BrowserFrame（导航状态）+ BrowserPresentation（DOM）
             ├─ Web：IframeImpl + IframePresentation
             └─ Desktop：ElectronWebViewImpl + ElectronWebviewPresentation
```

`src/client/index.ts:77` 检查 `dshDesktop.protocolVersion` 和浏览器桥接能力，选择载体。`BrowserBody.tsx` 只消费统一状态和操作，不自己区分平台。

### 3.3 Web：iframe 与受控地址历史

`src/client/view/IframePresentation.ts` 创建 iframe，设置 `referrerPolicy='no-referrer'`，默认 sandbox 包含 scripts、forms、same-origin 和 popup 相关许可。

iframe 无法读取跨域页面的真实 URL 和导航栈。DSH 因此只维护应用已知的导航历史；检测到受控加载之外的后续 load 时，进入地址 `unknown` 状态，限制后退、前进和外部打开，刷新回到最后已知地址。页面的 History API 和 fragment 变化仍可能不可见。

这条路线仍受站点 `X-Frame-Options`、CSP、混合内容等限制；失败也不一定触发可判断的 error 事件。DSH 提供系统浏览器打开作为出口，未通过代理删除站点的防嵌入响应头。它还提供临时关闭 sandbox 的选项，但这不会消除上述浏览器限制。

### 3.4 Desktop：webview、主进程租约和独立分区

1. 只有主应用窗口启用 `webviewTag`（`apps/desktop/src/main.ts:231`）。
2. preload 暴露窄接口 `acquire(workspace)`、`release(lease)`、`onOpenRequested(lease, listener)`，不把 Electron 或通用 IPC 对象交给网页。
3. 主进程 `DesktopBrowserGuests.acquire()` 为工作区分配进程内存储分区，并签发一次挂载租约。
4. 前端创建 `<webview partition="…" src="about:blank#租约">`。`will-attach-webview` 校验所属窗口、租约和分区；通过后强制关闭 Node、开启 context isolation、sandbox 和 web security，并移除 guest preload 等非批准配置。
5. `ElectronWebViewImpl` 监听真实导航、页内导航、标题、加载和进程事件，从 Chromium 获取真实 URL、标题和前进后退能力。
6. 原生 popup 被拒绝；合规 HTTP(S) 新开页请求通知所属右栏，创建 Browser 标签。权限申请和下载也由主进程限制。
7. 同一规范化工作区共享进程内 Cookie/storage；未解析到工作区的 Session 单独隔离。存储不跨应用重启保留。

Desktop Browser 注册 `keepMounted`，使标签切换、会话切换、收起和浮动时保留页面 DOM。它保存标题与 URL 检查点，重启后需要用户点击恢复或刷新；不宣称恢复页面内存、表单或完整 Chromium 历史。

### 3.5 地址策略与插件页面不能直接共用的原因

`src/client/browser/url.ts:25` 只接受 HTTP(S)，无 scheme 时补 HTTPS；拒绝嵌入账号密码、其他协议和应用自身 origin。主进程 `apps/desktop/src/browser-guests.ts:147` 还过滤 guest 的网络请求，禁止访问应用 Host，并处理相同端口的 loopback 别名。

所以 `/plugins/agent-goal` 这种应用内页面应走专用 `plugin-page` 类型；一般网站与本地开发服务走 `browser` 类型。两者共享 Dock、标签、工具栏部件和生命周期基础设施，访问策略分别定义。

### 3.6 用户浏览与模型操作是两套能力

右栏 Browser 是用户界面，不注册模型工具，也不自动把网页内容加入模型上下文。DSH 另有 `packages/browser-use/browser-use` 和三个实验性提供方：Playwright MCP、Chrome DevTools MCP、Stagehand。它们按 Agent/Session 管理浏览器控制资源。

源码没有表明右栏 webview 自动成为这些提供方控制的浏览器。若后续需要“让模型操作当前右栏网页”，还需单独设计浏览器实例绑定、读页/截图/操作接口及会话归属。

## 4. SugarAgent 建议开放的插件接口

以下是建议新增的接口，不是当前已支持的语法。

### 4.1 声明式右栏页面

可增加 `capabilities.ui["details.tab"]`，插件通过声明注册页面，宿主校验并生成页面地址。例如：

```json
{
  "capabilities": {
    "web": { "entry": "web/index.html", "assets": "web" },
    "ui": {
      "details.tab": [
        { "id": "main", "title": "Agent Team", "scope": "session", "order": 60 }
      ]
    }
  }
}
```

第一版每个页面使用已声明的 `web.entry`；不接受随意传入 HTML、脚本或任意 URL。已有 `navigation` 页面贡献可以由兼容适配器自动映射到默认右栏页，再逐步升级 manifest。

`scope` 需要区分会话业务与应用业务：Goal/Team 绑定会话；线程监控、账号等数据属于应用。页面数据范围与 Dock 布局归属应分开定义；应用页面需要在没有当前会话时也能打开，不能为了展示页面隐式创建用户会话。

### 4.2 统一打开 API 与页面桥接

建议新增 `MyAgentDock.openPluginPage(pluginId, options)`，并完善通用 `openTab(kind, options)`。打开时由宿主完成已启用声明检查、标签去重、落位、展开和上下文绑定。去重键至少包含插件、页面及绑定会话；同一页面重复点击聚焦已有标签。

普通插件通过声明得到宿主创建的 iframe；可信内置渲染器可复用现有物理目录和 `system_builtin` 校验机制。不能因为开放右栏，就把普通插件提升为可任意导入宿主 JS 的渲染器。

页面桥接可沿用设置页现有 `postMessage` 模式，增加版本、请求 ID 和标签归属，提供：

- ready/context：主题、语言、字号、插件/标签 ID、绑定会话与工作区上下文。
- visibility/dispose：暂停轮询、保存必要页面状态、关闭连接与取消请求。
- 请求打开本插件页面、打开网址、打开设置和关闭自身；宿主按操作逐项校验。

同时验证 `event.origin` 与 `event.source`，会话来自标签绑定，不接受页面伪造的任意会话身份。当前子代理与父会话共用右栏布局（`right-column.js:712`），还需把布局 surface 身份与业务 session 身份分开，避免给子代理页误传父会话 ID。

同源 iframe 可复用现有插件 API，也隔离样式，但**不构成不可信插件的权限隔离**。同源页面仍可访问同源资源；如果未来接入不可信网页插件，需另行建设独立 origin 和受限 RPC，不能仅增加 sandbox 属性后宣称完成隔离。

### 4.3 设置页内“打开页面”的处理

主聊天页将设置中心作为 iframe 浮层打开（`frontend/src/app/modules/settings.js:135`），设置中心自身没有主页面的 `MyAgentDock`。应由设置中心向宿主发送明确的打开插件页消息，主页面校验发送 frame 和插件声明，完成设置未保存检查后关闭浮层并展示右栏。

直接访问 `/settings` 时没有聊天宿主，应跳转到带受校验深链参数的主页面，再由主页面打开右栏。保留已有 `embedded: true` 设置分区；设置表单仍由设置中心负责，插件业务页面改走右栏。

### 4.4 迁移页面还需做的适配

- Goal/Team 页面当前要求手填 Session ID，应读取宿主绑定上下文；两个页面的 `style.css/app.js` 使用相对地址，迁移时统一改为 `/plugin-assets/{id}/…`。当前入口 `/plugins/{id}` 下，这些相对地址会解析到 `/plugins/style.css` 等位置。
- `sugar-bili-scroll` 有 `target="_top"` 返回入口，需改为面板模式下的关闭/导航请求；`thread-monitor` 的返回按钮也需适配。
- 线程监控定时器与 B 站状态/二维码轮询需响应隐藏和关闭；不能将页面保活等同于持续轮询。
- 现有页面需适配右栏窄宽、主题与字号。棋盘等宽内容可以使用现有右栏全屏，不必另开窗口。
- 插件停用、卸载、重新加载时同步注销入口和页面实例；禁止旧异步结果重新挂回已关闭标签。

## 5. 实施顺序与验证范围

| 阶段 | 修改范围 | 验收重点 |
|---|---|---|
| 1. 接通右栏扩展 | `app/plugins/ui.py`、`plugin-ui-slots.js`、Dock 注册表与正文渲染、开始页 | 声明可校验、注册正文可显示、重复打开聚焦、注销后无残留 |
| 2. 完成页面生命周期与迁移 | Dock 正文/浮动管理、页面桥接、各打开入口、设置外壳与插件页面 | 五个导航页进入右栏；已内嵌设置可用；主题、绑定会话、窄宽和关闭回收正常 |
| 3. 增加浏览器 | 独立 Browser 类型、共用导航控制器、Web iframe；Desktop 主进程和 preload | URL/历史/标题、原生新页路由、隔离分区、站点拒绝嵌入的外部打开出口 |
| 4. 可选模型接入 | 浏览器控制提供方与可见页面绑定 | 模型明确操作指定页面，跨会话不会串用浏览器 |

插件迁移需要覆盖聊天插件按钮、输入动作、设置插件列表及设置独立分区；还要检查没有当前会话、父子会话共用布局、切标签、切会话、分栏、浮动、收起、禁用和关闭。页面保活应使用真实 iframe/webview 验证，不能只断言缓存 Map 仍存在。

浏览器需要分别验证 Web 和 Desktop。Web 不能要求绕过站点防嵌入策略；Desktop 需要验证未授权 guest 挂载拒绝、应用 Host 请求拒绝、关闭释放资源、guest 崩溃和旧异步初始化取消。与浏览器无关的插件页面迁移可先独立交付。

## 6. 主要源码索引与验证状态

SugarAgent：`app/plugins/ui.py`、`app/plugins/web.py`、`app/plugin_web_gateway.py`、`app/webui.py:10282`；`frontend/src/app/plugin-ui-slots.js`、`modules/skill-picker.js`、`modules/settings.js`、`modules/dock/embedder/{tab-registry,right-column,surface-store}.js`、`modules/dock/renderer/dock-surface.js`；`app/templates/static/settings/{plugin_sections,sections_ext}.js`；`packaging/electron/{main,preload}.js`。

DSH：`packages/client/ui-sidebar-browser/README.zh.md`、`src/client/{index.ts,definition.tsx}`、`src/client/browser/{BrowserController,IframeImpl,url}.ts`、`src/client/view/IframePresentation.ts`、`src/client/electron/{ElectronWebViewImpl,ElectronWebviewPresentation}.ts`；`apps/desktop/src/{browser-guests,preload-browser,main}.ts`；`packages/client/ui-sidebar-right/`；`packages/bundle/web-app/cordis.patch.yml:272`；`docs/subsystems/browser-use.zh.md`。

本文完成了本地源码及 manifest 核对，未启动两个应用验证实际页面行为，也未运行功能测试。除本文外没有修改代码；实施阶段的运行验收项已列在上节。
