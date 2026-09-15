# 右侧详情栏（dsh dockkit 单挂载点）

> 更新日期：2026-09-14 ｜ 参照：`deepseek-harness/packages/client/ui-dockkit`（引擎/组件契约）、
> `ui-sidebar-right`（右栏产品化与 `ExpandButton`）、`ui-sidebar-files` /
> `ui-sidebar-documentpreview`（文件树与预览类型）。

WebUI 按 dsh 的三段式布局：最左会话列表、中间会话、右侧一个可开合的**详情栏**。
详情栏是 dockkit 在本项目的唯一挂载点：会话标题右上角的图标按钮打开，向左推挤
工作区，内置「工作区文件 / 文件内容 / 修改历史」三页。

> 早前版本曾同时在主内容区挂一套"会话分屏 + conversation 标签 + 只读镜像"，
> 已按要求整体移除（含分屏按钮、conversation 类型与镜像管线）。引擎、渲染器与
> 注册表原样保留，供详情栏使用。

---

## 1. 三层分离

```
┌─ embedder（产品层）──────────────────────────────────────────────────────┐
│  right-column.js  右侧轨道、拖宽柄、角落按钮、三个内置页、公开 API        │
│  surface-store.js 每会话停靠面 { layout, history, minted }（区域 right） │
│  tab-registry.js  标签类型注册表（band 解析、资源地址）                   │
│  integration.js   已删除（原主区挂载）                                    │
│                                                                          │
│  ┌─ renderer（DOM 渲染 + 手势，只报告意图）───────────────────────────┐   │
│  │  dock-surface.js 分割树/tab 条/分隔条；float-layer.js 浮动面板      │   │
│  │  gesture.js 指针原语；measure.js 房间规则读数                        │   │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌─ engine（纯逻辑，无 DOM、无框架、无宿主概念）──────────────────────┐  │
│  │  types / tree / constraints / geometry / operations / planner /    │  │
│  │  sequence / controller                                             │  │
│  └────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
```

**引擎是唯一计算布局的地方。**`applyOp(state, op)` 返回 `{ state, inverse }`，
逆操作在操作运行时捕获；创建型操作携带它创建的 ids，引擎不读时钟、不读随机源，
因此「同一初始状态 + 同一操作序列」经 `dockReplay` 必然重现同一棵树。

## 2. 文件与职责

| 文件 | 职责 |
|---|---|
| `modules/dock/engine/types.js` | 数据模型、id 铸造（`dockCreateMinter`）、结构判定 |
| `modules/dock/engine/tree.js` | 树读取器（悬空 id 抛错）与不可变写器 |
| `modules/dock/engine/constraints.js` | 常量、五区判定、`dockClampSizes` |
| `modules/dock/engine/geometry.js` | 落点几何、插入槽、房间规则（`dockHalvesFit`）、拖动阈值 |
| `modules/dock/engine/operations.js` | `dockApplyOp` / `dockReplay`（闭合操作联合） |
| `modules/dock/engine/planner.js` | 每个交互 = `(state, mint, …) → ops[]`；空数组 = 无操作 |
| `modules/dock/engine/sequence.js` | 意图级历史、focus 合并、`DockSequencer` |
| `modules/dock/engine/controller.js` | `DockController`（subscribe/getSnapshot） |
| `modules/dock/renderer/dock-surface.js` | 停靠面渲染 + tab/分隔条手势（只报告净结果） |
| `modules/dock/renderer/float-layer.js` | 浮动面板：移动/缩放/放回/关闭 |
| `modules/dock/renderer/gesture.js` | 指针捕获 + 窗口监听兜底 + 单手势控制器 |
| `modules/dock/renderer/measure.js` | 每次提交/尺寸变化后读矩形，产出房间规则读数 |
| `modules/dock/embedder/surface-store.js` | 每会话 `{ layout, history, minted }`；产品动作（区域 `right`） |
| `modules/dock/embedder/tab-registry.js` | 标签类型注册表（band 解析、资源地址） |
| `modules/dock/embedder/right-column.js` | 详情栏：轨道、拖宽、角落按钮、三页、公开 API |
| `styles/dock.css` | 全部样式（仅用现有主题变量） |
| `tests/dock-engine.test.mjs` | 引擎的 node 断言（24 项） |
| `workspace/分屏功能需求/dock_verify/dock_smoke.py` | 真实浏览器冒烟（详情栏） |

`app/index.js` 的拼接顺序：原有模块 → 引擎 8 件 → 渲染 4 件 → 嵌入 3 件
（`right-column.js` 最后加载，装配 `MyAgentDock` 并派发 `myagent:dock-ready`）。

## 3. 入口按钮（与 dsh 相同）

