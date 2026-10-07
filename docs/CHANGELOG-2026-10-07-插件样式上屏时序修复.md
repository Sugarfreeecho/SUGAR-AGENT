# 2026-10-07 插件样式上屏时序修复（改动审查 +/− 数字的"灰白一闪"）

## 一、症状

页面加载/刷新后的一两秒内，**改动审查的 +/− 数字先以未套样式的样子出现**（灰黑、没有红绿），随后才变成红绿：

- 会话里「执行过程」标题右侧的小徽标（`+x −y`）；
- 左栏「改动」页签 / 浮窗里的改动审查卡片（标题行与文件行）。

用户描述为"还没加载好的样子，过 1–2 秒就正常了"。与之无关的更早一次故障（改动审查完全不显示）是执行记录丢 `ui.changes`（见 `CHANGELOG-2026-10-06-改动审查数据链路修复.md`）。

## 二、根因

改动审查是插件：卡片/徽标的 **± 数字依赖插件自带样式表**（`.change-review-stat-added/removed`、`.pni-summary .pn-add/.pn-del`）。而 `frontend/src/app/plugin-ui-slots.js` 的加载器只把插件的 `<link rel=stylesheet>` 追加到 `<head>` 就继续 `import()` 并 `installChatExtension()`，**不等待样式表可用**：

- 数据（行、计数）本地就有 → 卡片/徽标立刻渲染；
- 样式表还在路上 → 数字继承容器字色（灰黑）；
- 样式表到达并应用 → 数字变红绿。

所以它是**时序问题**，不是配色值错：插件 CSS 自 2026-09-08 起就只有正确的 `color: var(--green-accent) / var(--red-accent)`，三分主题（默认深色、浅色、DSH 深色）的变量都在。也解释了"先前像是修好了、后来又出现"——冷缓存/首次加载明显，热缓存几乎看不见。

## 三、修复

`frontend/src/app/plugin-ui-slots.js`：

- 新增 `PLUGIN_STYLE_WAIT_MS = 8000` 与 `pluginStyleReady(link, timeoutMs)`：`link.sheet` 已存在→立即完成；否则等 `load`，失败走 `error`，并带**有界超时**兜底（都不会让插件界面被无限阻塞）。
- 新增 `ensurePluginStyleLink(definition, datasetProperty, attributeName)`：复用/创建插件样式 `<link>`（沿用原有 `data-plugin-chat-style` / `data-plugin-panel-style` 标记）并等待其可用。
- `loadPluginChatExtensions` / `loadPluginSessionPanelRenderers` 改为 `await Promise.all([import(moduleUrl), ensurePluginStyleLink(...)])` 之后再挂载渲染器——聊天扩展与左侧会话面板同一口径。

行为：样式就绪前不绘制插件界面；样式极慢时**界面整体延后出现**（而非先出未样式化界面）；样式加载失败/超时则照旧继续挂载（只是没有插件样式），不影响功能。

## 四、验证

- **实机 A/B 探针**（同一台机器、同一会话；探针把插件样式表的真正插入延后 4 s 以制造冷缓存条件，见 `workspace/改动审查修复_验证/probe-paint.js`）：

  | 判据 | 旧行为（挂 link 不等待） | 修复后 |
  | --- | --- | --- |
  | ± 数字首次可见 | 9616 ms（样式生效 **前** ~4 s） | 10369 ms（样式生效 **后** +12 ms） |
  | 首次可见颜色 | `rgb(0,0,0)` → `rgb(14,15,26)`（灰黑） | `rgb(21,128,61)`（绿） |
  | "数字已上屏但还不是红绿"的帧数 | **243 帧 ≈ 4.0 s** | **0 帧** |

- **最终构建实测**（无探针）：打开 `538fea5c`，采样 1200 帧；± 数字与过程框徽标首次可见即 `rgb(21,128,61)`，异常帧 **0**。
- **回归测试**：`tests/js/plugin_ui_slots_runtime.mjs` 新增 `pluginStyleReady` 行为用例（已应用/等待 load/error/超时有界）；`tests/test_plugin_ui_frontend.py` 新增契约用例，要求两个加载器都把"样式就绪"与模块导入一起 `await`，且旧的"挂上 link 不等待"写法必须消失。跑 `tests/test_plugin_ui_frontend.py tests/test_change_review_ui_payload_runtime.py tests/test_change_review_plugin.py` → **70 passed**。

## 五、文件

- `frontend/src/app/plugin-ui-slots.js`（等待插件样式再挂载渲染器）
- `tests/js/plugin_ui_slots_runtime.mjs`、`tests/test_plugin_ui_frontend.py`（回归）
- `app/templates/dist/**`（重建产物）

## 六、边界

- 样式表极慢（> 8 s，例如服务器繁忙 + 冷缓存）时，插件界面最多延后 8 s 出现；这是有意的取舍——宁可不显示，也不要显示一版会误导的未样式化界面。
- 本次只解决"插件界面先于自己的样式表上屏"；宿主面板（左栏页签、浮窗壳体、详情栏「修改历史」）由主样式表渲染，本来就不受影响。
