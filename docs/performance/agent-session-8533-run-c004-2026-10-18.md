# 8533第四次重启验收与追加路径补修（2026-10-18）

> 后续第五次重启`d68f57b4`已确认加载本篇5234冻结源，16个严格轮间仍4次超标。新增Hook外层证据、LLM线程池隔离及生产基准见[d68报告](agent-session-8533-run-d68-2026-10-18.md)，下文保留c004及其后续各阶段证据。

## 1. 实跑结论：后段恢复较快，整体仍未通过

会话`8533e824-397a-4be9-a9ea-fe82d233c8f8`的新run为`c004ed9b-8c6b-4fec-b08c-70978fd766df`，北京时间 **03:28:46–03:32:30**，23个请求、27次工具调用。8192进程PID28260启动于03:28:06，晚于上一批02:56完成时间；采集时32个生产文件均匹配冻结源`c9e1a73c…6ba886`，并出现新增的`round_entry`计时。已确认本次加载了扩展状态补修，不再按未重启处理。

严格口径：最后一个`execute_one_core`返回至下一次实际`http_send_entered`，包含工具外层审计、提交、交付、轮入口和准备。服务器返回等待不进入这个区间。

| 范围 | 完整配对 | <500ms | ≥500ms | P50 ms | P95 ms | 最大 ms |
|---|---:|---:|---:|---:|---:|---:|
| 全部 | 22 | 15 | 7 | 124.983 | 1601.943 | 1716.021 |
| 前7个（下一请求iter2–8） | 7 | 0 | 7 | 967.072 | 1716.021 | 1716.021 |
| 后15个（iter9–23） | 15 | 15 | 0 | 90.896 | 355.063 | 355.063 |

本轮用户问题是“现在又有哪些新增改动”，与上一run“请分析仓库未提交改动”的工具组合及任务不同。可以报告本次观测改善，不能据前次49/54超标和本次7/22超标计算受控提速倍率。全部样本、源证据和日志子段见[实跑整理](../../.analysis/interround-500ms-implementation/real-session-8533-run-c004ed9b.json)。

**诊断负载披露**：本次服务启动时，先前已发起的私有profile尚在运行（4CPU进程、1个I/O进程），随后立即停止追加压力实验，待真实run结束才运行候选实验。该profile完成时间03:28:52；真实首请求准备与它重叠，因此首请求不是干净的冷启动A/B。所有22个严格轮间的起点都晚于诊断文件完成的保守结束界，轮间重叠数为0；没有剔除任何轮间。原始负载区间与保守界写在实跑整理中，重叠不等于因果证明。

## 2. 当前卡顿步骤

### 2.1 互斥分段

各列分位数不能横向相加。

| 步骤 | P50 ms | P95 ms | 最大 ms |
|---|---:|---:|---:|
| core返回→最后工具模型事实提交 | 22.530 | 697.442 | 813.074 |
| 事实提交→下一轮准备开始 | 30.214 | 406.716 | 491.831 |
| 准备开始→调度worker | 37.254 | 505.954 | 509.058 |
| worker排队 | 1.610 | 6.703 | 55.626 |
| worker进入→HTTP发送入口 | 16.041 | 20.989 | 56.730 |

全部7个失败如下，iter表示即将发送的请求：

| iter | 总计 | core→提交 | 提交→准备 | 准备→调度 | 队列 | worker→发送 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2 | 1601.943 | 813.074 | 406.716 | 364.083 | 1.513 | 16.557 |
| 3 | 1037.100 | 115.621 | 387.834 | 505.954 | 6.703 | 20.989 |
| 4 | 572.734 | 62.794 | 207.297 | 190.287 | 55.626 | 56.730 |
| 5 | 1716.021 | 697.442 | 491.831 | 509.058 | 4.773 | 12.917 |
| 6 | 738.735 | 298.188 | 173.967 | 243.665 | 5.814 | 17.102 |
| 7 | 967.072 | 340.981 | 256.918 | 351.666 | 1.502 | 16.005 |
| 8 | 800.983 | 276.243 | 257.692 | 245.038 | 2.084 | 19.925 |

### 2.2 工具结束后的Hook外层和结果交付

