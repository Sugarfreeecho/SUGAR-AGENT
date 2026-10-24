# Thread Monitor（线程监控）

只读面板：把「进程真实 OS 线程数」与「Agent 运行态并发量」并排放在一起，用来发现线程池泄漏，以及看线程数与业务并发是否匹配。

## 打开方式

- 直接访问 `http://127.0.0.1:<端口>/plugins/thread-monitor`
- 或在 **设置 → 扩展 → 插件页面与设置** 里点「线程监控」（该入口来自本插件的 `ui.navigation` 声明）

改动不会热生效到已运行的进程：**重启 Agent 后插件才加载**（插件本身由宿主在启动时发现并安装路由）。

## 面板上的两组指标

| 组 | 含义 | 数据来源 |
| --- | --- | --- |
| 进程 OS 线程 | 本进程当前真实线程数、按创建来源折叠的分组、累计 CPU、存活时长 | `psutil.Process().threads()`，并用 `threading.Thread.native_id` 关联出线程名与 daemon 标记 |
| 业务并发 | 根会话 run、子代理 run、后台任务、PTY 终端、Agent Team 会话 | `session_lifecycle` 的 run 注册表、`agent_subagent.subagent_registry`、执行服务的 job/terminal 表、`agent_team.service` |

另有两项辅助数字：

- **待处理交互**：`human_interaction` 侧的提问 + 审批计数（不计入并发总数）。
- **线程 / 并发**：每个活动运行平均占用多少线程，明显偏高说明有线程没有随 run 释放。

## 怎么判断「疑似泄漏」

- 线程分组里某一组的计数随每次 run 单调上升，且 run 结束后不回落 → 该池在泄漏。
- 「疑似长存活线程」列出存活时间超过阈值的线程（默认 300s），按存活时长倒序。
- 「峰值 / 基线」给出进程启动以来的最高值与首次采样值；点「重置峰值」只清空本面板的统计，不动 Agent。

线程名折叠规则：只折叠**末尾纯数字**索引，所以 `myagent-llm-request_3`、`execution-io_7`、`pending-counts_0` 会分别归到 `myagent-llm-request_*`、`execution-io_*`、`pending-counts_*`；带随机十六进制后缀的名字与 `MainThread` 原样保留。

## 只读 API

```
GET  /api/thread-monitor?history=120    # history 取值 1..600
POST /api/thread-monitor/reset          # 只重置本面板的基线与峰值
```

`GET` 返回：

```json
{"ok": true, "data": {
  "timestamp": 1761..., "thread_total": 42, "delta_threads": 2,
  "peak_threads": 51, "baseline_threads": 38,
  "thread_groups": [{"group": "myagent-llm-request_*", "count": 8, "cpu_seconds": 12.3}],
  "threads": [{"thread_id": 12345, "name": "myagent-llm-request_3", "group": "myagent-llm-request_*", "daemon": true, "cpu_seconds": 1.2}],
  "concurrency": {"root_runs": 1, "subagent_runs": 2, "background_jobs": 0, "terminals": 1,
                  "pending_interactions": 0, "active_team_sessions": 0, "total": 4, "sessions": []},
  "history": [{"timestamp": 1761..., "thread_total": 42, "concurrency_total": 4}],
  "suspected_leaks": [{"thread_id": 12345, "name": "...", "group": "...", "alive_seconds": 420.5}],
  "process": {"pid": 1234, "num_threads": 42, "uptime_seconds": 3600.2, "rss_mb": 512.4},
  "errors": [], "running": true,
  "interval_seconds": 1.0, "leak_suspect_seconds": 300.0, "threads_per_run": 10.5
}}
```

两条约束写进了实现，改动时请保留：

1. **不创建宿主状态。** 采样只读 `sys.modules` 里已经存在的模块与单例，绝不因为「数一下」而首次 import `agent_harness`（那会全量扫描会话目录，实测数秒）或构造执行服务。
2. **不碰 Agent 状态。** 除了本面板自己的基线与峰值，代码里没有任何写操作。

## 环境变量

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `THREAD_MONITOR_INTERVAL_SEC` | `1.0` | 后台采样间隔，下限 0.25 |
| `THREAD_MONITOR_HISTORY` | `600` | 内存里保留的采样点，下限 60 |
| `THREAD_MONITOR_MAX_THREADS` | `200` | 每帧最多返回的线程明细条数 |
| `THREAD_MONITOR_LEAK_SEC` | `300` | 判定「疑似长存活」的存活秒数，下限 30 |
| `THREAD_MONITOR_SKIP_CONCURRENCY` | 空 | 置 `1` 时跳过并发探测，仅用于隔离排查 |

## 自检

```powershell
python -m py_compile "plugins\thread-monitor\monitor.py" "plugins\thread-monitor\host.py"
node --check "plugins\thread-monitor\web\app.js"
python scripts\selfcheck_thread_monitor.py          # 线程侧 27 项断言
python scripts\selfcheck_thread_monitor.py --full   # 同时探测宿主注册表
```

## 已知边界

- 只统计**本进程**。`execution-services` 的后台任务虽然跑在独立线程里，仍属于本进程，能被看到；子进程（PTY 里的 shell、外部 CLI）不在统计内。
- 由原生库创建、没有对应 Python 对象的线程统一显示为 `tid-<id>`。
- 并发表里的会话名来自 `session_manager.index`（内存），因此只覆盖当前进程已知的会话。