- **位置**：会话标题栏最右角落（dsh 的 `conversation.session.header.corner`）。
- **形态**：28px 圆形图标按钮，15px 面板图标（左侧栏图标镜像，分隔线在右）；
  无文字、悬停高亮、`title=打开侧边栏`、`aria-label=打开右侧边栏`。
- **行为**：常驻开关——图标始终可见，展开时呈按下态，再点即收起；详情栏自身 tab 条右端也有收起控件。（早前"展开即隐去"的 dsh 原版行为按用户要求改为常驻。）
- 图标路径内联自 dsh `ui-primitives` 的 `IconPanelLeftOutline16`（页面没有图标库）。

**条尾三个控件（与 dsh 图形逐字一致，见 [icons.js](../frontend/src/app/modules/dock/renderer/icons.js)）**：

| 控件 | 图形 | 来源 |
|---|---|---|
| 分栏 | 面板框 + 居中竖线 | `ui-dockkit` `TabPanel.tsx` 的 `SplitGlyph`（`PANEL_FRAME` + 中线） |
| 全屏 / 退出全屏 | 四角括号 / 两内收角 | `ui-sidebar-right` `SidebarRight.tsx` 的 `FullscreenGlyph` / `ExitFullscreenGlyph`（figma 抽取） |
| 收起侧边栏 | 面板图标镜像 | `ui-primitives` `IconPanelLeftOutline16` + `scaleX(-1)`，同 dsh 的 `collapseGlyph` |

四枚路径都由脚本从 dsh 源码直接抽取（不手抄），28px 圆形按钮内 15px 图形，间距 4px，与 dsh `iconButton` 一致。

## 4. 三个内置页

| 页 | 数据源 | 说明 |
|---|---|---|
| 开始（guide） | 无 | 栏的首页与兜底页：关闭栏内最后一个页签时由 settle 重新播种它（栏不会随之收起）；`+` = 在该面板新建一个开始页（"空窗口"）；引导卡进入文件树/修改历史 |
| 工作区文件 | `GET /api/workspace-files?dir=` | 逐层展开的树；目录优先、显示大小、可刷新；点文件打开文件内容页 |
| 文件内容 | 图片 `/api/workspace-image`；音视频 `/api/workspace-media`；文本 `GET /api/workspace-file-text`（新增） | 文本 UTF-8、按 200 KB 截断并提示；二进制提示"在系统应用中打开"；工具栏常备系统打开入口 |
| 修改历史 | 会话历史中的 `ui.changes`（`/sessions/{id}/history_snapshot`） | 按路径取最新 revision；± 着色 diff 可展开；撤销/恢复走 `change-reviews/undo\|restore`（工作区运行中时服务端 409）；监听 `myagent:ui-event` 实时追加 |

补充（2026-09-14 第二轮反馈）：

- **文件树分类图标**：按扩展名给色的 SVG（图片/代码/配置/文档/PDF/文件夹/通用文件）；
- **非文本兜底**：先按后缀（pdf/doc/xls/zip/exe…）直接给"系统打开"卡片；文本接口读回后
  若替换字符占比 >2% 也自动切到该卡片，不再显示乱码；
- **滚动记忆**：树、文件内容、修改历史各自的滚动位置按页签记录，被换出后重新挂回时恢复
  （浏览器会丢掉脱离文档的 scroller 位置，由 `__dockRestore` 钩子补回）；
- **分栏**：第二个面板以"开始"页落座（不再复制同一窗口）；两面板后分栏控件隐藏（死按钮不再出现）；
- **关合过渡**：轨道宽度 + 透明度 180ms 动画；**胶囊**：38px 条内上下各 5px 真正居中，最小宽 96px、最大 230px。
- **第三轮反馈**（2026-09-14）：角标加 `[hidden]` 样式修复"展开后仍可见"；Change Review 的「查看」被
  捕获改为打开详情栏的修改历史页；修改历史按"本轮 / 本次会话"两档呈现（默认本轮，样式借改动审查
  卡片：整行 +/- 底色、文件头、状态行）；只剩一个"开始"页时关闭它=收起详情栏；胶囊在浅色主题
  加底色与描边（此前近乎透明）。
- **统一开文件策略**：会话里的工作区文件链接（`a.msg-link-workspace-open`）改经
  `MyAgentDock.openPathSmart`：**文本后缀**（md/py/json/…，排除二进制与图片/音视频）在详情栏打开；
  其余一律交系统应用——与文件树点击同一套判定（`MyAgentDock.isTextPath` 可单独查询）。
- **修改历史**：页头两档"本轮 / 本次会话"（默认本轮，边界=最近一条用户消息，且**随新的用户消息即时推进**）；
  扫描带 20s 超时、失败静默重试 ×2、2s 看门狗，首次打开与会话切换并发时不会留下空页（诊断脚本
  `dock_verify/turn_scope_probe.py`、`dock_verify/scope_probe_browser.py`）。
