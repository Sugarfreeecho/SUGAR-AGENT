# Game Arena（game-arena）

让两个会话在同一个对局里下棋：五子棋（9–19 路）与围棋（9/13/19，含提子、打劫、禁入、停一手与数子）。

- 运行形态：`runtime: python` 的独立 worker 进程（`plugin.py`），工具调用走 worker RPC，不占用宿主事件循环。
- 工具：`gomoku_create` / `gomoku_join` / `gomoku_place` / `gomoku_view` / `gomoku_list` / `gomoku_surrender`，`go_create` / `go_join` / `go_place` / `go_pass` / `go_view` / `go_list` / `go_surrender`，以及跨棋种的 `game_view`。
- 页面：`web/`（`web.api=true`，请求经宿主网关代理到 worker）。
- 设置：`default_board_size`（新建对局默认棋盘大小，9–19，默认 15）。
- 目录：`plugin.py`（工具与对局入口）、`engine/`（五子棋与围棋规则）、`render.py`（棋盘渲染）、`storage.py`（对局持久化）。

## 热重载

- 改本目录里的代码或前端 → 设置页「重新发现 / 热重载」即生效，不必重启：worker 进程会整体重启（旧进程关闭、新进程按新代码拉起），对局状态来自 `storage.py` 的落盘数据，不会随进程丢失。
- 判定口径见 [插件热重载](../../docs/plugin_hot_reload.md)。

## 自检

```powershell
python -m pytest tests/test_game_arena_plugin.py
```
