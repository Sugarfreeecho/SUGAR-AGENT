# SSE 管道与断线续看 · 功能方案设计（UseCase 清单）

- 版本：2026-09-13（覆盖至：HEAD `6acc6bf`）
- 用途：逐条审查（四字段格式）。
- 适用实现：`modules/sse-handling.js`（3.6k 行）、`modules/event-dispatch.js`、后端 `runtime_v2_session_stream`。
- 上级：`00-WebUI对话界面整体设计.md`

---

## 1. 功能定位

界面的"生命线"：SSE 事件如何到达、如何续、如何防重复——参数全部显式。

## 2. UseCase

### UC-5C1 实时事件流
- **触发**：会话运行中（含新建未入库会话）。
- **预期现象**：事件按序到达并驱 UI；发送管线锁防止"新旧事件交错"；无事件丢失或重复上屏。
- **依据**：`sse-handling.js`（send pipeline 锁、事件应用）。

### UC-5C2 断线续看
- **触发**：网络闪断/代理切断/后台休眠导致 SSE 中断。
- **预期现象**：自动重连续看——**空闲 120s 触发探测、重连 ≤10 次、退避 0.5s→15s**；从上次游标继续（不丢不重）；次数耗尽后明确提示"刷新页面"。
- **规则与边界**：续看靠后端游标（after_seq/after_index），不是内存重放；提示写入界面日志（error-log）不弹窗轰炸。
- **依据**：`sse-handling.js` 顶部常量（SSE_IDLE_TIMEOUT_MS / STREAM_RECONNECT_MAX_ATTEMPTS 等）、`runtime_v2_session_stream`。

### UC-5C3 观察者重连（多视图）
- **触发**：同一会话在多个视图（主界面/子代理视图）同时打开。
- **预期现象**：各视图独立续看；互不拖垮；开关受 `MYAGENT_ENABLE_STREAM_RECONNECT` 控制。
- **依据**：`streamReconnect` 配置、观察者流设计（webui L190）。

### UC-5C4 事件回放一致性
- **触发**：刷新页面 / 打开历史会话。
- **预期现象**：已渲染内容与历史一致（含已撤销/已恢复类状态）；不发生"重放重复执行"（回放只读）。
- **依据**：`event-dispatch.js`、历史扫描（scanExisting）。

## 3. 边界

- 与"运行日志文件"无关：这里是界面流；
- 网关/服务面细节见 ../08-会话存储RuntimeV2/06。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-5C1 | `sse-handling.js` L40–120（锁） |
| UC-5C2 | 常量区 L1–24 + 重连逻辑 |
| UC-5C3 | `webui.py` L190/1736 |
| UC-5C4 | `event-dispatch.js` |

## 5. 版本记录

- 2026-09-13 v1：拆分首版（承接 UC-505）。