- iter5之前，`PostToolUse`总包络472.527ms；已计插件加载65.490ms、运行定义4.164ms、manager4.453ms、实际执行0.062ms。约398ms位于这些span之外，不能把它叫作“Hook脚本执行慢”。会话metadata、工作区准备及前后文件审计仍缺细分。
- 同一失败中的`tool_call`交付376.393ms，journal约182ms、UI约185ms；iter2之前结果交付346.215ms。它们是可确认的本地步骤，不与父包络重复相加。
- 全run已记录的journal进入→事务及journal会话锁取得包络P95 304.044ms、最大871.168ms。该范围还包含路径和锁文件准备，不能直接等同纯锁竞争；慢日志不是所有微操作的无偏分布。
- `PreToolUse`出现618.945ms和419.045ms，其中运行Hook定义准备分别498.038ms、406.904ms，实际执行均约0.1ms。PreToolUse发生在工具core返回之前，影响本轮工具时延，不把这两段另加进严格轮间。

### 2.3 下一轮准备仍有目录检查长尾

后22个请求的`tool_registry_revision`P50 9ms、P95 220ms、最大370ms，registry总包络最大376ms；`turn_cache`最大95ms，token估算最大40ms、配置解析最大21ms。日志中的目录慢例主要是host检查，不能笼统归因MCP等目录，更不能归因历史长度。

新增`round_entry`全部23次P50 2.372ms、最大76.936ms，后台通知poll最大34.515ms；本轮没有≥50ms的`extension_write`。这说明当前观测到的入口成本较小，但缺少重后台任务的样本，**不能仅凭没有慢日志证明扩展补修的实际收益**。

后台巡检仍有总计5504.207ms、其中枚举1821.096ms的全扫描，候选276个。它在全局锁外运行，尚无证据把扫描总时间全部计入前台轮间。change-review在core返回之前的部分仍属于工具执行，不重复计算。

### 2.4 首轮和收尾单列

首次准备→HTTP发送6671.346ms，其中pre_api工具目录总包络4300ms、静态段1524ms、token估算604ms。由于上述诊断负载重叠，不把本次与旧run首轮6938ms当作独立优化A/B。需要后续干净启动复核。

最后`final_pipeline`112ms，随后公共`run_finalize`141.255ms（终态提交15.072ms、未读状态44.864ms、metrics_finish71.373ms、power关闭1.342ms）。收尾按其实际顺序单列，不混入22个轮间。

## 3. 实跑后继续完成的生产修改

以下不属于上面c9实跑，需加载新代码后另验。

1. **每次追加绑定一次事件路径**：单条、批次和`append_event`的seq读取、事实写入、seq缓存更新使用同一次解析所得路径，减少重复resolver和文件检查；下一次操作仍重新解析，不保留常驻句柄。
2. **seq缓存补齐身份和发布守卫**：缓存同时核对device/inode/size/mtime；文件被同size/mtime替换、旧三字段缓存、未知inode均回事实尾部读取。冷观察者读取期间发生追加时，不把旧seq挂到新metadata；追加发布缓存时还核对实际writer的flush后fstat，避免文件替换后的错误游标。
3. **Hook外层细分计时**：补`hook_session_metadata`、`hook_workspace_prepare`、`hook_workspace_before/after`，保留原执行、审计与授权顺序。它用于定位约398ms未覆盖包络，本项本身不是速度优化。

私有复现确认旧c9能命中错误游标：保持文件size/mtime替换seq1→9后仍返回next2；以及观察者读尾与路径切换/追加交错时污染后续缓存。生产新增11项行为回归覆盖这些边界及三种追加入口。正常事实写入/flush、CAS、所有权和恢复事实边界均保持同步。

## 4. 验证与版本

- 正式生产源码：**532 passed，1 skipped，49.15秒**；范围含RuntimeV2、执行服务与重启恢复、UI批次、Agent循环、续跑、路径事务和Hook。跳过项为系统目录符号链接能力不足；实际目录替换用例已通过。日志见[回归结果](../../.analysis/interround-500ms-implementation/bound-append-production-regression.txt)。
- 32生产文件、1原基准、1新增测试文件编译通过，改动文件diff检查通过（仅CRLF提示）。冻结指纹`5234b299679f4bd1fc24f64d051920e141c406663531daa1756832c4109c5d42`，相对c9仅修改`event_log.py`与`agent_loop.py`两份生产文件；原基准未改。见[源清单](../../.analysis/interround-500ms-implementation/c004-bound-append-source-sha256.json)。
- 私有cProfile显示完整4结果批次的resolver调用中位100→83、stat427→363。但reference与真实服务启动重叠，批次分组数也不同，不能将其墙钟变化当作因果收益或500ms验收。

