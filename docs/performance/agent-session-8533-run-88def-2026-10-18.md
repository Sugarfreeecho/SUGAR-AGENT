# 8533第三次重启验收与扩展状态补修（2026-10-18）

> 后续03:28重启后的`c004ed9b`已确认加载本篇c9冻结源，22个轮间仍7次≥500ms，后15个全部通过。最新补修、四组合失败、源指纹与设计映射见[c004报告](agent-session-8533-run-c004-2026-10-18.md)；下文保留88def及其后续阶段证据。

## 1. 真实验收：仍未达到500ms

用户沿用会话`8533e824-397a-4be9-a9ea-fe82d233c8f8`复跑“请分析仓库未提交改动”。本次run为`88def20e-7dd0-4859-8f52-03536181a7c1`，北京时间 **02:44:03–02:53:26**，55个请求、69次工具调用。8192的PID19968启动于02:42:25，晚于上一批生产代码完成时间02:19:20；分析及结束时源文件均匹配冻结指纹`b547811f…fbff4c`。有新批次交付日志。没有将本次失败解释成未重启。

严格口径仍为最后一个`execute_one_core`返回至下一次实际`http_send_entered`，保留全部54个完整配对。该端点之后的服务器等待不计入；历史长度也不作为本地等待的归因。

| run / 已加载版本 | 配对 | <500ms | ≥500ms | P50 ms | P95 ms | 最大 ms |
|---|---:|---:|---:|---:|---:|---:|
| `82981386` / 390af5e1 | 70 | 27 | 43 | 1053.973 | 2079.395 | 3307.732 |
| `88def20e` / b547811f | 54 | 5 | 49 | 1002.480 | 3074.323 | 4629.657 |

中位数略降，但超标比例和长尾没有改善，不能宣布这批优化已解决生产卡顿。两次工具组合、后台任务和机器状态不同，不是控制变量A/B；特别是本次实际启动了后台测试任务。所有失败均保留在[完整整理](../../.analysis/interround-500ms-implementation/real-session-8533-run-88def20e.json)。整理合并会话日志和终端日志，并按run ID及单调时钟去重，避免日志处理器切换漏项。

## 2. 当前慢在哪里

以下互斥分段覆盖每个完整间隔，各列分位数不能横向相加。

| 本地步骤 | P50 ms | P95 ms | 最大 ms |
|---|---:|---:|---:|
| core返回→最后工具模型事实提交 | 232.047 | 1374.054 | 1883.060 |
| 事实提交→下一轮准备开始 | 320.946 | 1035.828 | 4057.770 |
| 准备开始→调度worker | 375.715 | 952.959 | 1370.816 |
| worker排队 | 4.451 | 28.735 | 60.055 |
| worker进入→HTTP发送入口 | 16.605 | 75.462 | 101.145 |

### 2.1 工具返回后仍在完成执行草稿、结果事实和UI交付

- `journal_state`墙钟中位25.917ms、P95 81.387ms，`ui_projection`中位23.961ms、P95 88.832ms；这些子段已较短，但其父包络仍可很慢。
- journal worker进入→事务及journal会话锁取得的包络中位31.363ms、P95 422.939ms、最大1355.830ms，共23次≥500ms。它包含路径解析、打开锁文件和锁获取等准备，不能直接改名为纯锁竞争。
- 872个已记录`fact_append`子段中位36.619ms、P95 124.313ms、最大1470.881ms。线程CPU分位明显较低；没有系统级I/O追踪，不能把等待进一步断言成某个过滤驱动或硬盘问题。
- 第7→8轮4126.961ms，工具返回时reasoning交付尚未完成，随后两条结果批次交付638.489ms。批次已生效，仍有超标。

这些事件可能重叠，包络和子段不重复相加。日志只记录达到阈值的操作，分布不是全部微事件的分布。

### 2.2 新发现：后台执行扩展状态仍在事务内全量读日志

`ExecutionService._persist_job → persist → SessionExtensionStateStore.set_latest`用于后台任务启动、结束、取结果和通知确认。原实现：

1. `get()`复制整个Runtime快照；快照落后时完整读取并投影日志。
2. `compare_and_set()`取得会话事务后，`_snapshot_for_update()`无条件`read_all()`，即使快照已经是最新版本也解析全部事实。

