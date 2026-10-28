# Execution Tools（execution-tools）

后台任务与持久终端：模型可以起长任务、回收输出、杀任务，也可以开一个跨轮复用的终端。

- 工具：`job_output`、`job_list`、`job_kill`，以及 `terminal_*`（open / send / read / signal / close / list）。
- 路由：`/api/execution/capabilities`、`/sessions/{session_id}/jobs*`、`/sessions/{session_id}/terminals*`（读写都校验本机同源）。
- 控制台：详情栏「执行与终端」插件页面，或独立 `/plugins/execution-tools?session=<id>`，显示后台任务、终端与 Computer Use 状态。左侧不再提供「执行」页签。
- 生命周期：`start()` 拉起通知 runner 并恢复上次的 owner；`stop()` 停 runner，并关闭该服务的运行中任务与终端（停用插件会打断正在跑的任务，这是刻意行为）。

## 热重载

- 改本目录里的代码或前端 → 设置页「重新发现 / 热重载」即生效，不必重启：`install()` 会先摘掉上一轮注册的同名 `APIRoute` 再注册，`start()` / `stop()` 重建服务侧 runner。
- 判定口径见 [插件热重载](../../docs/plugin_hot_reload.md)。

控制台复用原执行面板的输出、停止、用户终端创建/输入/结束、Agent 终端历史及 Computer Use 设置。终端使用本地构建的 `/assets/terminal-runtime.js`，独立页面也可连接；隐藏页面暂停 SSE，返回时从原输出 offset 重连。关闭视图仅释放连接，只有「结束」会关闭用户终端。

## 自检

```powershell
python -m pytest tests/test_plugin_execution_lifecycle.py tests/test_execution_services.py
```
