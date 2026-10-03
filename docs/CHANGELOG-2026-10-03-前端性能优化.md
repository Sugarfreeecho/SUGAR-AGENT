# 前端性能优化（2026-10-03）

本次优化针对长文本重测、长会话滚动和公共侧栏重复重建。原有未提交功能继续保留。

## 改动

- 流式文本：首尾空白处理只扫描空白前缀；尾窗查找限制在字符预算内，避免为超长单行扫描全文。
- 超过 60,000 字符的完整布局测量拆为 6,000 字符批次，每个任务约 4ms 后让出主线程；MessageChannel 调度避免连续 setTimeout 的延迟累计。不支持 MessageChannel 时使用 setTimeout。
- 保留实际浏览器行盒测量和有界 DOM；测量完成才提交完整高度结果。测量期间允许流式追加，大批输出立即更新最新尾窗；尺寸变化、终态、取消及删除会释放旧任务、测量节点和消息通道。
- 每个流式窗口最多缓存两种布局签名的完整结果，相同文本返回已测宽度时直接复用；窗口结束时清理缓存。
- 执行过程框：CSS 同时计算原有高度上限和工作区高度，不再反复清空样式读取布局。仅可视高度变化时扫描，移除滚动监听，批量更新共用一次工作区测量。
- 公共侧栏：外观未变化的窄态条目复用 DOM；回调更新无需重建按钮，点击时读取最新动作。
- 改动审查：一帧共用用户轮次查询，二分定位正在查看的轮。4,096 条用户消息的回归用例最多读取 13 个消息位置；贴近底部直接选最后一轮。

## 本机对比

使用 Edge 无头浏览器、1100×800 视口，对比优化前工作区快照与优化后源码。流式场景为 300,000 字符、每批 1,000 字符、300 次更新，重复三次取累计耗时中位数。其余数值为隔离场景测量，不能等同于整页响应时间。

| 项目 | 优化前 | 优化后 |
| --- | ---: | ---: |
| 分行流式累计耗时 | 1221.5ms | 1167.5ms |
| 单行流式累计耗时 | 798.8ms | 730.7ms |
| 300,000 字符重测同步调用 | 76.6ms | 1.7ms |
| 3,000,000 字符重测同步调用 | 641.7ms | 1.2ms |
| 3,000,000 字符重测完整完成 | 651.0ms | 741.4ms |
| 优化后重测最大单批耗时 | — | 7.8ms |
| 200 个展开框重复高度计算中位数 | 15.3ms | 0.7ms |

重测总工作仍随文本长度增长；分批让出主线程的重点是降低持续阻塞，首次完整测量总时间可能略增。普通短文本保持同步测量；已有宽度的精确缓存可避免重复工作。

## 验证与复跑

- 浏览器回归：全文渲染作为独立高度参照，覆盖多百万字符、折行、字体/宽度/显隐变化、测量中的追加、任务取消、最新尾窗和缓存复用。
- 交互回归：滚动不扫描高度、不重复写样式；工作区缩放保留原有上限；窄态按钮复用后调用最新回调；长历史选轮结果与原先线性查找相同。
- 相关流式、执行过程、侧栏、插件、改动审查与主题测试共 113 项通过；最终头窗查找调整后，17 项浏览器几何回归再次通过。生产构建和源码/构建产物一致性检查通过。

```powershell
.\python\python.exe -m pytest tests/test_llm_stream_window_geometry.py tests/test_frontend_performance_browser.py tests/test_process_aggregate_ui.py tests/test_process_aggregate_performance.py tests/test_public_sidebar.py tests/test_plugin_ui_frontend.py tests/test_frontend_session_stream_runtime.py tests/test_smooth_stream_runtime.py tests/test_frontend_theme_variants.py tests/test_change_review_plugin.py -q
.\python\python.exe -X utf8 scripts/benchmark_frontend_performance.py --baseline-dir .sugaragent/ui-performance-baseline
.\python\python.exe -X utf8 scripts/check_frontend_dist_sync.py
```

基线目录为本次优化前复制的本地源码快照，不入库；在其他环境复跑需要提供对应版本的 `session-scroll-history.js` 和 `message-rendering.js`。
