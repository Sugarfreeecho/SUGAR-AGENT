# CUA 全量测试会话复核与优化

> 后续真机复测补充：录制 getter 陈旧值与 UIA/截图矛盾已定位到宿主读取提前执行的顺序问题；空窗口合同还涉及重启后的图像缓存丢失。不能把这些现象直接归结为驱动错误或代码未加载。后续修复见 [CUA 录制与 SIGINT 复测修复](CHANGELOG-2026-10-05-CUA录制与SIGINT复测修复.md)。本文件其余内容保留前一轮的证据和判断时间范围。

日期：2026-10-05（Asia/Shanghai）。复核会话：`c5caf529-3324-4c1e-a975-2b3c06f27a58`。

证据来自本地服务的完整 history_snapshot / execution_records、原始结构化回执、`workspace/cua_fulltest_20261005/rec*`、MyAgent 当前适配代码、DSH 本地两个 Cua provider，以及 Cua 0.28.0 源码。没有重演会修改用户桌面的完整测试。

## 先修正测试报告的结论

| 原结论 | 原始证据支持的结论 |
|---|---|
| 约 60 次调用、75 分钟 | 本轮 turn 3827 有 121 次工具调用，其中 CUA 114 次、45 种工具。首次至末次调用开始时间为北京时间 09:43:20.874–10:06:44.383，跨度 23 分 23.509 秒；这不是每条工具耗时的总和，也不证明覆盖全部 57 种工具。 |
| 独立验证与内联验证使用同一选择器却矛盾 | 独立验证找“显示为 0”；成功内联验证找 Text“16”，时间和状态也不同。没有同状态、同选择器的对照证据。两种调用均使用同一个 driver verify_state。部分树中未找到元素应当 unknown，不能强行改成 satisfied。 |
| 7+9=16 全链路验证通过 | 这是计算器的算式结果。实际 `_verify` 共 3 次：检查 16 成功；检查 55、558 均返回 postcondition_unknown，宿主已经标记 failed。没有十六次完整验证。 |
| double_click 假成功 | 裸投递文案有误导性；但本轮带 `_verify` 的 double_click 已按验证不明失败，不能说适配层把这个组合操作判为成功。right_click 的裸回执仍属于未验证投递。 |
| set_window_frame 系统夹 3px 被判失败 | 记录显示请求 800×1000、实际约 800×1003，并有 unverifiable 回执。需要区分精确尺寸未证明与完全未生效，不宜扩大几何判定容差后直接宣称成功。 |
| browser_* 每个动作都失败 | owned Edge 的 get_browser_state 绑定三次失败，后续动作面未能测试；不能逐个登记为已执行失败。 |
| get_agent_cursor_state 两种模式都不可用 | 本轮使用 MCP，position:null 触发公布的输出 schema 失败。本次 Native SDK 只读探针返回正常数据；是否报错取决于调用链对该 schema 的执行方式。 |
| scroll 的截图相同证明整个工具不可用 | 只证明该场景未观察到画面变化，尚需排除滚动边界、目标和状态等因素。 |
| 隔离 Edge 是干净匿名环境 | 独立 profile/process 不等于匿名身份。报告中自动登录/收藏夹现象有风险意义；不能仅凭该现象断言驱动复制了原用户 profile，回执的 copied_existing_profile 为 false。 |

原报告作为历史记录保留，并添加复核提示；不覆盖截图、视频或原始回执。剪贴板只恢复了文本，原 HTML/Chromium 类型没有恢复，本次没有再次写剪贴板。

## 问题归属

DSH 锁定 `@trycua/cua-driver@0.28.0`。其 Native provider 直接传入 args 调用 SDK，MCP provider 交给同一驱动的 stdio MCP；没有找到在这两个 provider 中固定截图空间或校正录制坐标的实现。

| 问题 | 归属与判断 |
|---|---|
| 截图缩放改变后续像素解释 | Cua Windows 0.28.0 的 ResizeRegistry 按 PID 保存最近截图比例，get_window_state.max_dimension 会改写；replay 使用原 arguments，不包含当时截图空间。DSH 直通同一驱动也会面临此机制，但没有在 DSH 桌面重演。MyAgent 之前仅注释附件缩放，未消除驱动可变空间，这部分宿主适配需要改进。 |
| 光标 null 的 schema 错误 | 上游结构契约缺陷。0.28.0 success/refusal anyOf 中 position 被声明为非 null object；合法的未知位置是 null。不能绕过整个 schema。 |
| 录制 getter 报 disabled | 本轮 start/get/stop 都经同一 MCP 入口，不能解释成 CLI/MCP 混用。与成功 start、turn 目录和 stop 的视频路径确实冲突。根因还不能从现有证据完全证明，宿主应保留不确定性。 |
| XAML 输入丢失、快捷键拒绝、Electron 菜单模式缺失 | 主要是驱动/应用能力限制；“成功文案”和遗漏 isError 是宿主可以改善的结果解释。不能默默切前台或扩大输入范围。 |
| foreign_process_termination_denied | 正确的进程所有权拒绝，不能因间接派生就默认绕过；使用拥有的终端资源管理或显式 UI exit。 |
| 浏览器 CDP 窗口绑定失败 | 驱动路由证明问题，当前记录不能证明宿主迁移造成。isolated_new 的身份状态需要单独观察。 |