- **改动审查「查看」已回退为插件原生浮窗**：详情栏不再捕获该按钮（先前"按批次对齐"的实验已整体删除）；
  修改历史页仍是独立的会话级视图（本轮/本次会话双档）。

> ⚠️ `/api/workspace-file-text` 是后端路由，**需重启一次服务**才生效；在此之前文本页
> 显示"文本接口尚不可用（可在系统应用中打开）"，其余功能不受影响。

## 5. 交互与手势（照抄 dsh 的缺陷修复）

| 操作 | 结果 |
|---|---|
| 点角落按钮 | 打开详情栏（默认显示工作区文件页） |
| 拖左缘 8px | 调宽 320–960px；双击复位；宽度按浏览器记忆 |
| 面板 tab 条的 `▥` | 栏内分栏（水平、至多两面板；宽度不足时禁用/隐藏） |
| 拖 tab 到左右半区 / 面板中间 / 条内 | 分割落座 / 移入 / 重排（caret 按 chip 中点） |
| 拖 tab 出栏 | 浮动面板 380×300（级联 24px），可移动缩放、`⇤` 放回、`×` 关闭 |
| 拖分隔条 | 两侧吸收全部变化，每侧最小 20%（引擎下限 12%），松手不跳变 |
| chip 键盘 | ←/→/Home/End 移动焦点，Enter/Space 选中（WAI-ARIA tabs，手动激活） |

持久规则：手势开始捕获指针（窗口监听兜底）；chip 盒 `touch-action:none`（可滚动
但从不认领手势）；chips 让步、条尾控件永不让步；焦点落 click 不落 press；嵌套
关闭按钮停止自己的 press；全屏用主题 accent。

## 6. 公开接口

`globalThis.MyAgentDock`（`myagent:dock-ready` 后可用）：

```js
MyAgentDock.registerTabType({ id, kind, patterns?, priority?, canOpen?, title, body })
MyAgentDock.openResource('myagent-resource://<type>/…')   // 解析后落座详情栏
MyAgentDock.openDetails() / toggleDetails() / closeDetails()
MyAgentDock.openDetailsTab('files' | 'changes')            // 页面按 kind
MyAgentDock.openDetailsFile(workspaceRelPath)              // 文本/图片/媒体页
MyAgentDock.detailsState()                                 // 当前会话的栏布局
MyAgentDock.openSession(sessionId)                         // 切换会话（栏状态随动）
MyAgentDock.sessionId()
```

解析优先级：`extension > builtin > fallback` → 模式长度 → 注册顺序；`canOpen`
一票否决；页面地址 `myagent-page://<kind>`，资源地址 `myagent-resource://<type>/…`。
内置类型 id：`myagent.details.files` / `.document` / `.changes`。

## 7. 每会话状态与序列化

每会话一份 `{ layout, history, minted }`（区域 `right`），切会话切换栏状态、切回
保留、刷新回收起默认（memory-only，与 dsh 一致）。`SurfaceState` 是纯数据，可序列
化后 `dockReplay` 还原出逐 id 相同的树；接入方式为把 JSON 写入 `localStorage`
并在初始化时 replay。

## 8. 验证

```bash
cd frontend
node tests/dock-engine.test.mjs        # 引擎 24 项断言（无浏览器）
npm run build                          # 同步 app/templates/dist
npm run verify:dist                    # dist 与源码一致性
python ../workspace/分屏功能需求/dock_verify/dock_smoke.py   # 真实浏览器冒烟（需服务在 8192）
```

冒烟覆盖：启动回归、角落按钮（图标、展开隐去）、开栏推挤（1220→760px）、文件树
列出工作区、拖宽柄调宽（460→580px）、从树打开文本文件（文本接口未生效时优雅
降级）、修改历史列出会话改动并带撤销按钮、切会话后栏状态保持、收起、无页面错误。

## 9. 与 dsh 的记录在案差异

- **无主区会话分屏**：dsh 的 dockkit 只在右栏；本项目按其形态收敛，主区恢复原有
  单会话视图（早期双挂载实验已移除）。
- **撤销/重做无 UI**：引擎保留完整历史（`undo/redo` 于 store 可用），本期无入口。
- **持久化默认关闭**：dsh 为 memory-only；本实现具备 replay 确定性与序列化格式。
- **文本读取**：新增了一个最小后端接口（见第 4 节），这是相对 dsh（其远程工作区
  天然可读）唯一需要补的后端面；其余内容类型都复用既有接口。
- **无 rail/折叠轨道**：收起即完全不占位，保留角落按钮作入口。