后者会占用与journal共用的会话事务。这是源码可确认的重复工作，不是“上下文太长”的泛化解释。

使用本次13,130,406字节的完整行前缀副本，每次先追加一个execution事实，再更新同一job命名空间：

| 同一副本上的隔离更新 | 3次耗时 ms | 全量读日志次数 | 完整重放一致 |
|---|---|---:|---|
| 原扩展方法 | 891.628 / 825.982 / 802.824 | 6 | 是 |
| 受守卫的快照及后缀方法 | 6.712 / 4.958 / 5.968 | 0 | 是 |

这是顺序局部复现，不能外推整次Agent提速倍率。原始结果见[扩展更新副本对照](../../.analysis/interround-500ms-implementation/88def-extension-replay.json)。

第34→35轮间隔4629.657ms，其中提交→准备4057.770ms；结果交付约366ms，steer仅5ms，`round_gap_ms=3669`，期间出现后台任务通知的system事实。源码与复现支持优先修复通知相关扩展写入，但旧日志没有该次poll/persist/ack的独立span，**不能把整段3669ms全部归给它或GC**。

### 2.3 发送前仍重复检查工具目录、准备消息及配置

后54个请求的pre_api子段：

| 子段 | P50 ms | P95 ms | 最大 ms |
|---|---:|---:|---:|
| turn_cache包络 | 64 | 206 | 731 |
| tool_registry_total包络 | 146 | 311 | 565 |
| 其中revision | 94 | 250 | 526 |
| token_estimate | 7 | 36 | 52 |
| resolve_model_config | 19 | 140 | 246 |
| early_interrupt_checks | 18 | 69 | 80 |
| final_interrupt_checks | 13 | 46 | 216 |

registry慢明细最高514ms，其中host511ms、MCP3ms、host线程CPU15ms；不能继续把这一项写成“MCP等目录”。消息准备、插件配置读取及授权状态检查是后续具体排查对象。包络包含调用及调度时间，不把整个turn_cache直接写成消息转换CPU。

Hook方面，PostToolUse中位137.614ms、P95 972.858ms、最大1077.675ms；实际`hook_execute`不到1ms，慢点仍在目录/定义准备及其包络。

### 2.4 后台巡检和change-review仍有成本，不能直接算成轮间

定向巡检已经跳过任务树，但当前真实全扫描仍找到276个候选，枚举最高5471.276ms、扫描总计11208.249ms。扫描已在心跳全局锁外；只能确认后台仍有显著文件系统工作，未证明这些毫秒全部阻塞前台。

change-review有before约1072ms、after约1062ms；after慢例分别落在inventory约1001ms和index_read约815ms。本次run_shell的change-review常在`execute_one_core`返回前结束，因此它影响工具总耗时，不能把整个after阶段再加到严格轮间。外层`tool_workspace_audit`则在严格端点之后，仍属于轮间。

### 2.5 首轮与结尾单列

第一次准备→HTTP发送 **6938.036ms**，没有上一工具，不混入54个配对。最后`final_pipeline`867ms，其中`finish_after_final`676ms；随后公共`run_finalize`205.298ms，包含metrics_finish107.005ms、未读状态59.334ms、终态事实21.301ms、power guard0.810ms。它们是本地可见收尾成本，不能用worker队列小来忽略，也不与已嵌套阶段直接相加。

## 3. 验收后继续实现的补修

这些修改在02:53真实run结束后才进入生产源码，**不属于上述b547实测**。

1. 扩展状态更新在原会话事务中校验投影版本、源文件身份、size/mtime与seq；最新则复用不可变快照，连续后缀走已有严格补尾。冷缓存、旧stamp、替换、截断、版本不符保留事实恢复。只复制选中的namespace，事实追加、CAS冲突与持久化顺序保持同步。
2. seq缓存键直接来自本次已解析并stat的路径，消除二次解析。新增命名空间在两次解析间切换的用例，原代码会把A路径游标装到B路径键下；也减少四工具交付批次的20次重复解析/60次metadata查询。该计数来自隔离profile，没有证明单独的整体墙钟收益。
3. `round_entry`补齐pre_api开始前的所有权检查、review补扫、子代理通知和后台执行通知。后者分poll、模型通知提交、ack。后台扩展写入≥50ms记录`extension_write/extension_snapshot`及原事实子段；记录不含任务payload，也不推迟提交和确认。

