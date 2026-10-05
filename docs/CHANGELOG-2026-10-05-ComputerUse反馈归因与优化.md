# Computer Use 反馈归因与优化

分析范围：两份 2026-10-05 复盘、当前 MyAgent 实现、本机 DSH 源码，以及 Cua Driver `cua-driver-rs-v0.28.0` 源码（提交 `1b50c02e2d34734f64d2d22f54eb76cc97b4a663`）。当前 MyAgent 使用 `cua-driver==0.28.0`；DSH Native 也依赖该版本，DSH MCP 使用外部已安装的可执行程序，实际版本取决于配置。以下“DSH 也有”指相同驱动版本、权限和平台下的行为，不代表已重演两个原任务。

## 逐项结论

| 反馈 | 归因及 DSH 对照 | 本次处理 |
|---|---|---|
| 看得到 `[23]`，取不到 token/snapshot_id | 适配层丢信息。MyAgent 只投影 `content`；DSH 普通工具调用同样只投影 `content`，但在 canonical `value.structuredContent` 中保留原始数据供程序化调用。因此是共有投影缺口，加上迁移缺少原始结构保留。 | 两个 provider 都展示 snapshot_id、element_token、原始 index，并在 outcome metadata 保留结构化数据。过滤后不重新编号。 |
| Posted click 带 ✅，看起来成功但界面没变 | 投递能力/回执文案来自上游；投递不等于界面生效。驱动已返回 `verified:false`、`effect:unverifiable`，MyAgent 和 DSH 普通投影均没有展示。截图 hash 不变只能说明像素未变，不能普遍证明投递失败。 | 显示 DELIVERY ONLY 及原始验证状态；增加可选 `_verify`，按业务谓词区分 satisfied、unsatisfied、unknown，不把“图没变”直接当错误，也不重放输入。 |
| Chromium 后台 click 可用，key/scroll 被拒 | 上游 Windows 事件能力不同，DSH 使用同一驱动也会遇到。不是迁移缺了一套后台键盘实现。 | 保留 `background_unavailable`、事件类型/窗口类/建议，补充语义动作、已授权 CDP 和前台授权指引；禁止自动升级到前台。 |
| 坐标有约 13px 偏移 | 现有复盘不能唯一证明驱动用了错误矩形。该版窗口截图按 DWM frame 裁切，点击也从 DWM inset 起点映射，并使用实际截图原宽/返回宽缩放。`window_bounds` 是窗口枚举外框，不能用来反推截图比例；截图含非客户区时，全部按 ClientRect 换算也会错。MyAgent 的归一化和模型请求还可能再缩放，旧提示没有给出完整映射。 | 附件保留坐标空间与驱动原图尺寸；给模型明确的预览→驱动像素 x/y 比例，再由驱动映射屏幕，避免双重缩放。不硬编码减 13px、不改上游二进制。原任务偏移仍需隔离窗口复现。 |
| UIA 从 3 元素变 383，空 query 被误读为没有控件 | Chromium/Electron UIA 的激活/懒加载来自上游。Windows 驱动已有 `elements_complete:false`，部分空树还有 degraded/reason，原投影丢掉了这些字段。DSH 普通投影有相同风险。 | 展示完整性、计数、降级原因；提示稀疏/空树不能证明元素不存在。不会仅凭 3 个元素就武断标记“未激活”，不会自动置前激活。 |
| 前台窗口点击关闭 Radix 弹层/点到其他窗口，缺接收 HWND | 前台激活可关闭依赖焦点的弹层；窗口级输入路径缺少统一实际接收 HWND 诊断，是上游限制。DSH 没有额外修复这条 native 路径。 | 保留上游已有投递 path/诊断，明确置前/前台操作后重新观察。未伪造“接收 HWND”等于指定 window_id；接收 HWND 需改驱动并做专门路由测试。 |
| 缺动作后置条件闭环 | 驱动已有 `verify_state`，MyAgent/DSH 都主要依靠模型另调验证。 | 窗口动作新增可选 `_verify`，一次输入后检查同一 pid/window/session；默认不返回图片、等 1 秒。只有稳定 satisfied 才完成；其余为失败。调用串行，其他 Agent 调用不会插在动作与验证之间。 |
| start_session(命名) 后 list_apps 仍说 ended | 上游命名会话和 transport 隐式会话分开；list_apps/list_windows 没有 session 参数，DSH 也遵守该 schema。 | 错误明确写出需要不带标签的 `start_session({})`；命名会话提示重启同标签。没有向不支持 session 的工具注入参数，也没有静默复活会话或重试输入。 |
| CDP consent_required，不知怎么开启 | 上游标准权限模式对已有登录态的边界，DSH 默认配置也不会自动批准。 | MCP 设置增加默认关闭的显式授权开关，启动参数追加 `--grant existing-profile`；错误给出操作路径。审批开关启用时验证实际参数摘要，不能拿旧配置审批覆盖新授权。 |
| 45k 树被截断，每一步截图成本高 | 大树和全量图片来自上游默认观察；两边都有结果预算限制。仅从复盘不能保证未来任务调用减少到 4 次。 | 去掉与结构化元素重复的无 token markdown；关键状态位于大输出前面。提示 query/树-only/图-only；验证默认不带图。超大结构仍按现有机制完整落盘，未永久删掉尾部控件。 |
| 打包 Electron 没有 CDP 端口 | 环境事实；已有 profile 授权也不能凭空生成端口。DSH 同样需要可访问的端点。 | 在设置和错误提示中明确这一条件，不把开启授权等同于接通浏览器。 |
| 用户/多个 Agent 共享桌面，快照过期 | 两边都不能锁住用户的真实桌面。命名 session 不是桌面隔离。 | provider 内部调用串行并支持取消，排队后再次检查权限模式；动作+验证不被另一个 provider 调用插入。用户手动操作仍可能改变状态，须重新观察。 |

