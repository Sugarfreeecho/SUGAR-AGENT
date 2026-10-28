# Goal / Agent Team 运行链路检查与控制台补齐

日期：2026-10-27。范围：当前工作树中的 `agent-goal`、`agent-team`、宿主状态服务、调度和插件独立页面。结论基于本地源码与隔离测试；未重启用户正在运行的应用，未调用真实模型服务。

## 交付结果

两个入口仍为 `/plugins/agent-goal`、`/plugins/agent-team`，也可从会话右侧详情栏打开。嵌入页面跟随当前会话，独立页面支持最近会话建议、手动 ID 和 `?session=<id>`。

| 控制台 | 已补齐的操作与信息 |
| --- | --- |
| Goal | 创建目标、可选总预算、完整目标文本、编辑、暂停、恢复、追加预算、取消、删除；已用/剩余 Token、续跑次数、运行时间、错误和重试原因；独立 Judge 结论/诊断；人工验收、保存审核、带反馈重开 |
| Agent Team | 创建团队；创建真实持久成员、选择模型配置和只读模式、后台派发、打开成员会话、中断、恢复、移除；任务创建/编辑、优先级、依赖、状态、结果、释放、搜索/筛选/分页；消息发送、收件箱筛选、逐收件人状态和 Lead 已读；手动调度、请求关停、完成关停、归档 |
| 公共交互 | 5 秒串行刷新；隐藏或卸载时停止轮询；15 秒普通请求超时、60 秒成员操作等待；操作防重入、旧响应隔离、错误保留、弹窗内错误与处理中提示、审核草稿保护、窄屏和宿主主题适配 |

控制台没有把 JSON 当主界面，完整状态保留在折叠区，便于排查。

## 运行架构

Goal 的事实由 `app/agent_goal.py` 管理。模型的完成请求进入插件 `runtime.py` 的独立 Judge；Judge 通过后进入人工审核。`runner.py` 在目标 active、无执行租约、预算充足、重试到期、没有人工等待且未手动停止时，经 `session_control` 提交续跑。页面只执行用户控制动作，不再创建另一套浏览器续跑循环。

Team 的事实由 `AgentTeamService` 写入 Runtime V2 的插件扩展状态，成员执行复用 `run_subagent_task`。自动调度按优先级认领依赖满足的 pending 任务，成员运行后回收状态。新增 HTTP `/api/agent-team/{session_id}/control` 复用这套执行能力，并将页面派发固定为后台运行；原来只添加 roster 行的 `/members` 接口不作为控制台“创建成员”的实现。

## 已发现并处理的问题