### 4.1 新生产代码的完整流程基准

使用bundled Python3.10.11、生产`astream_events`和本机SSE模型，执行真实工具与耐久交付，无付费API。40分片/10ms、带usage；长历史37,276,095字节，300归档会话各6个任务目录，真实watchdog；重载为已确认存活的4CPU进程和1个fsync I/O进程。各组顺序运行，无c004真实run重叠。未开启cProfile或额外diagnostic spans，原基准代码保持不变，前后源码均与5234指纹匹配。

| 工具 / 条件 | 每轮工具 | 配对 | send P50 ms | P95/P99/最大 ms | ≥500ms |
|---|---:|---:|---:|---:|---:|
| read / 轻载短历史 | 4 | 6 | 126.942 | 176.307 | 0 |
| read / 轻载长历史 | 4 | 6 | 195.981 | 218.166 | 0 |
| read / 重载短历史 | 4 | 6 | 233.706 | 259.311 | 0 |
| read / 重载长历史 | 4 | 6 | 445.346 | 518.804 | 1 |
| write / 重载长历史 | 1 | 4 | 210.304 | 264.812 | 0 |
| shell / 重载长历史 | 1 | 4 | 205.323 | 303.940 | 0 |

合计32个完整配对、104次工具全部成功，**仍1次≥500ms，不能宣布达标**。每组仅4或6次，P95/P99均为最大值；31/32通过不代表95%置信度满足目标。四组read、write、shell的source与全部统计见[整理](../../.analysis/interround-500ms-implementation/c004-bound-normal-flow-summary.json)，其中分别链接原始文件。完整投影与投影版本失配均为0，但没有把“完整投影为0”改称“全部read_all为0”。

失败为重载长历史iter2→3，互斥步骤为core→提交145.218ms、提交→准备265.781ms、准备→调度59.941ms、队列2.124ms、worker→发送45.741ms。3条已完成结果先合批交付，最后一条在其后单独交付，后者225.241ms（journal174.660ms、UI41.349ms）；journal worker进入→事务取得100.852ms，轮入口仅6.112ms。原策略只合并已经就绪的结果，不等待凑齐；没有通过延迟工具或移动计时端点减少失败。保留[失败细分](../../.analysis/interround-500ms-implementation/c004-bound-outlier-ops.json)。路径/锁文件准备及提交仍是下一步定位对象，不能把100.852ms未经细分就全部称为锁竞争。

read复现命令如下；write/shell将`--steps`改4、`--tools-per-round`改1、选择对应tool并加`--only-case loaded_long`，使用不同输出文件：

```powershell
.\python\python.exe -X utf8 scripts/benchmark_agent_interround.py --steps 6 --tools-per-round 4 --tool read_file --execution-records 200 --stream-fragments 40 --fragment-interval-ms 10 --archived-sessions 300 --archived-task-dirs 6 --watchdog-interval-ms 100 --stress-workers 4 --output .analysis/interround-500ms-implementation/c004-bound-four-case-read.json
```

回归由`.analysis/interround-500ms-implementation/run_targeted_tests.py`在一次性workspace运行：`tests/runtime_v2`、`test_execution_integration.py`、`test_execution_services.py`、`test_execution_recovery.py`、`test_execution_ui_commit.py`、`test_tool_batch_delivery.py`、`test_round_entry_timing.py`、`test_local_operation_timing.py`、`test_agent_loop_runtime_v2.py`、`test_queued_followup_continuation.py`、`test_session_path_transaction_cache.py`、`test_hooks_core.py`，参数`-q --disable-warnings --tb=short`。

## 5. 当前状态

**真实目标仍未达成**：c9实跑22个轮间有7个≥500ms，不能用后15轮通过覆盖前7轮失败。当前已落地重复路径解析减量和缓存正确性补修；Hook外层等待及首轮目录准备仍需新探针的真实证据。对“卡在上述本地步骤”的证据充分，对每段文件系统/调度等待的唯一根因仍不具备95%把握，不给出未验证的达标保证。

用户设计同步在08/01 UC-8A15、09/04 UC-9D13及09/05 §4.14。后续按新run ID、源码指纹和完整严格端点验收，继续保留失败样本。
