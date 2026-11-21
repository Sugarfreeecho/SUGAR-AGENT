# Goal 阶段卡在「续跑已排队」— 会话 ef57474e 诊断报告

日期：2026-11-12（本地 +08:00）
会话：`ef57474e-47cf-5f52-86a6-241207da4871`（小Sugar助手-微信、QQ、飞书连接）
Goal：`goal_a0073243d6b542c4`，status=active，current_run_id=null
结论：**不是界面卡住，也不是模型没响应**。一条 `session.continue` 操作在宿主重启后永久停在 `running`，goal 后续每次续跑都被 `_coalesce_key` 合并到这条僵尸操作上，于是既起不了新 run，阶段又永远停在 `queued`。

## 1. 现象

- `GET /sessions/ef57474e-.../goal/progress` 返回
  `phase=queued`、`label=续跑已排队`、`since=1794410993.165`（= 2026-11-11 23:29:53）
  `run_id=control-d866f132-...`、`operation_id=d866f132-...`
- 从 23:29:53 到 2026-11-12 10:07 约 10.6 小时，该阶段与 `since` 从未变化。
- 期间该会话实际发生过 7 次真实 `chat` run（16:04Z、16:30Z、16:32Z、16:47Z、00:58Z、01:31Z、01:55Z），
  包括最近一次 `b93d7f43`（09:55:55–10:02:14，正常产出），界面仍显示「续跑已排队」。

## 2. 关键证据

### 2.1 控制层操作表（`%LOCALAPPDATA%\SugarAgent\session-control\control.sqlite3`）

| 字段 | 值 |
| --- | --- |
| id | `d866f132-298c-48c3-95e0-5973f7b404fa` |
| principal | `host:agent-goal` |
| method | `session.continue` |
| status / delivery | `running` / `pending`（唯一一条非终态 continue） |
| run_id | `control-d866f132-298c-48c3-95e0-5973f7b404fa` |
| created / updated | 23:27:10 / 23:27:10（此后从未推进） |
| `_coalesce_key` | `agent-goal:session.continue:ef57474e-47cf-5f52-86a6-241207da4871` |

对照组：`87e9f6e9-...` 也是一条 `session.continue`，但 principal 是 `host:execution-tools`（job-wakeup），
key 不同，已正常落到 `coalesced`，与本问题无关。

### 2.2 运行时状态

- `runtime_observability.json`：`control-d866f132-...` 状态 `stale`，心跳停在 `15:28:05Z`，
  `stale_reason="heartbeat older than 90s"`，`finished_at=15:29:50Z`。
- 宿主进程 pid 4516（python）启动时间 **23:28:18**，即该 run 执行期间宿主重启过。
- `metadata.json` 的 `active_run_id` 在重启时仍是 `control-d866f132-...`，`active_run_fence.json` 由旧进程持有。
- 目标侧：`current_run_id=null`、`status=active`、`blocked_streak=1`（blocker `im-credentials`），
  因此 `should_continue()` 一直为 True，调度器每轮都会尝试续跑。

## 3. 根因链

1. 23:27:10 创建 `session.continue` 操作 `d866f132`，23:27:11 起 run `control-d866f132`，状态 `running`。
2. 23:28:18 宿主重启。`session_control/service.py:805-814` 的启动对账只跑一次，且条件是
   `not deps.is_stream_active(session)`；重启瞬间该会话仍被判为流活跃，于是这条 `running` 操作被跳过。
   之后没有任何补做的对账，操作永久悬挂。
3. 23:29:50 运行时以「心跳超 90s」把该 run 判为 `stale`，goal 记为中断并把 `current_run_id` 置空；
   23:29:53 goal runner 重新入队（`_set_progress(sid,'queued')`），`session.continue` 被
   `store._admit`（`store.py:129-131`）按 `_coalesce_key` 命中那条僵尸操作并原样返回，**不会创建新 run**。
4. 阶段无法推进，三处逻辑叠加：
   - `runner._set_progress`（`runner.py:33-47`）对 `queued → queued` 视为“同一阶段”，保留旧 `since`；
   - `runner._observe_progress`（`runner.py:50-66`）只在事件 `run_id` 等于记录的 `run_id` 时才推进阶段，
     而僵尸操作对应的 run 永远不会再发事件；
   - `runner.progress_snapshot`（`runner.py:68-105`）只有在**完全没有阶段记录**时才回落到 `running`，
     所以真实在跑的 chat run 也无法纠正显示。

结果：UI 永久显示「续跑已排队（10 小时+）」，同时该会话的 goal 续跑链被彻底堵死——不是显示问题，是功能问题。

## 3.1 引入时间线（git 追溯）