| 优先级 | 原问题 / 触发条件 | 修复与验证 |
| --- | --- | --- |
| P1 | Team 宿主工具传入 `parent_runtime_config`，dispatcher 不接收，真实工具调用会 TypeError | 补齐参数并沿派发和连续调度透传，回归覆盖宿主调用形状 |
| P1 | 成员等待共享写锁时取消，旧实现仍等待线程里的阻塞 acquire，持锁者不退出则取消也不结束 | 改成非阻塞 acquire + 可取消异步等待；验证持锁者不释放时等待者仍及时取消 |
| P1 | 后台成员被取消会抛 CancelledError，绕开 Exception 回收，roster 长期停在 working | 屏蔽监视者取消对 child 的传播；区分 child 已终止，正常回收；显式中断保留 stopping/stopped，避免立刻被自动调度重新唤醒 |
| P1 | Team 页面没有完成关停入口，只能请求关停，归档一直冲突 | 补齐三步流程；后端拒绝仍有工作成员时假完成；无实际执行的遗留 working 状态可显式停止后完成关停 |
| P2 | Goal 页面审核只发送 feedback，但服务必填 objective | 审核表单发送目标、反馈和预算；浏览器覆盖保存、重开与批准移除 |
| P2 | Goal blocked 没有用户恢复路径；恢复后可能遗留手动停止标记 | 允许用户恢复 blocked，重置阻塞计数；显式创建/恢复时清除 interrupt，继续走原协调器 |
| P2 | 同一成员可被并发派发，或把别人的任务交给另一成员执行 | 成员 working 转换带原子 expected_states；派发前校验任务归属和终态；空指令校验先于任务认领 |
| P2 | 任务转回 pending 后保留 assignee，后续自动认领永远跳过；blocked 任务不能释放 | pending 清理 assignee；允许释放已认领的 blocked 任务 |
| P2 | 增加任务依赖编辑后可能产生环或覆盖模型刚提交的任务结果 | 同一事实事务内校验 DAG；页面传 expected_seq，陈旧任务保存返回冲突 |
| P2 | 消息只有 queued，而 consume 只允许 delivered 后调用；缺少自动投递器时收件人无法确认已读 | 显式消费允许直接确认 queued/delivering/failed 邮件，仍校验收件人，禁止 consumed 倒退 |
| P2 | Goal GET 和控制动作在 ASGI 循环执行同步存储；Team 读取复制整份会话投影 | Goal 读写移出事件循环，写入复用 run_fact_commit；Team 只复制扩展状态，不复制对话历史 |
| P2 | 页面没有超时、防连点、切换隔离；后台刷新可能覆盖审核草稿 | 两页使用公共 Console 生命周期；测试覆盖旧请求、双击、超时、嵌入绑定、隐藏停止、弹窗内服务错误 |
| P2 | 目标已被替换时，旧窗口动作可能修改新目标 | 用户动作可带 expected_goal_id，并在 Goal 原子 mutation 内校验 |
| P2 | Team 工具 schema 未声明 dispatcher 使用的 state 参数 | 补齐 state 枚举，保留 task status 的独立语义 |

主要源码：`app/agent_goal.py`、`app/agent_team/{api,service,store,tools,policy}.py`、`plugins/{agent-goal,agent-team}/host.py`、两插件的 `web/`、`app/templates/static/workflow-console.{js,css}`。

## DSH 对照

读取了本地 `D:/AI/AI Agent/OpenAgent/Deepseek Harness/deepseek-harness`，修订 `477b4f4205`。这里对照的是该检出的实现，不宣称是上游最新行为。

| DSH 的设计 | 本项目采用 / 保留的做法 |
| --- | --- |
| Goal 服务保存事实，独立 round driver 决定续行；恢复后 armed/disarmed 与持久 phase 分开 | 继续保留 GoalManager / 插件 runtime / runner / session_control 分工；页面不承担续跑。MyAgent 原有跨重启自动续跑语义不在此次修改 |
| `{id, revision}` 拒绝陈旧 Goal 操作，UI pendingRef 防同帧重复提交 | Goal 用户动作增加身份检查；Team 编辑增加 seq 检查；页面同步设置 busy 并隔离旧请求。Goal 的同一目标多窗口编辑仍未扩展为完整 revision CAS |
| Team roster 持久身份和实际运行状态分离；任务显示 owner、readiness、blockedBy | 展示持久 child 会话、成员状态、负责人、可调度和依赖状态；提供实际成员创建/派发/停止入口 |
| Task 更新维护 DAG 与 compare-and-set | 对可编辑依赖加入环检查，并用 seq 防覆盖 |
| 消息持久 queued-minus-delivered，目标按消息身份去重，Steer 或冷恢复唤醒 | 保留本项目持久邮箱并修复消费路径；控制台清楚区分“发消息”和“派发执行”，未把 UI 发信改成隐式自动唤醒 |
| GoalBar 保留编辑 draft、pending、错误；TeamAction 可打开成员和查看展开任务 | 审核 draft 不随轮询重置；弹窗内可见错误；成员会话链接、任务结果展开、分页与状态过滤 |

本地对照文件：

- `docs/subsystems/{goal,agent-team}.zh.md`
- `packages/goal/goal/README.zh.md`
- `packages/client/ui-goal/src/client/GoalBar.tsx`
- `packages/experimental/client-ui-agent-team/src/client/TeamAction.tsx`

## 使用时仍需理解的等待条件

