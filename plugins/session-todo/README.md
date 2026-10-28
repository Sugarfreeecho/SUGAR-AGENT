# Session Todo（session-todo）

会话级计划面板：把「这轮要做哪几件事、做到哪一步」显示在会话里，模型用 `update_todo` 维护，用户能一眼看到进度。

- 工具：`update_todo`（整表替换，状态为 `pending` / `in_progress` / `completed`）。
- 面板与徽标：`session.panel` 的「当前计划」显示完成数 / 总数与条目；面板上有「清除」（`set_state`，带确认）；徽标在有计划时出现。
- 存储：数据就是通用的扩展状态（`plan` 命名空间），没有额外数据库。
- 目录：`host.py`（工具注册）、`runtime.py`（`workflow_runtime` 回调）、`web/`（面板渲染与样式）。

属于 `system` 级插件：设置页不显示，随宿主常开。

## 热重载

- 改本目录里的代码或前端 → 设置页「重新发现 / 热重载」即生效，不必重启：工具按内容摘要换新模块，`runtime.py` 回调按摘要重建，面板脚本走 `?v=<摘要>`。
- 判定口径见 [插件热重载](../../docs/plugin_hot_reload.md)。