## 实现与用法

继续使用原有 Native/MCP 互斥 provider、同一 57 个上游工具和中央审批，未升级驱动版本、未引入另一个桌面执行通道。窗口输入 schema 增加可选 `_verify`，在送给上游前剥离。

```json
{
  "pid": 123,
  "window_id": 456,
  "element_token": "<本次快照的 token>",
  "_verify": {
    "expect": [{"element": {"selector": {"label_contains": "Logs"}, "exists": true}}],
    "timeout_ms": 1000,
    "include_screenshot": false
  }
}
```

验证要求选择能说明目标状态的谓词；“窗口存在”或已经存在的按钮只能证明该谓词，不能证明点击达成了整个任务。`element.exists:false` 无法由部分树证明，仍按驱动 schema 拒绝。需要视觉判断时，另取 image-only 截图并让模型核验。

失败码 `postcondition_unsatisfied` / `postcondition_unknown` 表示动作之后的条件没有得到证明，**不是输入已回滚**。观察报错也保留投递回执。输入拒绝后不执行后置检查，取消不重放，桌面级动作需另调验证。

已登录浏览器开关位于执行面板 → Computer Use → MCP。当前用户配置没有自动开启该开关；需要用户在界面明确勾选并保存。已有 MCP 配置中的授权参数仍然有效。若启用了 MCP 注册审批，须先将 `--grant existing-profile` 加到服务器配置 args 并批准精确配置，再保存 Computer Use。连接已有共享 daemon 时，启动参数不能修改那个 daemon 的权限。

## 源码证据

- MyAgent 旧 `format_call_tool_result` 只读取 content；新投影位于 `app/execution_services/computer_results.py`，provider 与 `_verify` 位于 `app/execution_services/computer.py`。
- DSH `packages/mcp/mcp-client/src/tools.ts` 的 `createOutput.render` / `prepareImageProjection` 从 content 取文本；`createExecutor` 保留 structuredContent；Native provider 复用 `createMcpToolDefinition`。这解释了普通调用与程序化读取的差异。
- Cua [Windows get_window_state / click 实现](https://github.com/trycua/cua/blob/cua-driver-rs-v0.28.0/libs/cua-driver/rust/crates/platform-windows/src/tools/impl_.rs)：`build_element_entry`、snapshot registry、elements_complete、实际截图 resize ratio、`bitmap_to_screen` 和未验证回执。
- Cua [Windows capture](https://github.com/trycua/cua/blob/cua-driver-rs-v0.28.0/libs/cua-driver/rust/crates/platform-windows/src/capture.rs)：PrintWindow 的全窗口 buffer、DWM frame 裁切和 inset。
- Cua [动作支持矩阵](https://github.com/trycua/cua/blob/cua-driver-rs-v0.28.0/libs/cua-driver/docs/action-support.md)：不同 Windows 输入类型支持不同，保留无法证明效果的能力缺口。
- Cua [verify_state 实现](https://github.com/trycua/cua/blob/cua-driver-rs-v0.28.0/libs/cua-driver/rust/crates/cua-driver-core/src/expectation.rs)：稳定采样与三态结果，不穷尽的元素树不能证明缺席。
- Cua [授权与 runtime 所有权说明](https://github.com/trycua/cua/blob/cua-driver-rs-v0.28.0/libs/cua-driver/README.md)：existing-profile 是显式 grant；MCP/SDK 使用同一个驱动能力，不是另外一套通用后台输入实现。

## 验证边界

以模拟桌面结果验证两种 provider 的寻址投影、后置条件、输入不重放、串行及取消、截图双重缩放、配置审批摘要、API Origin/类型校验和设置恢复；以隔离的 headless 页面验证 UI 开关。真实 Native SDK 只进行工具目录发现和 shutdown，不发送桌面输入。没有重演用户日常 Edge/OpenCode/Electron 任务，因此不宣称原任务的 13px 偏移、弹层关闭或后台静默丢事件已经在真实应用中消失。

检查结果：主回归 **206 passed, 2 skipped**（Computer Use、MCP、中央安全、执行集成、附件、隔离前端）；最后一次截图/投影补充回归 **60 passed**；真实 Native SDK 目录/关闭 smoke **1 passed**；前端 dist 同步检查和 `git diff --check` 通过。上述测试组有重叠，数量不直接相加。

确认 399 个会话均无运行 Agent、后台 job 或终端后，通过现有托盘机制重载空闲服务。更新后的 `/api/computer-use` 已返回 `provider:mcp`、`state:ready`、`tool_count:57`、`allow_existing_profile:false`，现有浏览器授权偏好没有被自动提升。