- **普通 Team 消息不会自动唤醒空闲成员或 Lead。** 发消息表示写邮箱；需要立即执行请派发。若后续迁移 DSH 的自动消息投递，需要一起实现持久投递确认、幂等和冷恢复，不能只在发信后追加一次盲目 resume。
- **等待人工输入/审批会阻止续跑。** 这是运行时的正常门禁；控制台可打开成员会话处理，不通过“恢复”跳过用户审批。
- **共享工作区写操作仍串行。** 无法创建隔离 worktree 时，多成员的写入可能互相等待；此次修复确保等待可取消，没有取消写锁保护。
- **Team 调度仍按根团队逐个扫描。** 单个成员启动慢会拖延该轮扫描；下一阶段可把每根团队调度改成独立、有期限的 worker。页面的 60 秒超时只是等待上限，不代表已经撤销后端接受的操作，因此超时后提示先刷新。
- **Judge 仍使用模型 transport 的超时/重试。** 此次没有替换模型网络策略，独立 Judge 的长请求仍可能占用当前运行。控制台显示请求状态与诊断，不能把页面刷新当作终止模型。

## 验证与生效

新增 `tests/test_workflow_console_regressions.py` 与 `tests/test_workflow_consoles_browser.py`。浏览器加载真实生产 HTML/JS/CSS、调用真实插件 API 和临时 Runtime V2 状态；子模型执行使用测试替身，防止消耗用户模型额度。覆盖完整 Goal 操作、真实成员创建接线、任务依赖编辑和后台派发、邮箱、关停归档、旧请求、超时、防重入、嵌入生命周期以及 390px 布局。

首轮控制台截图位于 `.analysis/workflow-consoles/{goal-console,team-console,team-console-mobile}.png`。首轮未修改主前端 bundle 源码；后续左侧页签迁移已更新主 bundle，见下节。

最终组合验证：**167 项测试通过**。包括 Goal、Team、Runtime V2 团队投影、插件 UI/路由热重载/Web Gateway、目标侧栏与审核徽标，以及新增控制台回归和真实浏览器流程。Python 编译、三个 JavaScript 模块语法、`check_frontend_dist_sync.py` 和 `git diff --check` 均通过。浏览器测试中的模型执行使用替身，未进行真实模型请求联测。

涉及 `app/agent_goal.py` 与 `app/agent_team/` 的宿主改动，安装此次代码后需要重启后端。仅插件热重载不足以更新已导入的宿主模块。

## 后续：左侧插件占位页签迁移

已移除工作区左侧 `execution`（执行）与 `plugins`（插件）页签，并阻止旧注册调用重新建立它们。显式的计划、目标、改动页签继续保留。

- `execution-tools` 提供正式的详情栏控制台与独立页面，复用原后台任务、输出、终端、Computer Use 设计。xterm 与本地样式构建为独立入口，iframe 内的终端菜单、复制/粘贴、SSE 暂停和原 offset 重连都在页面自身管理。
- 默认插件分组的状态卡片进入各自详情页的「会话状态」区，包括 Team 与 Game Arena。没有独立页面的 UI 插件获得通用控制台，兼容同时声明嵌入设置页的情况。
- 左侧与各个插件控制台分别持有渲染状态和 cleanup，复用同一字段、动作、专用渲染器。关闭/隐藏详情页清理其资源；保留每个会话的页面绑定，不影响其他页或左侧目标、计划。
- 新增真实浏览器迁移测试，覆盖两种页面 scope、通用页、状态动作、会话切换、隐藏与关闭；执行控制台测试加载生产构建的终端资源，但后端任务/终端操作使用隔离替身。

此次包含主前端改动，已重新构建 `app/templates/dist`。更新代码后重新加载主界面，再从详情栏「插件」打开控制台。

2026-10-28 迁移验证结果：**127 项组合回归通过**，终端相关 **3 项定向复测通过**；生产前端构建、dist 同步、JavaScript 语法及本次修改的 diff 检查通过。覆盖左侧页签移除、详情页动作与状态、app/session 两种 scope、侧栏中尚未出现的会话、UI-only 插件、终端输入与菜单、隐藏续接和页面释放。执行控制台截图为 `.analysis/workflow-consoles/execution-console.png`。

