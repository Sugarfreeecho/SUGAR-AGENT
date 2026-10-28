# Computer Use（computer-use）

桌面操作能力的开关与状态面板。插件本身只做三件事：读状态、按配置连接/断开、把可用的 Computer Use 工具挂进工具目录；真正操作桌面的是原生驱动或 MCP 服务。

- 路由：`GET /api/computer-use`（状态、当前 MCP 服务列表、插件是否启用）、`POST /api/computer-use`（`enabled` 布尔 + `provider` / `server_alias` / `allow_existing_profile`）。
- 工具：`tool_definitions` 只在 manager 处于 `ready` 时返回 manager 的 catalog；工具的执行落在 `computer_use/`（原生驱动）或 `cua-driver-mcp` 这个 MCP 服务上。
- 生命周期：`start()` 按已保存的配置重连，`stop()` 在服务仍存活时主动断开，避免插件停用后还握着桌面会话。
- 目录：`host.py`（路由与工具声明）、`computer_use/`（manager、策略、结果封装）。

## 热重载

- 改本目录里的代码 → 设置页「重新发现 / 热重载」即生效，不必重启：新模块会重建 manager，`install()` 先摘旧路由再注册，`stop()` 负责收尾旧的桌面连接。
- 判定口径见 [插件热重载](../../docs/plugin_hot_reload.md)。

## 自检

```powershell
python -m pytest tests/test_computer_use_plugin_migration.py
```
