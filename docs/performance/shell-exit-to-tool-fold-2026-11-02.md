# run_shell退出后工具行迟迟不折叠：真实调用复核（2026-11-02）

结论：用户给出的调用在后端“进程退出状态记账→最终工具结果记账”之间有 **7.648秒**，其中change-review执行后扫描 **7.496秒**。这段有实际本地工作，阻塞本次工具完成及下一模型请求；不能解释成纯前端动画、空等或大结果落盘。前端实际收帧/绘制时间没有保留，本报告用后端端点定位，不能把记账时间直接称为屏幕折叠时间。

## 1. 匹配与端点

- 会话：`0b8d8aa7-2343-4a6f-a243-2c7bd7a313af`。
- run：`f504c8e9-2b45-4752-b1f4-2d9de3e29384`，ReAct第79轮。
- call：`call_00_qq9qvoraa8x2ura3k0yit5ew`。
- 命令和用户示例完全一致，结果为55 passed in 20.44s、Exit code: 0。

| 北京时间 | 后端事实/计时 | 含义 |
|---|---|---|
| 11:12:01.262 | events seq1045，execution_recorded | status=completed、process_state=stopped、exit_code=0，结果已含退出码；尚无最终UI提交标记 |
| 11:12:01.286 | event_delivery结束 | 此次tool_execution_state交付包络152.841ms，event_publish本体3.978ms；退出信息可进入实时展示 |
| 11:12:08.863 | change_review_timing stage=after | 执行后工作区扫描结束，elapsed=7495.534ms |
| 11:12:08.895 | seq1046，model_tool | 模型工具结果事实时间戳，append_model_message计时12ms |
| 11:12:08.910 | seq1047/1048，execution_recorded + tool_finished | 最终UI工具结果记账，前端收到后才满足自动折叠条件 |
| 11:12:09.142 | 第80轮request.started_at | 本地下次请求准备已完成到记录请求阶段；非实际HTTP发送端点 |

退出状态seq1045到最终tool_finished seq1048为7648ms。后者是折叠资格建立的后端事实时间戳，提交确认、发布、浏览器接收和绘制还会有尾段；本次没有把这些未知段填成0。

## 2. 7.496秒在做什么

生产change-review计时：

| 子段/计数 | 本次值 |
|---|---:|
| inventory（Git清单获取及路径过滤等整个函数） | 4632.410ms |
| 文件签名 | 321.204ms |
| 索引读 | 58.882ms |
| 索引写 | 4.315ms |
| 文件读/哈希 | 1.852ms |
| blob I/O / diff / UI commit | 各0ms |
| 锁等待 | 0.003ms |
| 文件 / 签名缓存命中 | 1936 / 1931 |
| 检测状态需重读的条目 / 输出变更行 | 5 / 0 |

这些已记子段之外约2476.871ms仍未由现有子计时单独归属，不能将其全称为磁盘写入或空白。源码在扫描合并阶段再次逐路径调用 `_runtime_output`，是进一步拆分的候选；尚未用历史调用栈证明该候选独占全部差额。

当前源码、当前工作区一次只读剖析（1938文件）进一步拆开inventory：总2125.503ms，Git子进程222.673ms，逐路径输出目录过滤1757.908ms，路径键66.320ms。`_runtime_output`在每个文件上执行 `Path(path).resolve()` 及 `WORK_DIR.resolve()`，该函数调用1938次。此剖析仅替代其 `agent_tools.WORK_DIR` 配置依赖为相同默认目录，未启动app、模型或写入生产会话；它证明当前过滤路径是热点，**不将当前222.673ms倒填为历史Git耗时**，也不把整个4632.410ms称为Git进程本体。

## 3. 为何Exit code出现了却还不折叠

`agent_tools.run_shell` 在通信/输出读取结束后组装包含退出码的result，经 `report_state` 发 `tool_execution_state(completed)`。这说明子进程已结束。之后仍依次有scratch lease释放、change-review after capture、通用workspace audit、指标/PostToolUse Hook、模型工具事实提交及最终工具UI结果提交。

前端 `renderExecutionEvent` 对 `tool_execution_state` 更新进程status/result，但不设 `ui_committed=true`；最终 `tool_call` 才设置该标记。`renderExecutionRecord` 在工具行有 `ui_committed` 时调用 `autoCollapseToolRowAfterResult`，且保留用户手动展开与待审批例外。自动折叠函数没有固定几秒的计时器。本次漫长空档主要发生在最终工具事件之前。

因此：

- **影响本次Agent执行效率。** after capture仍在 `_execute_one_core` 返回路径，后续结果/模型事实及下次API均要等待。只把前端提前折叠可改善观感，无法省掉扫描等待。
- **折叠动作本身不控制后端。** 如果最终工具事件已经发布后仍显示很久，则需浏览器收帧/渲染端点进一步定位；当前证据不能排除额外客户端尾段。
- **落盘不是本次7.5秒的主项。** 退出状态自身已记账，review索引写4.315ms、模型结果追加12ms，blob写为0。它仍含文件元数据读取/路径解析和扫描，不等于没有I/O。

## 4. 现有达标率的边界及后续优化顺序

第80轮已有严格trace显示 `_execute_one_core` 返回→首次实际HTTP send **335.548ms**，其中返回→工具模型事实提交28.595ms。这个trace仍有效，但起点晚于run_shell的进程退出，也晚于change-review capture；所以本例“指标<500ms”与“看到Exit code后等了约7.6秒”可以同时成立。

应补充“process exit/state ready→最终工具事实提交/发布→下一首次send”口径，并保留现有core-return口径分列，不能直接把两个边界的历史达标率混算。

收益有依据的下一步：先把清单中的Git进程、路径过滤/规范化和sweep合并过滤分别计时；按单次扫描复用解析后的输出根、减少重复路径解析，验证符号链接/junction、删除/忽略状态变化及输出目录排除语义。然后再评估review收尾的线程隔离与UI明确显示“进程已退出、审查处理中”。不能用跳过shell后的工作区审查、取消完整签名、只提前折叠来宣布性能目标达成。

本次为分析与只读定位，没有修改生产运行或前端行为，因此没有执行新的代码回归或请求重启。此前心跳/schema补修不针对本例的review路径，不能把它们称为已解决此等待。

证据：`.analysis/shell-exit-fold-20261102/facts-and-next-request.json`、`exit-window.json`、`inventory-profile.json`，以及同目录提取/只读剖析脚本；保留相关源码SHA256。生产事实来自该会话events/metrics，扫描明细来自terminal日志的11:12:00–11:12:10窗口。

## 5. 用户随后选择关闭全工作区扫描

用户要求关闭这类扫描后，当前store已改为默认 `MYAGENT_CHANGE_REVIEW_WORKSPACE_SWEEP=0`，保留声明路径审查。18:15:56定向刷新插件后，新真实run_shell日志的inventory/signature/sweep均为0；5项独立复核通过，无需再重启。上文§4的减少扫描路径解析是当时建议，本次用户选择直接关闭该覆盖面，不再将其列为当前必须优化的热路径。完整核验与生效证据见[关闭状态报告](change-review-workspace-sweep-disabled-verification-2026-11-02.md)。
