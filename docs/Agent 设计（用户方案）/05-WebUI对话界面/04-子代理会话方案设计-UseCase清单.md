# 子代理会话 · 功能方案设计（UseCase 清单）

- 版本：2026-09-18 v4（在 v3「dsh 式重建」整体重写基础上补 UC-5D15；覆盖至：`4083cbc` + 模型选择器接线）
- 用途：逐条审查（四字段格式）。
- 适用实现：`frontend/src/app/modules/ui-slot-registry.js`、`state/subagent-catalog-store.js`、`state/subagent-addressing.js`、`modules/subagent-frames.js`、`state/subagent-ui-decisions.js`、`modules/subagent-catalog-ui.js`、`modules/subagent-composer-ui.js`、`tests/subagent-ui-foundation.test.mjs`；接线点 `index.js` / `message-rendering.js` / `session-management.js` / `sse-handling.js` / `styles/app.css` 追加块。后端零改动。
- 上级：`00-WebUI对话界面整体设计.md`

---

## 1. 功能定位

子代理不再是"抽屉面板里的卡片"，而是**可寻址的会话**（沿 dsh 设计）：标题栏出现一台"谱系目录"，点开即把主子会话切进主对话区查看其完整会话（含历史与流式）；输入区按"谁在说话"自动进入可写 / 锁定 / 只读三态，并在子结果未纳入父回答时给出"继续综合"入口。

## 2. UseCase

### 2.1 标题栏谱系目录

#### UC-5D1 触发器出现与计数
- **触发**：当前会话存在子代理（或流里刚刚出现其成员帧）。
- **预期现象**：标题右侧出现一枚胶囊"**N 个子代理**"；有任一子代理运行中时显示活动点并写"**N 个子代理 · M 运行中**"；**无子代理的会话不出现任何触发器**（不闪烁）。
- **依据**：`subagent-catalog-ui.js::renderTrigger`（证据=目录行或流内成员帧；`.subagent-catalog-trigger`）。

#### UC-5D2 目录树内容
- **触发**：点击触发器展开目录。
- **预期现象**：逐行列出子代理——行首状态点、**子代理自己的名称**（`name→title→description→subagent_type` 兜底）、行尾元信息（耗时 / 惰性拉取的 token 指标）；当前已寻址的行显示选中标记；空目录显示"暂无子代理"。
- **依据**：`subagent-catalog-store.js::normalizeEntry`（label 优先级）、`subagent-catalog-ui.js`（门户 fixed 定位、`role=tree`）。

#### UC-5D3 键盘导航
- **触发**：目录展开状态下按键。
- **预期现象**：↑↓ 在行间移动、←→ 进入/退出子层级、Home/End 跳首尾、Esc 关闭并还原焦点、Enter 选中。
- **依据**：`subagent-catalog-ui.js::onMenuKeydown`。

#### UC-5D4 状态点语义（四色）
- **触发**：观察任意行的状态点。
- **预期现象**：**琥珀=进行中**（含呼吸动画）；**绿色=正常完成且未读**；**蓝色=正常完成且已读**；**红色=错误**（失败/中断/取消/orphaned/stale/缺结果）；诊断行（不可点开的损坏数据）恒为红色。
- **规则与边界**：判定优先级＝终态 → `ok/error` 字段 → running → queued；打开该子代理后圆点**即时由绿转蓝**（打开即已读）；已读状态持久化在 `localStorage["myagent.subagent.read.v1"]`（隐私模式退化为内存态）。
- **依据**：`subagent-catalog-store.js::inferOutcome / isSubagentRead / markSubagentRead`、`subagent-catalog-ui.js::statusDotClass`、`app.css` 追加块（`.is-running / .is-unread / .is-read / .is-error`）。

#### UC-5D5 目录数据新鲜度
- **触发**：子代理启动/结束、成员帧到达、打开目录。
- **预期现象**：成员帧（SSE `agent_id`）驱动增量更新；未覆盖的子代理立即让触发器显形并**去抖**刷新目录；单飞防重入；请求在途期间到达的帧在结算时折入，不会因旧响应覆盖新事实。
- **依据**：`subagent-frames.js`、`subagent-catalog-store.js::refreshCatalogs`（单飞 + 尾随刷新 + patch 队列）。

### 2.2 会话寻址