源码：[Windows 截图/输入及 ResizeRegistry](https://github.com/trycua/cua/blob/cua-driver-rs-v0.28.0/libs/cua-driver/rust/crates/platform-windows/src/tools/impl_.rs)、[录制/回放实现](https://github.com/trycua/cua/blob/cua-driver-rs-v0.28.0/libs/cua-driver/rust/crates/cua-driver-core/src/recording_tools.rs)、[验证实现](https://github.com/trycua/cua/blob/cua-driver-rs-v0.28.0/libs/cua-driver/rust/crates/cua-driver-core/src/expectation.rs)。

## 本次实现

1. **固定截图参考空间。** get_window_state 不再把 max_dimension 传给驱动；驱动按配置默认尺寸捕获，小预览由宿主缩放。structuredContent.coordinate_mapping 和附件 source.coordinateMapping 保留 driver/preview 尺寸，模型请求二次缩图仍直接换算到驱动像素。没有改成客户区像素，没有按 DPI 重复缩放。截图到屏幕的最后一步仍由驱动执行。
2. **拦截不可靠回放。** 新录制写 MyAgent 坐标合同；回放前核对配置、精确窗口图像/物理尺寸，拒绝旧录制、过期 token/index/zoom、桌面像素轨迹、同 PID 多窗口及轨迹内几何/配置变化。缺少依据时不发输入。原 rec、rec2 不被自动补造合同。成功计数仍明确标注为投递计数。
3. **严格光标兼容。** 只修复 position:null 的 tool_output_invalid；保留 success/refusal 联合结构，完整校验修正后的 schema。其他字段仍非法则原样失败。保留原错误证据，不重放读调用。
4. **诚实解释结果。** nested refusal 统一为失败；键盘/文本 delivery_failed 且没有成功后置验证时为 input_delivery_unconfirmed。裸点击、双击、右击、滚动的 unverifiable 原生文案加未验证标记，去掉成功图标。已成功的后置条件不再同时提示“仅投递”，但只能证明其指定谓词。
5. **录制状态冲突。** 当前连接最后一次成功 start 与实时 disabled 冲突时返回 recording_state_conflict、状态 unknown，保留双方证据；不把缓存伪装成活跃状态。另一个 Agent 不能在同一宿主连接上停掉已有录制。独立驱动客户端和重启后的所有权不能靠本地缓存证明。
6. **界面管理入口。** 普通 MCP 使用逐工具开关；Computer Use 工具由独占 provider 统一管理，显示启用状态。MCP 设置页新增明确说明，开关和 Native/MCP 切换在聊天页“执行 → Computer Use”。没有添加能绕过 provider 管理的第二条工具开关路径。

## 保留的边界

固定预览消除了本轮 per-call max_dimension 引起的漂移，不保证其他客户端、窗口调整、用户移动界面后旧坐标仍有效。驱动 PID 级登记仍存在，所以观察另一个同 PID 窗口后需要刷新当前目标。原生录制证据图可能是原始窗口尺寸，不能当作工具截图空间。

get_recording_state 的底层实时状态错误、XAML hotkey/后台键鼠能力、Electron 原生菜单和浏览器绑定没有被宿主兼容层彻底修复。UIA 的部分证据保持 unknown；截图用于补充观察，也不是任何任务状态的自动成功证明。

继续保留 0.28.0，与 DSH 锁定版本一致。上游 [0.33.0 发布说明](https://github.com/trycua/cua/releases/tag/cua-driver-rs-v0.33.0)列有 Windows Chromium DIP 坐标和窗口匹配修复；[0.33.2 输出契约源码](https://github.com/trycua/cua/blob/cua-driver-rs-v0.33.2/libs/cua-driver/rust/crates/cua-driver-contract/src/outputs.rs)包含 nullable_cursor_point_schema。已对照源码和下载候选 wheel，但没有安装、自动升级或宣称新版本解决所有问题。

## 验证

- Python 主回归：**233 passed, 2 skipped**，涵盖新坐标/证据测试、Native/MCP provider、附件、MCP、中央安全、执行集成、工具状态和前端契约。
- 隔离 headless 设置页：**50 passed**，覆盖已管理 provider 的目录展示及其他设置行为。
- 真实 Native SDK 仅做目录、光标只读数据和 shutdown；没有发键鼠输入。其公布 schema 对 position:null 的原始校验失败与 MCP 历史回执一致；纯本地兼容函数使用该公布 schema 和本轮历史回执，恢复合法数据成功。
- 新回归检查预览尺寸变化不改变驱动点击点、附件多次缩放、联合 schema 严格校验、录制冲突/所有权、权限在预检后变化、旧/变更回放拒绝。测试使用模拟桌面，不据此宣称计算器、Terminal、Edge 的全部真实动作已经修复。

空闲重载前后核对 400 个会话：运行 Agent 为 0，运行 job/终端为 0，无查询错误；通过现有托盘重载服务，监听进程从此前 PID 18388 更新为 PID 4132。

重载后的实际 HTTP 检查：`provider:mcp`、`state:ready`、`tool_count:57`；MCP 目录中 57 个工具均由 Computer Use 管理，9 个窗口动作保留 `_verify`，固定预览和回放合同说明已发布。`allow_existing_profile:false`，未提升浏览器授权。设置页脚本与工作区文件 SHA256 一致，新增管理入口说明已随服务发布；已经打开的设置页刷新后显示。
