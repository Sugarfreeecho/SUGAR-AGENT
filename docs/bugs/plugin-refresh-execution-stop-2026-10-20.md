# 插件刷新导致执行会话被误停

## 定位

问题报告中的触发链可由当前代码复现：插件启停、安装、卸载或重新加载调用
`webui.refresh_web_plugin_lifecycle()`，原先的
`start_bundled_host_extensions()` 会先停止全部宿主扩展。
execution-tools 的停止回调从全部历史 job、terminal 收集 owner，随后调用
`stop_owner(..., reason="execution_tools_disabled")`。只有已完成或已取消任务的
会话也会进入 `suppressed`，从而拒绝后续 shell 和模型终端执行。

该路径只改变执行层状态，不会向 agent 主循环发送用户中断，因而会出现
shell 被拒绝而文件等工具仍继续执行的现象。

需要区分两种启动：插件 stop/start 通常复用仍存活的执行服务线程，
`ExecutionService.start()` 此时立即返回；真实 shutdown/start 才创建新线程。
因此仅在服务 `start()` 中清空集合无法修复插件停启路径。

报告中的 245b00fc 会话目录及 web-search-providers 状态记录不在本次工作区中，
事发时间取自用户报告；本次确认依据为代码核对及独立回归复现。

## 修复

- `app/plugins/host.py` 按 plugin ID、内容签名增量协调生命周期，保留无变化的
  扩展，仅停止被禁用、移除或更新的扩展。生命周期操作串行化，避免并发刷新
  重复启动；每次成功启动立即记账，避免后续插件启动失败造成资源失管。
- `plugins/execution-tools/host.py` 只从 ACTIVE job、运行中的 terminal、仍在
  启动的 terminal 收集需要清理的 owner，忽略历史资源。
- `app/execution_services/jobs.py` 按原因记录执行抑制和终端关闭状态。
  execution-tools 重新启用仅解除 `execution_tools_disabled` 原因，保留用户
  主动停止、会话删除、权限变化等其他原因。新的人类消息仍通过原有
  `resume_execution()` 路径恢复对应会话。
- 真实服务线程重启清理上一生命周期的停止集合和原因；存活线程上的幂等
  `start()` 保留已有停止状态。

重新启用不会重放已取消命令，也不会恢复已关闭的旧终端。正在运行的宿主需要
重启一次以加载本次 Python 代码。

## 验证

新增 `tests/test_plugin_execution_lifecycle.py`：18 项通过。修复前首批 13 项中
12 项失败，修复后全部通过，随后加入终端和 API 路径验证。

覆盖真实子进程在无关插件刷新后的存活、completed/failed/killed 历史任务、
无 job 的模型与用户 PTY、终端启动中禁用、已关闭历史终端、显式停止与删除
状态保留、服务真实重启、插件更新、部分启动失败、并发刷新，以及插件开关
API 到真实刷新函数的调用链。通知 runner 和持久化配置入口在测试中隔离，
不切换用户的实际插件设置。

现有相关测试另外 49 项通过：

```powershell
.\python\python.exe -m pytest tests/test_plugin_execution_lifecycle.py -q
.\python\python.exe -m pytest tests/test_execution_services.py tests/test_bundled_host_extensions.py tests/test_execution_integration.py tests/test_execution_api.py tests/test_plugin_background_services.py tests/test_host_catalog_availability_scope.py tests/test_settings_package_import.py -q
```

修改文件的 `git diff --check` 通过。
