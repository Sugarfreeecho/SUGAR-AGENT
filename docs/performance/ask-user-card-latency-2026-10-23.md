# ask_user 参数完成到卡片出现的延迟补修

## 1. 结论与范围

已定位并修复人机交互服务的重复全量投影和完整快照复制。问题创建仍等待原事实提交完成，再推送卡片；创建和取消写入改为等待式线程调用，避免同步文件工作阻塞事件循环。没有改变ask_user必须独占一条assistant工具批次的规则，也没有在参数尚未结束时提前发问。

实际样本为会话`4bc203cb-adb5-4a8e-8ada-c9f299c3e7c6`、run `649bcb9e-5175-402a-9601-c65e066e0ab9`、工具`call_00_5dyu7k7vcqx4ey7rr9wyai3b`。2026-10-22 23:01:57.693参数已完整，直到23:02:01.238才记录卡片的执行锚点，服务端相关链路约**3545ms**。这是可关联的本地事实边界，尚不是浏览器绘制时间。

同一份真实日志前缀的首轮隔离对照，原后端准备为5146.569 / 5981.500ms，补修后为100.311 / 103.974ms。随后对最终源码再次冻结核对，独立一对为**10478.094ms → 169.745ms**，全量日志读取仍为每次2次→0次。两批分开保留，不混成受控负载的统计样本或外推P95/生产通过率。最终相关功能回归**200 passed，75.95秒，源码无漂移**。

截至2026-10-23 00:33端口核对，服务仍是10-22 20:09:46启动的PID23820，早于本批代码，实际生产收益尚未验收。未重启或中断用户任务，未向真实会话插入测试问题。

## 2. 实际样本的分段

从35个不重复参数片段重建得到完整JSON，1389字符、4个问题；第一次可完整解析的记录就是seq27429。后续边界均来自同一run和tool_call_id。

| 本地时间（2026-10-22） | 事实/阶段 | 与上一边界之差 |
|---|---|---:|
| 23:01:57.693 | 参数JSON首次完整，seq27429 | 起点 |
| 23:01:57.757 | 助手工具调用事实提交，seq27435 | 64ms |
| 23:01:57.926 | 工具待执行锚点，seq27436 | 169ms |
| 23:01:57.977 | 工具进入waiting_input，seq27437 | 51ms |
| 23:01:59.768 | interaction_requested，seq27438 | 1791ms |
| 23:02:01.238 | 卡片关联的execution_recorded，seq27439 | 1470ms |

事件timestamp在写入/投影流程内部产生，因此上述是可核验的事实间隔，不是各函数的精确耗时。前后1791/1470ms还包含锁、锚点、索引和推送处理，不能全部直接标成磁盘或回放时间。用户在23:13:31才回答的等待不属于卡片出现延迟。

原始去内容化关联记录见[production-case.json](../../.analysis/ask-card-latency-20261022/production-case.json)，局部日志见[production-timings.log](../../.analysis/ask-card-latency-20261022/production-timings.log)。前端`event-dispatch.js`收到人机交互事件后直接调用`renderHumanInteractionEvent`；已有浏览器回归覆盖锚点、草稿与交互。本次没有生产浏览器端接收/绘制时间戳，不宣称前端所有场景零等待。

## 3. 原因与实现

### 3.1 消除同一次创建的两次全量回放

原`_snapshot_locked`发现快照seq落后就`read_all + projector.project`，但只返回私有计算结果。紧接着`_append_locked`再读到旧发布快照，发现仍落后，又全量读日志并投影。模型消息刚提交后，`tool_pending/waiting_input`正好会追加执行事实，所以只落后两条也触发整个事件历史的两次回放。

现在事务内复用第一次检查过的快照；使用既有`SnapshotStore.project_after_append`严格补尾，再投影本次请求。补尾后更新其已读来源边界，避免下一步重读同一尾段。版本、文件身份、字节边界和连续seq守卫继续执行；冷缓存、损坏派生戳和源替换仍回退全量重建。seq相等也需核对来源identity/size/mtime，不能把seq相等当源未变化。创建、回答、取消、过期及审批分析复用同一规则，摘要校验与审批决定语义保持。

### 3.2 状态查询只复制交互记录

原创建后的`get()`通过`read_consistent`复制了整个Runtime快照，包括无关模型与执行历史。现在内部取得只读一致视图，`get/list`仅深复制返回的交互记录。返回的嵌套问题、选项与metadata仍隔离，调用者不能改写发布缓存。pending计数索引仍在原事务提交路径更新，没有为先显示卡片而延后事实提交。

### 3.3 创建离开事件循环，取消仍收敛

`wait_for_user_answers`用既有`run_fact_commit`在线程创建问题，所属loop继续等待；成功回执在原loop登记waiter，再在线程重查状态，最后按原顺序推送卡片。创建前后恰好收到答案时，重查可恢复答案；取消发生在排队或创建中时，先等创建结算、登记回执，再取消该问题并移除waiter，不遗留可操作的孤立问题。创建失败不发卡片。