#### UC-5D6 打开子会话
- **触发**：点击目录中的一行。
- **预期现象**：主对话区切换到该子代理的**完整会话**（历史分页、流式输出与主会话同体验）；面包屑变为"**‹ 父会话名 / 子会话名**"；该行标记为已读。
- **依据**：`subagent-addressing.js::openChild`（父入栈 → 复用既有 `switchSession` 的 stash/restore）、`message-rendering.js::renderSubagentAddressedTitle`。

#### UC-5D7 返回父会话
- **触发**：点击面包屑的父会话片段（或浏览器后退语义）。
- **预期现象**：回到父会话原位置（滚动位置与未发送草稿保留，复用 stash/restore）；面包屑还原；目录选中态清除。
- **依据**：`subagent-addressing.js::returnToParent`、`session-management.js`（寻址守卫）。

#### UC-5D8 双子会话/刷新健壮性
- **触发**：在子会话中刷新页面；或寻址栈已空但标题残留。
- **预期现象**：刷新后仍停留在该子会话（自动快照恢复）；"标记在、栈已空"的残留面包屑被防御性清掉。
- **依据**：`message-rendering.js::updateSessionTitle`（残留防御分支）、`subagent-addressing.js` 快照恢复。

### 2.3 编辑器三态与续接

#### UC-5D9 三态自动切换
- **触发**：进入/离开子会话、父会话离线、子代理结束。
- **预期现象**：① **可写**：continuable 子代理且父在线；② **锁定**：父离线但子仍在运行——输入禁用、保留 Stop；③ **只读**：one-shot 历史（如 best-of-n 汇总）或父离线且已停——输入区上方出现只读占位说明。
- **规则与边界**：接管走**插槽链选举**（`conversation.composer` 座位，priority -10，select 按只读决策投票）；返回父会话后编辑器还原，不覆盖其它原因造成的禁用。
- **依据**：`subagent-ui-decisions.js::decideEditorState`、`subagent-composer-ui.js::registerComposerSeat / electComposerSeat / syncComposer`、`ui-slot-registry.js`。

#### UC-5D10 续接提示
- **触发**：父会话存在已结束且结果未纳入父回答的子代理（且无子代理运行中）。
- **预期现象**：输入区上方出现提示"**N 个子任务结果尚未纳入上方回答，点击补充综合**"；点击走既有 `/continue-subagents` 流程。
- **依据**：`subagent-composer-ui.js::syncContinueHint`、`subagent-ui-decisions.js`（续接条件纯函数）。

#### UC-5D11 输入门控
- **触发**：只读/锁定态下尝试输入或发送。
- **预期现象**：输入与发送被禁用；恢复可写时还原（不产生"永久锁死"）。
- **依据**：`subagent-composer-ui.js`（门控与还原；测试断言"不覆盖其它禁用原因"）。

### 2.4 纪律与一致性

#### UC-5D12 目录数据只进对象层
- **触发**：审查代码分层。
- **预期现象**：子代理业务数据（地址/目录/已读）只存在于 `subagent-catalog-store.js` 的对象层（引用稳定快照 + subscribe）；UI 只订阅渲染，不反向写状态；slot 注册表遵循"声明即授权、disposer 级联"。
- **依据**：`ui-slot-registry.js`、`subagent-catalog-store.js`、`tests/subagent-ui-foundation.test.mjs`（44 断言）。

#### UC-5D13 后端零改动与成员帧复用
- **触发**：核对前后端改动面。
- **预期现象**：目录数据来自既有 `GET /sessions/{id}/subagents?lite=1`；活跃度来自既有 SSE 的 `agent_id` 帧（`subagent_start/finish` 生命周期帧 + ephemeral 活动帧，1.5s 节流）；**目录链路后端无新增端点**；侧栏的运行中点保持原样。
- **依据**：`subagent-frames.js`、`sse-handling.js`（两个 `agent_id` 分支）、`webui.py`（目录链路未改动；选择器接线见 UC-5D15）。

#### UC-5D14 主对话区无回归
- **触发**：常规对话与流式输出。
- **预期现象**：条目左对齐无横向漂移；页面无横向滚动条（右侧停靠栏收起时其内容被应用壳裁剪）；切换会话、返回父会话均无布局跳动。
- **依据**：`app.css`（`.app { overflow: hidden }` + 末尾限定 `subagent-*`/`breadcrumb-*` 命名空间的追加块）、`verify_stream_layout.py`（横向溢出=0 实测）。