设计分别落在用户设计08/04 UC-8D9、08/01 UC-8A14、09/04 UC-9D13及09/05 §4.13。

## 4. 验证和版本

- 候选局部一致性回归36 passed；正式生产源码定向回归 **496 passed，45.26秒**，覆盖RuntimeV2、后台执行/重启、UI批次、轮入口、Agent循环和续跑。两组有重叠，不相加。
- 新增13项覆盖：warm及journal补尾、外部追加、保持size/mtime/seq的替换、截断、旧投影、旧stamp、COW/只复制namespace、seq路径切换、轮入口取消/暂停、通知提交失败不ack等。
- **32个生产文件+1个原基准文件编译通过**；冻结指纹 **`c9e1a73c057770e5293eb3d808712a69247129ae857464e3bfe85fb1db6ba886`**，完整清单见[源清单](../../.analysis/interround-500ms-implementation/88def-extension-source-sha256.json)。
- 后台通知完整流程的附加负载对照另记下节；局部复现和测试通过均不代表真实500ms验收通过。

### 4.1 带真实后台执行状态写入的完整流程对照

生产`astream_events`连接本机SSE模型，不调用付费API；真实read_file、Hook、事实/UI交付和通知服务。初始1000条历史、4000条context事件、200条完成execution记录，共37,276,095字节；40流分片/10ms间隔、有usage；300归档会话各6个任务目录、实际watchdog（全扫描周期保持默认）。同时4个CPU worker及1个fsync I/O worker，均确认启动并记录CPU秒数。

每组6个完整配对、24次成功read_file。在每次工具返回后**刻意额外注入job创建和结束**，再由原轮入口提交完成通知并ack：每轮共3次真实扩展状态写入。正常Agent此处只领取/确认已完成任务，因此本组是附加边界负载，不冒充原任务复跑。

| 扩展方法 | HTTP send P50 ms | P95 / 最大 ms | ≥500ms | 轮间全量读 |
|---|---:|---:|---:|---:|
| 私有进程恢复原get/更新方法 | 1883.122 | 2250.992 | 6/6 | 18 |
| 新生产方法 | 912.498 | 1073.527 | 6/6 | 0 |

中位约下降52%，但两个独立顺序样本不是全机器状态严格相同的A/B，不能直接外推真实提速。两组都还超标，**没有达成目标**。原基准的`full_model_projection_calls`两组都是0：重复解析完整日志后发现seq相同、不调用project，也会很慢；因此这里额外按实际`SessionEventLog.read_all`及严格端点计数，而不把“0次完整投影”等同“0次全量读取”。

原始[reference](../../.analysis/interround-500ms-implementation/88def-notices-reference.json)、[current](../../.analysis/interround-500ms-implementation/88def-notices-current.json)与[计数整理](../../.analysis/interround-500ms-implementation/88def-notices-comparison.json)保留。私有诊断入口`benchmark_extension_notices.py`封装原基准，reference仅在独立测试进程替换两个旧方法；生产源码未反复切换。复现参数如下，两组只改变reference开关与输出路径：

```powershell
.\python\python.exe -X utf8 .analysis/interround-500ms-implementation/benchmark_extension_notices.py --reference-extension --steps 6 --tools-per-round 4 --tool read_file --only-case loaded_long --execution-records 200 --stream-fragments 40 --fragment-interval-ms 10 --archived-sessions 300 --archived-task-dirs 6 --watchdog-interval-ms 100 --output .analysis/interround-500ms-implementation/88def-notices-reference.json
```

不带`--reference-extension`并改输出文件即新方法。正式回归命令为同目录`run_targeted_tests.py`运行`tests/runtime_v2`、`test_execution_integration.py`、`test_execution_services.py`、`test_execution_recovery.py`、`test_execution_ui_commit.py`、`test_tool_batch_delivery.py`、`test_round_entry_timing.py`、`test_local_operation_timing.py`、`test_agent_loop_runtime_v2.py`和`test_queued_followup_continuation.py`，参数`-q --disable-warnings --tb=short`。运行入口均带Windows spawn的`__main__`保护，测试使用一次性workspace。

