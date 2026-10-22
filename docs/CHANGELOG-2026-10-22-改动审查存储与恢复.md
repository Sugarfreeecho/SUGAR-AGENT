**改动审查：存储、故障提示与中断恢复（2026-10-22）**

完成两批修复：第一批贯通故障状态、外置大 diff；第二批外置 baseline 清单、恢复已结束执行留下的 pending。保留历史 UI 事件的全文 diff 协议，以及撤销、恢复、分支复制和事件重试行为。

面板继续按需显示：有可展示的改动或记录失败时显示，初始未检查、确认无改动时隐藏。失败提示不会被另一个并发工具的成功覆盖；会话切换及查看其他用户轮时，状态各自隔离。部分覆盖信息随对应工具状态保存，有改动行时可展示。

存储格式升级为 v2，首次访问旧会话时迁移，避免启动时遍历全部会话。先提交内容 blob，再原子替换索引和版本号；迁移中断时旧索引保持可读，可再次尝试。

- 超过 **512 UTF-8 字节**的 diff 保存为 gzip blob，索引使用 `diff_blob` 引用。极小 diff 保留内联，避免普通一行编辑增加一个文件及一次 fsync。大小上限按字节判断。
- GC 同时保留记录、待交付事件及操作结果引用的 diff；分支复制会复制所需 diff 内容。历史事件和撤销/恢复的幂等结果仍按原协议返回全文 diff。
- 新 baseline 的清单存入已有 ZIP 的独立 manifest entry，共用既有提交，主索引只保存引用与校验和。迁移的旧清单使用独立 blob。清单按需加载，缓存限定为 8 份。
- 撤销/恢复会在改动文件前验证 diff 和快照内容。损坏的 baseline manifest 在扫描工作区前报错，避免反复支付无效扫描开销。Git 清单命令失败也会进入可见故障状态。
- 热索引读取直接打开文件并处理不存在的情况，省去每次读取前重复的存在性查询。

pending 不按固定年龄删除。新捕获记录进程 PID、进程启动时间、执行身份和创建时间，恢复依据是执行器已退出、已被确认不活动，或工具已经经过 finally 边界而事后记录失败。活跃工具、外部活跃进程和无法确认的执行受到保护。

恢复时先生成可撤销的记录，并把变更及诊断放入持久 outbox，再移除 pending；宿主提交 UI 事件成功后才确认 outbox。旧数据缺少事前快照时，会生成明确的恢复失败事件。被 pending 或 deferred sweep 引用的 baseline 不会提前释放。恢复较早的非 Git 捕获时，也会保留最早的文件来源。

异常处理统一到每次工具调用独立的 `ChangeReviewCapture`，覆盖原生、宿主和插件工具。批量 flush 的故障使用同一 UI 事件链路，重复失败去重，重试成功后清除对应批次故障。健康工具状态随既有工具事件提交，不另加一次持久化写入。

主要实现文件：`plugins/change-review/store.py`、`runtime.py`、`host.py`、`web/change-review.js`、`web/change-review.css`、`app/change_review_capture.py` 和 `app/agent_loop.py`。HTTP 与工具捕获使用同一个 store 模块和会话锁。前端构建产物已经重建，同步检查脚本也固定使用 UTF-8 解码构建输出。

验证包括 179 条相关回归，以及浏览器中的错误独立展示、初始隐藏、恢复后隐藏、切换轮次、过期事件隔离和错误文本转义。新增存储测试覆盖迁移中断、并发迁移、GC、分支复制、历史重试、损坏内容、活跃 pending 保护、恢复后的撤销及事后记录重试。最后的索引读取调整另通过了 78 条定向回归。测试记录保存在 `workspace/TempOutput/change-review-fix-20261022/regression.xml`。

另外，在两份当前真实会话的隔离副本中核验了 596 条记录元信息、537 份仍保留的 diff 和两份 baseline 清单；迁移前后一致。已经升级的会话使用重建的 v1 测试输入，已退役并被 GC 的内容按既有策略处理；测试不对原会话执行迁移或撤销。结果见同目录 `migration-validation.json`。

性能对照使用任务开始时保存的 store.py，所有真实会话只复制索引，在隔离目录迁移和读写；没有用测试修改真实会话或项目文件。A/B 顺序交替，保留 fsync；合成工具对照固定相同文件清单，隔离 Git 启动时间。绝对延迟受当时机器负载影响，不能与原报告其他日期的采样直接相减。

真实会话副本、每侧 30 次读写的结果：

| 会话 | 索引体积 | 读取 p95 | 写入 p95 |
|---|---:|---:|---:|
| a874ad4d | 24.07 → 0.55 MiB | 339.9 → 27.3 ms | 366.4 → 28.9 ms |
| 06345307 | 16.72 → 0.16 MiB | 1029.8 → 28.6 ms | 811.0 → 16.7 ms |

首次访问还包含一次迁移：上述两份副本分别约 1.82 秒和 1.26 秒，后续访问不重复迁移。这是格式转换成本，不应与迁移后的纯读取延迟混为一谈。

详细对照记录：`workspace/TempOutput/change-review-fix-20261022/final-benchmark.json`；额外的小会话交替对照及配对样本保存在同目录 `small-session-final.json`。可复用 `scripts/benchmark_change_review_storage.py` 运行相同类型的隔离测试。性能验收同时查看小会话的普通编辑、无改动调用和三工具批次，避免只用大历史索引的收益代表全部场景。

最终小会话对照如下。无改动和普通编辑每侧 60 次，三工具批次另扩充至每侧 200 次；各行只比较同轮 A/B，不能跨行比较绝对耗时：

| 场景 | p50，改前 → 改后 | p95，改前 → 改后 |
|---|---:|---:|
| 无改动 Shell 审查 | 20.1 → 19.8 ms | 24.0 → 23.7 ms |
| 普通文件编辑 | 43.4 → 42.1 ms | 52.4 → 51.9 ms |
| 三工具批次 | 131.2 → 130.8 ms | 152.2 → 149.5 ms |

此前 60 次批次短测的 p95 曾有 164.8 → 185.1ms 波动；扩充至 200 对后的 p95 如上，配对中位数比值的 bootstrap 95% 区间约为 0.986–1.000，没有观察到稳定的性能回退。单次最大延迟仍有环境噪声，不承诺所有调用都更快。原始 200 对样本保存在 `batch-tail-validation.json`。

回归命令：

```powershell
.\python\python.exe -m pytest tests/test_change_review_plugin.py tests/test_change_review_compact_store.py tests/test_change_review_diagnostics.py tests/test_change_review_status_browser.py tests/test_change_review_ui_payload_runtime.py tests/test_agent_loop_runtime_v2.py tests/test_agent_extensions_integration.py tests/test_plugin_ui_frontend.py tests/test_sidebar_runtime_footer.py -q
node tests/js/change_review_visibility_runtime.mjs
node tests/js/change_review_stats_runtime.mjs
node tests/js/change_review_ui_payload_runtime.cjs
.\python\python.exe scripts/check_frontend_dist_sync.py
```

生效时使用更新后的后端进程；旧会话将在该进程首次访问时迁移。面板脚本按更新后的插件资源加载。
