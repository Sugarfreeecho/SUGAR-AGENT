# CHANGELOG — 2026-08-15（上午补充批次）

本批次来自 8/15 上午的 Codex 会话（10:08–10:56），与先前"恢复门禁/执行轨迹"批次同日。

## 一、会话待办标签与 Goal 待审核标签（10:08b / 10:25）

- 侧边栏会话可标记为"**待办**"（todo 标签，类似草稿徽章）；切换会话时窗口名残留问题同步修复。
- Goal 完成后，会话目录显示"**待审核**"标签（`goal_review_pending`），与结果审核流程衔接。
- 会话元数据新增 `todo` / `goal_review_pending` 字段（`webui.py` 透出）。

## 二、Ask 卡片交互优化（10:08a）

- 提交按钮仅在**所有问题回答完毕**后显示；未答完时使用"确认"。
- "不回答"仅跳过当前题目，不终止整个问答。

## 三、输入框与悬浮层修复（10:26a / 10:30 / 10:26b 后续）

- 重命名等输入框在**拖选文本越出窗口**时不再误关闭；点击外部区域关闭机制保留。
- 生成中换行不再导致 MCP 等 hover 浮窗关闭（与"追问模式选项框"同类问题一并修复）。
- 拖文件入输入框发送无响应问题后续修复（媒体路径序列化相关，见先前 media 提交）。
- 新增 `ui_hover_runtime.cjs` 运行时测试。

## 四、执行轨迹与 UI 打磨（10:26b 后续）

- 执行轨迹行文本权重/字号可读性优化（v2 前端版本）。
- LLM reasoning 行在回合结束前自动折叠（`finalizeActiveLlmReasoningRow`）。
- 各主题定义不同的悬浮表面色（`--floating-surface`）。
- MCP 注册失败改用全局警告横幅（`skill-picker.js`）。

## 五、系统通知迁移与常驻图标 UX（10:56）

- 后台完成系统提醒优化：系统提示包含**状态 + 会话名 + 最近发送的问题**，移除"打开 SugarAgent"按钮；系统通知 API 不可用时回退原生消息框。
- **托盘概念统一为"常驻图标"**（Windows 任务栏右下角 / macOS 顶部菜单栏 / Ubuntu 顶部栏），文档与文案同步（README/SPEC/frontend README）。
- 前端关闭时左下角 Runtime 图标状态同步；托盘打开 UI 复用已有前端页面（`_ui_presence_has_reusable`），防止重复开启；托盘通知全部迁移至系统通知。
- 相关：`desktop_notify.py`、`notify_ui_closed.ps1`、`tray_launcher.py`、`agent_updater.py`、`webui.py`、`first_time_config.html`。

## 相关提交（本批次）

- `feat(webui): session todo labels and Goal review badges`
- `feat(human): Ask card submit-on-all-answered behavior`
- `fix(webui): input drag-select and hover regressions`
- `feat(webui): execution trace readability and registration banner`
- `feat(notify): system notification migration and resident icon UX`
- `build: sync frontend distribution`