## 5. 当前结论和下一次验收

**目标仍未达成。** 已确认并处理的具体缺陷是扩展状态全量读和seq缓存键二次解析。剩余真实热点包括事件提交包络、host目录检查、Hook资源准备、轮入口空档和首尾成本；后台巡检仍有秒级I/O。对这些步骤的存在有日志依据，对每个内部等待的根因及各项修复最终收益仍有测量缺口，不能给出无依据的“95%全部解决”保证。

待本批加载后沿用同一会话复跑，按新run ID采集全部完整配对，并核对新round_entry与extension_write子段；不得将上述b547数据归到新补修。之前的失败、隔离原型及各阶段版本继续保留。

## 6. c9冻结后的独立定位与真实检查点恢复

本节保持c9生产源码不变，仅在独立进程及文件副本上继续核对。采样时8192仍为02:42启动的PID19968，最新run仍是已结束的88def，没有将这些独立结果冒充新生产验收。

### 6.1 轻载调用本体尚不能解释旧run的包络长尾

每项预热3次后采30次，使用墙钟cProfile，计时可能受采样影响。host用20个私有注册绑定，调用真实bundled插件可用性逻辑；未启动实际插件服务或computer连接。消息输入是本run磁盘投影中的128条真实模型消息，复现相同的两遍sanitizer、缓存前缀与增量末尾、缺失tool补齐、孤立结果过滤及执行提示词函数。

| 独立操作 | 中位 ms | 最大 ms |
|---|---:|---:|
| get_plugin_manager | 1.973 | 2.614 |
| 插件状态read | 0.136 | 0.174 |
| 20绑定的一次host catalog pass | 2.354 | 3.805 |
| 真实128条消息的纯热路径整理 | 0.308 | 0.444 |
| 执行提示词函数 | 2.116 | 3.614 |
| 消息整理连同执行提示词 | 2.555 | 3.201 |

host profile中，30个pass共调用manager30次、状态read30次，现有同次availability scope有效；不是20个绑定各自读一次。manager30次包含210次Path.resolve、480次GetFinalPathName、330次stat；主要是路径规范化，但独立包络仅约2ms。真实消息的纯Python整理不到1ms，不能把旧run中turn_cache的64–731ms直接当作该算法的CPU时间。

这些结果没有重建原任务当时的线程、锁、文件系统和后台任务竞争；不能据此否定真实长尾，也不足以证明某种竞争是其唯一根因。下一次c9实跑先检验去掉扩展全量读取后的相关包络；若仍慢，需要锁获取、配置解析、状态读取和运行时调度的独立证据，不能用陈旧授权/插件状态缓存换取表面数字。

原始[host profile](../../.analysis/interround-500ms-implementation/continued-c9-host-profile.json)、[真实消息热路径profile](../../.analysis/interround-500ms-implementation/continued-c9-warm-turn-profile.json)及对应pstats保留。这是定位证据，不计为新增性能验收样本。

### 6.2 真实旧检查点能补到耐久终态

磁盘latest快照停在seq7919，而事实尾部seq7933已有本run的run_finished；磁盘派生快照落后不等同于终态事实缺失。独立复制事实和该快照，仅将stamp文件身份映射到副本，保留原seq和字节边界。先计算完整重放作为oracle，再禁止被测补尾调用read_all。

新扩展读取在原事务内补齐14条后缀耗时 **6.160ms**；恢复run状态finished，模型消息及扩展状态均与完整重放一致，原发布快照未改变。副本测试没有写入真实会话，也没有重跑工具。证据见[真实检查点补尾](../../.analysis/interround-500ms-implementation/continued-c9-real-checkpoint-tail.json)。这补充验证了本批对真实数据的恢复边界，不将单次6ms外推为一般冷恢复或整体轮间耗时。

## 7. 当前c9版本的四组合与工具补验

