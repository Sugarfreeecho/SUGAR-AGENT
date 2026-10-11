# 桌面壳右键菜单 · 功能方案设计（UseCase 清单）

- 版本：2026-10-11 v1（覆盖至：当前工作区；14 类对象的自定义菜单与原生菜单仲裁）
- 用途：逐条审查（四字段格式）。
- 适用实现：`frontend/src/app/modules/context-menus.js`（共享菜单与 `MyAgentContextMenu.bind`）、`frontend/src/styles/context-menus.css`、`packaging/electron/main.js`（`installNativeContextMenu` 原生回退与 frame 定位）、`packaging/electron/preload.js`。
- 上级：`00-WebUI对话界面整体设计.md`｜功能清单：[`../../desktop-context-menus.md`](../../desktop-context-menus.md)（14 类对象的操作表与验证入口）。

---

## 1. 功能定位

右键菜单按点击对象提供操作，复用各区域已有的按钮、确认弹窗和后端接口；前端处理的菜单阻止原生菜单重复弹出，文本编辑与图片操作保留 Chromium/Electron 原生行为。

## 2. UseCase

### UC-5Q1 会话与工作目录区菜单
- **触发**：右键会话列表项、会话标题或工作目录分组标题。
- **预期现象**：会话项提供打开、置顶、待办、重命名、归档、导出、删除、复制会话 ID；目录组提供展开/折叠、在目录中新建会话、重命名、复制路径、打开目录。均复用既有入口与禁用状态。
- **依据**：`context-menus.js` 会话区 provider；`tests/test_context_menus_browser.py`。

### UC-5Q2 消息、执行过程与修改历史菜单
- **触发**：右键用户消息、助手回答、代码块、链接、执行过程或修改历史条目。
- **预期现象**：用户消息支持复制原始内容、改写、删除本条及后续对话；回答/代码/链接支持复制原始 Markdown、导出文本或图片、分支、删除后续对话、代码复制、打开或复制链接；执行过程复制包含折叠详情并可展开/折叠；修改历史展开差分、预览文件、复制差分与路径、撤销或恢复（沿用已有状态限制）。
- **规则与边界**：生成中的会话禁用改写与历史删除；选区在菜单获得焦点之前捕获；消息复制复用原始 Markdown 而非渲染文本。
- **依据**：`context-menus.js` 消息区 provider、`message-rendering.js` 原始文本源。

### UC-5Q3 工作区、媒体与附件路径菜单
- **触发**：右键工作区文件、文件预览、输入附件路径或图片/音视频。
- **预期现象**：文件类支持预览或展开目录、系统打开、打开所在目录、复制绝对或相对路径、刷新、切换源码或预览、移除输入附件；图片复制和保存使用原生菜单；音视频支持播放/暂停、静音、循环与复制地址。
- **依据**：`context-menus.js` 工作区 provider、`workspace-media.js`、插件会话面板附件卡片。

### UC-5Q4 面板、任务与窗口菜单
- **触发**：右键会话状态/计划/Goal、后台任务、持久终端、用户交互终端、标签栏、浮动窗口、历史记录或聊天空白处。
- **预期现象**：状态/计划/Goal 仅呈现当前可用操作（复制内容、清除计划、统计、暂停/继续、编辑、删除、结果审核）；后台任务与持久终端提供复用输出、连接、查看、停止、结束、复制输出与关闭视图；终端提供复制选区、粘贴、全选、清空视图、回到底部、关闭视图——清空或关闭视图均不结束 shell；标签栏/浮窗提供新建、复制、分屏、移至浮窗、关闭当前或其他或右侧标签、放回主区/关闭浮窗；空白处提供跳转消息、复制记录、回到最新、展开或折叠侧面板。
- **依据**：`context-menus.js` 各面板 provider；`tests/js/desktop_shell_runtime.cjs`。

### UC-5Q5 键盘可达性、关闭条件与生成态限制
- **触发**：键盘操作或菜单打开期间的外部交互。
- **预期现象**：`Shift+F10` 或菜单键打开菜单；方向键、Home、End 导航；Enter 或空格执行；Esc 或 Tab 关闭并恢复焦点。点击外部、实际滚动、窗口尺寸变化、窗口失焦、对象被移除或切换会话会关闭菜单；菜单始终限制在窗口边界内，支持浅色/深色/紫色主题与字体缩放，长菜单可滚动。
- **依据**：`context-menus.js` 键盘与生命周期管理；`tests/test_context_menus_browser.py`（真实点击、键盘、窗口边界、过期对象、标签与浮窗）。

### UC-5Q6 原生菜单互斥与插件接口
- **触发**：右键文本编辑区域、设置窗口、首启向导、内嵌 iframe，或插件通过 `MyAgentContextMenu.bind(element, provider)` 注册自定义菜单。
- **预期现象**：前端处理的菜单阻止原生菜单弹出；文本编辑与图片操作保留 Chromium/Electron 原生行为，操作定位到实际点击的页面或内嵌框架（原生弹窗的 `frame` 为对应 frame）；插件 provider 返回菜单项数组、bind 返回清理函数并在生命周期结束时注销；菜单内部不绕过现有操作的禁用状态。
- **规则与边界**：Electron 主进程 `installNativeContextMenu` 只在自定义菜单未处理时弹出原生回退；preload 修改需桌面客户端重启生效。
- **依据**：`packaging/electron/main.js::installNativeContextMenu`、`preload.js`；`tests/js/desktop_context_menu_electron.cjs`（真实 Electron 不可见窗口验证互斥、原生编辑与 iframe 定位）、`tests/test_desktop_context_menu.py`。

## 3. 边界

- 菜单只是既有操作的第二入口：不新增业务语义，删除/撤销/恢复/停止等仍走原流程与状态限制；
- 浏览器端（非桌面壳）下原生回退由浏览器自身提供，本专项的互斥与 frame 定位只在 Electron 壳内生效。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-5Q1~5Q4 | `frontend/src/app/modules/context-menus.js`、`styles/context-menus.css` 及各区域 provider |
| UC-5Q5 | `context-menus.js` 键盘/生命周期；`tests/test_context_menus_browser.py` |
| UC-5Q6 | `packaging/electron/main.js::installNativeContextMenu`、`preload.js`；`tests/js/desktop_context_menu_electron.cjs`、`tests/test_desktop_context_menu.py` |

## 5. 版本记录

- 2026-10-11 v1：初版——14 类对象的菜单操作、键盘与关闭条件、生成态限制、原生菜单互斥与 frame 定位、插件 `bind` 接口；落地 `context-menus.js/.css` 与 Electron 主进程/预加载改动。