| 时间 | 提交 | 引入的缺陷 |
| --- | --- | --- |
| 2026-08-28 | `5b8fbcb` feat(plugins): host services, web gateway and built-in feature plugins | goal runner 初版，用本地 reserve token 起续跑 |
| 2026-09-20 | `48afe4f` fix(goal): guard against duplicate continuation runs | 防重靠 `_has_local_worker_activity` + 30s 恢复宽限（**存活判断**） |
| 2026-10-29 02:04 | `388cd13` feat(control): session control service, automation and scheduled tasks | ① `_coalesce_key` 合并（`store.py:129-133`）；② 启动对账只跑一次且用 `is_stream_active` 门控（`service.py:805-814`） |
| 2026-10-29 02:12 | `5f7dd46` feat(plugins): bili, feishu, goal/team and computer-use updates | **回归点**：`_continue` 改用 `session.continue(..., coalesce=True)`，并把原来的本地活跃检查换成 key 合并——防重从此只看 key、不看 run 是否存活 |
| 2026-11-04 22:05 | `614ea88` feat(plugins): goal, team, monitor, web tools and change-review updates | `_set_progress`/`progress_snapshot`：queued→queued 保留旧 `since`，无记录才回落 `running`——排队状态被冻结且无法被真实 run 纠正 |

- 首次实际触发：2026-11-11 23:27–23:29（宿主在续跑 run 执行中重启，23:28:18 启动对账把该会话误判为流活跃而跳过）。
- 10-29 到 11-11 共 13 天未暴露：需要“续跑进行中重启宿主 + 目标仍 active”同时成立；控制库全局仅此 1 条非终态 `session.continue`，属于低频竞态而非高频故障。
- 版本号：`plugins/agent-goal/.myagent-plugin/plugin.json` 一直为 `1.0.0`，无 tag 可对应发布批次。

## 4. 建议的修复（未实施）

### 4.1 立即解卡（二选一）

- 最轻：在**该会话无活跃 run**时重启宿主。启动对账此时 `is_stream_active=false`，会把该操作收口为
  `unknown / process_interrupted`，下一次 tick 即可重新 admit。
- 直接改数据：把该行置为终态（先在宿主停止或确认无续跑时执行）
  ```sql
  UPDATE operations
     SET status='unknown', delivery='pending',
         error='{"code":"process_interrupted","message":"stale continuation from previous process"}',
         updated=strftime('%s','now')
   WHERE id='d866f132-298c-48c3-95e0-5973f7b404fa';
  ```

### 4.2 防复发（代码）

1. `app/session_control/service.py:805-814`：启动对账不要只做一次。首次 monitor tick 之后再补一轮，
   或把判断从 `is_stream_active` 改为“该 run 是否有新鲜心跳 / 是否仍持有 run fence”，避免重启瞬间误判。
2. `app/session_control/store.py:129-131`：coalesce 命中 `running` 操作时校验其 run 是否仍存活
   （observability 仍 `running` 或有 fence）；僵尸操作不应再被返回，应就地收口后新建。
3. `plugins/agent-goal/runner.py:33-47`：`queued → queued` 时若 `operation_id/run_id` 变化或
   `since` 超过阈值（如 90s），应刷新 `since`，避免把“重试”显示成“同一排队”。
4. `plugins/agent-goal/runner.py:68-105`：为 `queued/preparing` 增加过期兜底——
   超过阈值且宿主有活跃 run 时回落 `running`，无活跃 run 时回落 `waiting`。
5. `plugins/agent-goal/runner.py:232-263`：`_continue` 拿到操作后校验 `operation['status']`；
   若为终态或 `run_id` 与活跃 run 不一致，不要把它写进阶段记录，并触发一次对账。

### 4.3 回归用例

- `tests/test_goal_panel_resume_browser.py` 已覆盖 `queued → preparing → model_wait → finishing`，
  建议补一条：**coalesce 到已中断操作时，阶段必须在阈值内离开 `queued`**。
- `tests/test_agent_goal.py`、`tests/test_session_path_scope_owner.py` 可加“重启后 running 操作被收口”的断言。

## 5. 复核命令

```powershell
# 阶段快照
Invoke-RestMethod "http://127.0.0.1:8192/sessions/ef57474e-47cf-5f52-86a6-241207da4871/goal/progress"

# 僵尸操作
python -c "import sqlite3,os;c=sqlite3.connect(os.path.join(os.environ['LOCALAPPDATA'],r'SugarAgent\session-control\control.sqlite3'));print(c.execute(\"select id,status,delivery,run_id,datetime(created,'unixepoch','localtime') from operations where session_id='ef57474e-47cf-5f52-86a6-241207da4871' and status not in ('succeeded','failed','stopped','interrupted','unknown','cancelled','coalesced','rejected')\").fetchall())"
```

## 6. 说明

按用户要求，本次**未修改任何线上数据或代码**，仅只读排查；`get_goal` 在本会话无 goal（返回 null），
上述状态均来自目标会话自身的存储与接口。

## 数据来源

- `control.sqlite3`（`C:\Users\Sugarfreeecho\AppData\Local\SugarAgent\session-control\control.sqlite3`）操作记录
- `workspace/sessions/ef57474e-.../runtime_observability.json`、`metadata.json`、`active_run_fence.json`、`events.jsonl`
- `GET http://127.0.0.1:8192/sessions/ef57474e-.../goal` 与 `/goal/progress`
- 代码：`app/session_control/service.py`、`app/session_control/store.py`、`app/session_control/public.py`、
  `plugins/agent-goal/runner.py`、`plugins/agent-goal/host.py`
- 进程信息：`Get-Process -Id 4516`（python，启动于 2026-11-11 23:28:18）