### 2.5 模型入口

#### UC-5D15 子代理会话中的模型选择器
- **触发**：在子代理会话中操作右下角模型选择器。
- **预期现象**：打开子代理会话时选择器显示该子代理的档案；切换作用于该子代理且只影响它——接入层保留全部数据动作（切换记录、fork 冻结释放、父任务行同步、熔断清理、子代理状态事件），**不打断**当前请求，新档案自下一次模型调用生效。
- **规则与边界**：旧 Dock 的"卡片菜单 → 切换模型"入口已随重建移除，**选择器即入口**；`task action=switch_model` 仍按安全边界交接语义执行（中断 + 续跑）。语义细则见 [../01-LLM接入/05-手动切换与兼容降级矩阵方案设计-UseCase清单.md](../01-LLM接入/05-手动切换与兼容降级矩阵方案设计-UseCase清单.md)·UC-1E2。
- **依据**：`webui.py`（`/sessions/{id}/model_profile` 识别 `is_subagent` 并转交 `handover=False`）、`agent_subagent.py::switch_subagent_model_profile`、`subagent-addressing.js`（寻址即切换当前会话，选择器随之刷新）。

## 3. 边界（不在本篇）

- 子代理的**定义/调度**（task 工具）见 [../03-工具系统/工具系统能力清单.md](../03-工具系统/工具系统能力清单.md) §7；
- 子代理的**模型切换语义**（只影响该子代理）见 [../01-LLM接入/05-手动切换与兼容降级矩阵方案设计-UseCase清单.md](../01-LLM接入/05-手动切换与兼容降级矩阵方案设计-UseCase清单.md)；
- 子代理的**存储与运行注册**（Runtime V2 子会话目录、状态词表、修复）见 [../08-会话存储RuntimeV2/04-扩展子代理与运行注册方案设计-UseCase清单.md](../08-会话存储RuntimeV2/04-扩展子代理与运行注册方案设计-UseCase清单.md)；
- **主区会话分屏**按用户要求已移除，不在范围内（原 UC-5H1~5H6 作废）。

## 4. 依据映射

| 层 | 文件 | 职责 |
|---|---|---|
| 插槽 | `modules/ui-slot-registry.js` | 声明即授权、单/链座位、优先级选举、disposer 级联 |
| 对象层 | `state/subagent-catalog-store.js` | 地址/目录/已读/指标；单飞刷新与帧修补；`inferOutcome` |
| 寻址 | `state/subagent-addressing.js` | 父入栈、`switchSession` 复用、返回、快照恢复 |
| 桥接 | `modules/subagent-frames.js` | SSE `agent_id` → 成员帧（节流 + 证据触发刷新） |
| 决策 | `state/subagent-ui-decisions.js` | 编辑器三态 + 续接条件（纯函数） |
| UI | `modules/subagent-catalog-ui.js` / `subagent-composer-ui.js` | 触发器+目录树 / 只读占位+续接提示 |
| 接线 | `index.js`（闭包内 `uiWiring`）、`message-rendering.js`、`session-management.js`、`sse-handling.js` | 装配与守卫 |

## 5. 版本记录

- 2026-09-18 v4：补 UC-5D15「子代理会话中的模型选择器」——旧卡片菜单入口已移除，右下角选择器承接子代理模型切换（数据动作全保留、不打断、下一次调用生效）；UC-5D13 表述更新（目录链路未改后端，选择器接线单列）。
- 2026-09-16 v3：**整体重写**——旧「子代理 Dock」面板（UC-5D1~5D5，浮层卡片形态）已随 dsh 式重建移除，本版按「可寻址会话」新实现重编 14 条 UC；文件更名为《04-子代理会话方案设计》。验证：44 条单元断言 + 浏览器 8/8（目录/寻址/返回/输入区）+ 4/4（四色状态点）+ 横向溢出归零。
- 2026-09-14 v2：修正子代理状态模块计数（9 个）并更新版本线至 `d022831`。
- 2026-09-13 v1：拆分首版（承接 UC-507 与 UC-1E2 的界面部分）。