依据原《同机Agent实现对比与500ms方案》补齐本次生产源码的四组测量，未借用旧版本通过结果。生产文件及原基准脚本在前后均与c9清单一致，未混入候选优化。仍使用实际Python3.10.11、生产astream_events、本机SSE模型、真实工具与耐久交付；40流分片/10ms间隔、有usage、300归档会话各6个任务目录、实际watchdog。长历史37,276,095字节，重载为已确认运行的4个CPU进程和1个fsync I/O进程，各例附CPU时间差；没有加入§4.1的额外job创建/结束负载。

| 工具 / 条件 | 每轮工具 | 配对 | send中位 ms | send P95/P99/最大 ms | ≥500ms |
|---|---:|---:|---:|---:|---:|
| read / 轻载短历史 | 4 | 6 | 131.810 | 200.078 | 0 |
| read / 轻载长历史 | 4 | 6 | 166.064 | 199.855 | 0 |
| read / 重载短历史 | 4 | 6 | 276.404 | 622.153 | 1 |
| read / 重载长历史 | 4 | 6 | 378.630 | 429.491 | 0 |
| write / 重载长历史 | 1 | 4 | 191.290 | 234.068 | 0 |
| shell / 重载长历史 | 1 | 4 | 176.339 | 355.868 | 0 |

合计32个完整配对、104次工具调用全部成功，**仍有1个send端点超标**；更晚headers端点最大622.616ms。样本仅4或6次，各组P95/P99都等于最大值，不能据31/32通过声称有95%置信度达标，也不能用重载长历史通过覆盖重载短历史失败。write/shell本次只补重载长历史，未将旧版其他组合写成本版结果。

所有例的完整投影计数及轮间完整投影计数均为0、版本失配0；read各39次补尾、write15次、shell21次。registry每例7或5个请求中包含1次初建，其余命中或stale-hit。完整投影计数不等于实际read_all计数（见§4.1），本组没有把前者改名为“全量读取为0”。原始[四组read](../../.analysis/interround-500ms-implementation/c9-four-case-read.json)、[write](../../.analysis/interround-500ms-implementation/c9-loaded-write.json)、[shell](../../.analysis/interround-500ms-implementation/c9-loaded-shell.json)与[整理](../../.analysis/interround-500ms-implementation/c9-normal-flow-summary.json)保留。

### 7.1 622ms超标的互斥步骤

该例为重载短历史第6→7轮，全部4个read结果已返回：

| 步骤 | ms |
|---|---:|
| 最后core返回→工具模型事实提交完成 | 107.901 |
| 提交完成→下一轮准备 | 370.801 |
| 准备→调度 | 41.950 |
| worker队列 | 1.998 |
| worker进入→HTTP send | 99.502 |

同一时间轴上，4条结果的严格交付批次从+116.351ms开始，持续324.236ms；round_entry仅4.356ms，其中execution通知poll约0.966ms。下一轮pre_api汇总33ms。worker中的消息转换1.216ms、wire编码2.789ms，其余约95ms没有更细的SDK/调度分项，不能把它全部写成JSON编码时间。交付包络与其journal/UI子段不可重复相加，详见[失败原始span](../../.analysis/interround-500ms-implementation/c9-four-case-outliers.json)。

这项补验确认本版本仍有结果批次交付长尾；没有通过删减事实提交、跳过UI确认或丢弃失败样本凑出通过结论。它仍不能代替当前服务加载c9后的真实同任务验收。

## 8. MCP依赖和当前启动状态的边界

按原方案再次核对已修复的本地缓存：`@upstash/context7-mcp 4.4.2`直接使用缓存中的Node入口，stdio initialize约1037.051ms、tools/list约2.901ms，总1039.952ms、返回2个工具。仅本地协议发现，没有调用远端工具、修改用户MCP配置或再次安装依赖。结果见[本地探针](../../.analysis/interround-500ms-implementation/continued-c9-context7-local-probe.json)。

旧服务02:43:55的日志同时出现ready和60秒启动超时，后续还有一次stdio启动。这说明不能仅凭ready行宣布运行连接健康；上述探针绕过npx及服务启动线程，也不能据它把历史超时归给包损坏、网络或某一个锁。Agent请求读已发布代的逻辑保持不变；管理面GET工具列表仍显式等待ensure_started，未用该接口在此处触发新的启动/重连。下一次真实run同时观察每服务ready/错误及工具目录代，保留未就绪时明确不可用和正常请求不等待失败服务的契约。
