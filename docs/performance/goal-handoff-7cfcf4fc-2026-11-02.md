# Goal 两轮交接的等待分析与修正

分析日期：2026-11-02。会话：`7cfcf4fc-a567-4124-8db9-0e04d2602be3`。

## 结论与测量口径

等待来自答案提交后的收尾、Goal 再次调度、控制队列派发及新轮请求准备，不能都算成模型响应慢。最终答案已经提交，也不代表运行已释放、下一轮能马上进入。

只读分析了会话事件事实、execution_metrics、runtime_observability、session-control SQLite 操作记录及按 run_id 匹配的本地计时日志。没有恢复用户手动停止的目标、修改会话状态或发起额外模型请求。

最近保留的记录中，86 次相邻、上轮成功且下轮由 agent-goal 发起的交接，**上轮指标结束 → 下轮指标开始**的中位数为 **20.096 秒**，P95 **41.067 秒**，最大 **95.783 秒**。这个口径不含最终答案提交后、指标结束前的收尾，也不含下轮请求准备和模型响应。中断轮仍保留在相邻序列中；未跨过中断拼接成虚假的长交接。超过 300 秒的间隔会标记复核并排除汇总。

事件时间是后端提交时间，不是浏览器实际绘制时间。请求指标 started_at 是创建指标行的时间，不能当作精确 HTTP send。缺失的阶段计时留空，不用 0 代替。

## 一个慢样本的完整交接

上轮 `control-55056b3d-947e-4108-b9c8-4badaf57c0be` → 下轮 `control-8a81cbbb-4a24-4b75-90a7-72f8597512dc`。表内时间均为北京时间，2026-11-02。

| 时间 | 锚点 | 与上个锚点间隔 |
|---|---|---:|
| 08:41:28.096 | assistant_final_committed：最终答案提交 | — |
| 08:42:19.411 | run_finished：运行终态事实提交 | 51.315 秒 |
| 08:42:23.665 | 本轮执行指标结束 | 4.254 秒 |
| 08:42:27.709 | control 操作最终更新时间 | 4.044 秒 |
| 08:43:15.004 | 下一次 continue 获接收、进入持久队列 | 47.295 秒 |
| 08:43:40.662 | 下一轮执行指标开始 | 25.658 秒 |
| 08:43:53.818 | 第一条模型请求的指标行创建 | 13.156 秒 |

**最终答案提交 → 下一轮运行开始为 132.566 秒。** 若从较晚的 observability finished_at 起算，只得到 73.184 秒，会漏掉用户感知中的前半段。到新轮请求指标点又增加了 13.156 秒；API 计时中的首增量另约 3.033 秒，二者不是浏览器首字的精确时间戳。

相邻两个交接的「最终答案提交 → 下一轮运行开始」分别为 24.809 秒和 67.694 秒，说明不是固定的轮间休眠。Goal 默认轮询周期为 2 秒，控制维护周期为 0.5 秒，完成事件还会唤醒检查；这些配置本身解释不了几十秒等待。

## 时间花在哪里

### 1. 答案已经出现，收尾仍在执行

慢样本的 final_pipeline_timing 只有 2.843 秒，它只覆盖 final 附近的流水线，不能代表完整收尾。日志显示其结束后，到 SessionEnd 准备前仍有约 38 秒未细分的间隔，处于 queued-turn 检查与子代理结果落点处理路径。旧代码无这两步的独立计时，无法把这 38 秒全部归给某个函数。

代码确认：anchor_pending_subagent_results_for_run 原来先读取完整 UI 历史，再读取待交付结果；日志随后显示待交付结果为 **0 条**。长会话即使没有任何结果需要落点，也每轮重复做完整历史读取。已将判定顺序调整为先读待交付结果，无属于本 run 的未定位结果就直接返回。

慢样本 run_finalize 整体为 19.115 秒，其中 workflow_accounting 两个锚点之间约 10.217 秒，terminal_commit 3.532 秒，terminal_attention 0.937 秒，metrics_finish 3.851 秒。整体跨过了 run_finished 事实提交，不能把它再加到前表的 51.315 秒上。这里还包含状态存储、UI 投影、用量与指标等本地操作；现有证据不支持归因于 Judge 调用，本次目标没有待验收请求。

新增 queued_turn_handoff 与 post_final_handoff 慢计时，后者细分 anchor_pending_subagent_results、session_end_hook。后续可以确认剩余收尾等待，而不是只看 final_pipeline。

### 2. 已知 Goal 被全量会话发现挡住

原 Goal tick 在每分钟全量发现到期时，先读取包含归档会话的 inventory，再逐个 discover，之后才提交已知活跃 Goal 的续跑。一次长运行结束后通常已经超过扫描周期，容易碰上该路径。

本样本能精确界定 **control 上轮完成 → 新操作接收为 47.295 秒**；旧日志缺少 scheduler 子阶段，无法证明其中每一秒都在 inventory。这个阻塞顺序由代码与受控测试确认，已改为先检查并提交已知活跃 Goal，之后再做恢复用的全量发现。没有缩短轮询周期来增加空转。

新增 goal_scheduler 慢计时，细分 known_discovery、full_inventory、cold_discovery、admit_continuation，记录 first_admission 锚点。

### 3. 操作已入队，还在等维护与执行准备

原 control tick 先做规则调度、跨会话事件桥接、通知与 followup 发现，最后才派发 pending 队列。新接收操作没有独立唤醒派发，可能等待整批维护完成。大事件积压时，去重桥每次推进 500 条，原派发还会退回再等一个维护周期。