## 2026-10-28：实机资源遗漏修复与控制台视觉交付

用户反馈界面仍简陋后，检查了正在运行的 localhost:8192 和实际 Edge 详情栏。发现 `/static/workflow-console.css`、`/static/workflow-console.js`、`/static/plugin-page-bridge.js` 返回 404：样式、控制逻辑、会话绑定无法加载。之前的浏览器测试直接供应本地资源，未验证生产路由是否注册，因此前面的测试结果不能证明实机资源链路可用。插件自己的资源还采用固定地址加一小时缓存，可能继续显示旧文件。

修复包含：

- `app/plugin_page_assets.py` 为四个公共页面资源注册精确白名单路由，设置正确 MIME、`nosniff`、`Cache-Control: no-cache`。宿主启动和 Goal / Team 热安装都可注册；重复安装不累积路由，也能替换旧的插件资源缓存路由。
- Goal 与 Team 的资源使用统一版本参数；插件资产继续由既有 Web Gateway 校验路径，缓存改为要求重新验证。
- Goal 增加品牌标题、绑定会话栏、指标卡片、四阶段进度、目标概览、独立 Judge、诊断与人工验收分区；Team 增加团队概览、指标、任务/成员/消息/运行信息页签、任务状态分栏、成员头像与职责卡片。保留已有操作、超时、草稿与生命周期处理。
- 无数据时提供创建引导与真实表单，宽屏并排、窄屏收紧留白；嵌入页面显示会话名称，自动隐藏手工 ID 表单。

本轮界面和资源修复已通过同值插件重载应用到当前运行服务，未重启后端，也未终止正在运行的用户会话。实机确认公共资源全部返回 200，Goal 独立页和 Team 详情栏显示新版样式，Team 自动绑定当前会话并继承深色主题。

本轮验证：**54 项通过**，包含 10 项控制台浏览器测试、实际宿主静态资源测试、路由热重载、Web Gateway、执行控制台、详情页迁移与详情栏页面回归。Python 编译、JavaScript 语法与定向 diff 检查通过。新增资源测试直接读取宿主 ASGI 路由；浏览器资源也经过真实路由，不再直接读取文件供应给浏览器。模型派发继续使用隔离替身，未向用户实际会话写入演示目标或团队。

截图位于 `.analysis/workflow-consoles/`：

- `goal-console-live.png`、`team-console-live-details.png`：当前运行服务实拍，无演示数据。
- `goal-console.png`、`team-console.png`、`team-console-members.png`、`team-console-mobile.png`：隔离测试数据的完整状态。
- `agent-goal-empty.png`、`agent-team-empty.png`：隔离的深色嵌入空状态与创建表单。

## 2026-10-28：与「刷B站」统一外观

按用户指定，以 `plugins/sugar-bili-scroll/web/index.html` 的现有界面为参考，统一 Goal / Team 的字体、字号、固定顶栏、黑色主按钮、次要按钮、12px 卡片圆角与 16px 内边距、紧凑指标格、彩色状态胶囊和下划线页签。空状态改为简洁说明卡片与创建表单。样式限定在 `body[data-console]`，执行控制台继续使用自身布局；「刷B站」源码未改动，Goal / Team 的接口与操作流程未改动。

已通过当前 localhost:8192 的 Edge 页面核对实际字体栈、顶栏间距、卡片和主按钮样式。Goal / Team 的生产资源版本参数已同步更新，无需重启后端。18 项控制台、执行页与资源路由回归通过；最后的字号和表单字重调整经 3 项视觉/嵌入定向用例复核通过。

新截图使用 `*-bili.png` 后缀，保留上一轮截图以供对照；当前服务的实际空状态截图为 `goal-console-bili-live.png` 与 `team-console-bili-live.png`。完整状态示例仍来自隔离测试数据。
