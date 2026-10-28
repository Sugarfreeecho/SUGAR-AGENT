# Desktop Notifications（desktop-notifications）

无人值守会话结束或需要用户处理时，发一条系统通知。插件只做一件事：向 `notification_providers` 注册一个通知提供方。

- 路由：无。前端入口：无（通知由宿主在会话完成 / 需要关注时触发）。
- 注册：`install()` 与 `start()` 各注册一次（宿主的 lifespan 可能在同一解释器里重启），`stop()` 注销，全部带 `replace=True`，重复注册安全。
- 开关：`MYAGENT_UI_CLOSED_NOTIFY=0` 可关闭网页关闭时的通知（测试进程默认关闭）。

## 热重载

- 改本目录里的代码 → 设置页「重新发现 / 热重载」即生效，不必重启：旧提供方按 `stop()` 注销，新模块 `start()` 立刻重新注册，不存在两份回调。
- 判定口径见 [插件热重载](../../docs/plugin_hot_reload.md)。
