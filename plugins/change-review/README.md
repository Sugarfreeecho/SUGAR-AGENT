# Change Review（change-review）

逐行查看一次运行改动了哪些文件、哪些行，并可安全撤销 / 恢复；结论直接嵌在聊天流里，不额外开面板。

- 入口：`chat.extension` 槽位渲染（`web/change-review.js` + `change-review.css`），在含有改动的消息下出现。
- 路由：`POST /sessions/{session_id}/change-reviews/undo`、`POST /sessions/{session_id}/change-reviews/restore`（只允许本机同源浏览器调用）。
- 快照：`runtime.py` 作为 `workflow_runtime` 在运行前后捕获 diff；`store.py` 保存逐行结果与撤销所需的原文，按文件 mtime + size 摘要加载，编辑后不会留在旧模块上。
- 目录：`host.py`（路由与动作校验）、`runtime.py`、`store.py`、`web/`。

## 热重载

- 改本目录里的代码或前端 → 设置页「重新发现 / 热重载」即生效，不必重启：`runtime.py` 回调按内容摘要重建，`store.py` 按文件摘要重新加载，`install()` 会先摘掉上一轮注册的同名 `APIRoute` 再注册。
- 判定口径见 [插件热重载](../../docs/plugin_hot_reload.md)。

## 自检

```powershell
python -m pytest tests/test_change_review_plugin.py
```