已增加一个合并唤醒的共享派发任务：操作获接收、worker 释放时直接检查持久队列；周期 tick 也在维护前检查一次。500 条去重批次有进展时继续推进，不再等下一次维护。授权、人工交互、停止标记、预算/Goal 生命周期、持久 receipt、执行租约和并发预算仍经过原检查。

即时派发与维护共用派发锁；事件桥对同一会话的游标也增加有界锁，防止两条消费路径并发覆盖游标。没有增加每个 Goal 独立 worker 池。

新增 control_dispatch 阶段计时：authorize、load_metadata、pending_human、durable_event_bridge、validate_bindings、reserve_run；control_run_prepare 细分 history_tail、clear_interrupt、source_before_run。

本次样本 **接收 → 下轮指标开始为 25.658 秒**，同时包含派发等待和进入 agent_loop 前的准备。旧日志不能继续准确拆分这 25.658 秒，新计时用于补齐这个缺口。

### 4. 新轮已经开始，工具目录与 Token 估算还没准备完

慢样本第一条请求 pre_api 共 9.881 秒，已包含在前表的「下轮开始 → 请求指标点」区间内，不能再次相加。

| 第一条请求的准备项 | 耗时 |
|---|---:|
| tool_registry_total | 6.385 秒 |
| token_estimate | 2.674 秒 |
| build_messages | 0.397 秒 |
| plugin_context | 0.276 秒 |
| load_model_history | 0.026 秒 |

工具目录内部 host definitions 2.394 秒、disclosure 2.378 秒、revision 0.914 秒等属于嵌套阶段，不与 registry_total 相加。单纯裁剪聊天历史不能解决这个样本的主要等待。

精确本地单调时钟记录 preparation_to_http_send 为 10.573 秒，模型请求 worker 队列只有 5 毫秒。API 首增量约 3.033 秒，其中上传正文约 0.726 秒、等待响应头约 1.195 秒；其余包含序列化、发送与流解析等间隔。因此主要耗时发生在请求发出前。

工作区同时已有工具 schema 内容缓存、工具披露离开事件循环、Token 估算缓存和日志减量等改动；这部分属于同一工作区的其他优化，不能算成本次已在线验证的收益。保留运行时权限和工具过滤的实时检查，避免为了缓存整份 registry 而使用过期权限。

## 呈现调整

会话 Goal 面板和输入框窄条显示阶段名与阶段用时；设置中的 Goal 控制台也显示相同阶段：

`本轮收尾 → 等待下一轮 → 续跑已排队 → 准备下一轮 → 正在请求模型 → 进行中`

- final 事件即进入收尾，不等到 run_finished 才提示。
- 人工停止显示「已停止，等待继续」，待用户交互、暂停、阻塞、退避分别说明。
- 用真实观测到的阶段时间计时，没有锚点时仅显示标签；不生成虚假的百分比或剩余秒数。
- /goal/progress 返回精简状态，不返回目标正文、对话或用量去重列表。等待期最多每 2 秒校准，执行/停止期每 15 秒；隐藏页面停止读取，卸载中止请求。完整 Goal 仍由初次读取、状态事件或操作更新。
- 只跟踪当前续跑的 run_id，旧 run 的迟到事件不会覆盖新一轮状态；阶段内 token delta 不会重置计时。

## 验证与生效范围

已验证的关键行为：

- 人为挂住后台维护，新 send/continue 仍在 1 秒观察窗口内进入测试 worker；有 1001 条积压事件时也成立，持久去重仍完成。
- 同时调用周期与即时派发不会重复启动；并发桥接连续推进两个批次，游标不会退回或重复消费同一批。
- 没有本 run 的待定位子代理结果时禁止读取 UI 历史；有匹配结果时仍正确定位，其他 run 的结果不受影响。
- 浏览器真实加载插件资源，验证阶段名与计时同步到面板和窄条、精简轮询、卸载清理；原暂停、阻塞继续、预算和审核操作仍通过。
- session-control、运行收尾、排队 followup、流恢复、子代理通知的 169 项回归通过；阶段/UI 与相关插件回归分别通过。最终测试数量以本轮交付说明为准。

**这是代码与受控测试完成，尚未完成同一真实会话的在线前后对比。** 当前宿主进程早于这些 core 改动，service、automation、agent_loop、agent_harness 的修正需正常重启服务加载；只热重载 Goal 插件不能加载宿主修正。本次未擅自重启，也未恢复用户手动停止的会话。

复测时建议分别检查 final→terminal、terminal→admitted、admitted→run_started、run_started→HTTP send、HTTP send→first_delta，并在同类负载下比较 P50/P95。不能把「阻塞维护时 worker 小于 1 秒启动」外推为整个真实交接已降到 1 秒。

## 复现与诊断

在仓库根目录执行：

```powershell
.\python\python.exe scripts/diagnose_goal_handoff.py 7cfcf4fc-a567-4124-8db9-0e04d2602be3 --events --limit 6 --output .analysis/goal-handoff-7cfcf4fc.json
```

脚本以 SQLite mode=ro 打开控制库，仅输出标识、阶段、时间和耗时，不导出对话正文。默认不扫描事件日志；--events 额外补齐末尾样本的持久 final/terminal/start 锚点。分析快照位于 `.analysis/goal-handoff-7cfcf4fc.json`。