`run_fact_commit`增加可选`trace_state`，只给首参不是ReAct State的调用补关联标签，不改变writer参数和既有调用行为。builtin invoker传入实际react_iter；`_runtime_v2_committed`仍只在请求事实完成之后用于推送。

### 3.4 新的分段计时

- `ask_user_card_prepare`关联session/run/iter；只覆盖创建、waiter登记、状态重查和emit确认，在等用户答案前结束。
- `ask_question_create_await / ask_question_status_recheck / ask_question_card_emit`分别记录三个等待区间。
- worker中的`interaction_snapshot_prepare / interaction_fact_append / interaction_projection / interaction_checkpoint / interaction_pending_counts`分开记录；原`fact_commit_await`仍区分排队、工作和回到loop。
- 没有emit时不记录假的`ask_question_card_emitted`。emit完成只代表服务端回调确认，不是浏览器收到或绘制。父子包络不可重复相加；日志不记录问题、选项、答案或请求正文。

## 4. 真实前缀的隔离对照

保存请求前的34,980,597字节、27,437条事实。对照从seq27435的一致快照出发，随后补上两条执行状态事实，预热journal锚点；测量创建、状态重查、真实journal卡片关联，使用与原逻辑一致的异步派生checkpoint。事实提交仍在计时路径。各测例都有独立目录，并检查请求、摘要、pending计数及新service的重读恢复。

| 次序 | 版本 | 创建ms | 状态重查ms | 卡片journal关联ms | 合计ms | 全量读取 |
|---|---|---:|---:|---:|---:|---:|
| 1 | 旧 | 5016.659 | 125.433 | 4.477 | 5146.569 | 2 |
| 2 | 新 | 94.926 | 0.453 | 4.932 | 100.311 | 0 |
| 3 | 新 | 98.147 | 0.963 | 4.864 | 103.974 | 0 |
| 4 | 旧 | 5854.218 | 124.002 | 3.280 | 5981.500 | 2 |

见[对照结果](../../.analysis/ask-card-latency-20261022/prefix-benchmark.json)。这不是LLM调用、实际SSE队列或屏幕绘制测试；为固定输入只建1个问题，原生产样本是4个问题；准备期完整投影和checkpoint排空不计入计时，journal已预热，未制造CPU压力。自然主机负载未受控，不能把小样本当全部生产场景保证。旧失败、重建回退和异步取消的正确性另由功能回归验证。

首轮后补充了损坏派生戳保护、无emit不伪造标记及注释，随后对最终版本00:35的独立对照冻结7份关键依赖，运行期源码漂移0，见[最终源码对照](../../.analysis/ask-card-latency-20261022/prefix-benchmark-final.json)：

| 最终源码变体 | 创建ms | 状态重查ms | 卡片journal关联ms | 合计ms | 全量读取 |
|---|---:|---:|---:|---:|---:|
| 旧交互服务 | 10199.675 | 267.939 | 10.480 | 10478.094 | 2 |
| 最终交互服务 | 164.029 | 0.771 | 4.945 | 169.745 | 0 |

最终两例同样验证事实和重读恢复。旧/新单次值较首轮都变大，两批未控制整机负载，不能把差异归于某一细小提交，也不拿较快首轮代表所有最终运行。可确定的机制变化是消除正常尾部的两次全量读取及无关快照复制。

## 5. 验证与限制

新增13个用例覆盖正常补尾不读全量、同seq/不同seq源替换、损坏派生来源、只复制单条记录、原loop登记与落盘后发卡、快速回答、创建中重复取消、写失败不发卡、准备trace在答案前结束及无emit不伪造交付。

扩大组合包含完整Runtime V2等，547 passed/1 failed；失败为`test_host_builder_uses_one_snapshot_and_execution_checks_live_disable`原预期4个工具，当前目录多出独立的`switch_work_dir`，且运行期间另一任务修改`agent_harness.py`。保留该[扩大门禁](../../.analysis/ask-card-latency-20261022/gate-attempt1.json)，未改该测试或工具目录来凑通过。初次新增用例另有3个fixture断言错误：raw_model_messages内容实际在payload下，修正测试后复验，没有改变生产记录结构。

最终对当前源码冻结的问答/审批、浏览器卡片、事实取消、执行恢复、主循环及源边界组合为**200 passed，75.95秒，源码漂移0**，见[最终定向门禁](../../.analysis/ask-card-latency-20261022/final-targeted.json)。不把547和200相加，不声称整个仓库测试全绿。

收尾核对时，本批3份生产文件仍与最终测试和最终前缀对照一致；`agent_loop.py`随后又由另一任务修改，该后续版本不冒充已经被这200项执行覆盖。未覆盖/未加载边界均保留在[最终核对](../../.analysis/ask-card-latency-20261022/final-audit.json)，本批独立于此前工作区改动的差异见[production.diff](../../.analysis/ask-card-latency-20261022/production.diff)。

加载情况见[进程核对](../../.analysis/ask-card-latency-20261022/server-process.json)。生产进程早于本批修改，下一次自然加载后，可直接用正常ask_user运行的新trace核验；无需复跑之前的大任务。冷启动重建、原loop调度、SSE积压和浏览器绘制仍需按真实数据分开看，不能预先保证所有出卡都低于500ms。
