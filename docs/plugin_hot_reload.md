# 插件热重载

改插件目录里的文件后，到底要不要重启 SugarAgent？答案看**改的是哪一层**。这份文档是唯一口径，各插件 README 与 Skill 都指向这里。

## 怎么触发

**设置 → 扩展 → 插件 → 「重新发现 / 热重载」**，等价于 `POST /api/extensions/reload`。插件开关（停用 → 启用）走同一条对账路径，效果相同。

重载不是原子操作：宿主会停止并重建该插件的 MCP 服务、工作流回调、后台任务和 worker 进程，期间工具会有 1~2 秒空窗（实测 MCP 工具数 20 → 0 → 20）。

## 会生效的层

| 层 | 生效方式 | 生效时机 |
| --- | --- | --- |
| `web/` 前端资源 | 按内容签名加 `?v=` 直接读盘 | 刷新页面即可 |
| `plugin.json`（名称、设置 schema、UI 声明） | 重新发现后重建目录 | 立即 |
| Skills / Hooks / MCP 配置 / 命令 | 扩展缓存失效后重建 | 下一条消息或下一次 Agent 边界 |
| `host.py` 工具（`tool_definitions`） | 宿主按 `content_signature` 加载新模块 | 下一轮对话 |
| `host.py` HTTP 路由 | `install()` 先摘同路径旧 `APIRoute` 再注册 | 重载后立即 |
| `runtime.py` 工作流回调 | 模块名带内容摘要 | 重载后立即 |
| `start()` / `stop()` 里的常驻服务 | 按签名对账，先停旧再起新 | 重载后立即 |
| `runtime: python/node` 插件（如 game-arena） | 独立 worker 进程重建 | 重载后立即 |

## 仍然需要重启

1. **宿主核心代码**：`app/*.py`（`webui.py`、`agent_extensions.py`、`plugins/host.py`、`plugin_host_services.py` 等）。插件重载只换插件自己的模块，不会重新导入宿主。
2. **`.env`**：环境变量只在进程启动时由 `agent_harness` 读取一次，改完必须重启（`web-search-providers` 的设置页会同时写 `.env` 和 `os.environ`，是例外）。
3. **宿主 Python 依赖**：往宿主环境新装包后，若导入失败才需要重启。

另外，插件 `host.py` 里 import 的宿主模块（`app/acp_bridge/`、`app/agent_team/`、`app/agent_goal.py`、`app/execution_services/` 等）仍属宿主代码：插件重载只换插件自己的文件，改这些模块要重启。

## 每个插件的路由清理

`include_router` 会**复制** `APIRoute` 对象，而 FastAPI 先注册先匹配，所以「重新执行 `install()`」并不足以换掉旧处理器——必须显式摘掉旧路由。bundled 插件都按路径清理：

```python
from fastapi.routing import APIRoute

stale_paths = {route.path for route in router.routes}
app.router.routes[:] = [
    route for route in app.router.routes
    if not isinstance(route, APIRoute)
    or getattr(route, "path", "") not in stale_paths
]
app.openapi_schema = None
app.include_router(router)
```

只清 `APIRoute`：`sugar-bili-scroll` 的 MCP 网关是 `app.mount` 的 `Mount`，路径同在前缀下，按前缀清会把它一起删掉，而它的 `install()` 发现 `app.state` 已存在就不会再挂。

回归测试见 `tests/test_plugin_route_reload.py`：每个适配器用两个不同摘要各装一次，同一「路径 + 方法」必须只剩一份。

## 已知代价

- 每轮重载都会在 `sys.modules` 里留下旧模块与旧包（宿主按摘要命名，这是刻意为之），单个进程反复重载会缓慢增长；长时间开发建议隔一段时间重启一次。
- 常驻服务由各插件自己的 `stop()` 负责收尾。没有 `stop()` 的连接不会被自动关闭。
- 重载期间正在执行的 run 不会被回滚，工具调用可能因 MCP/worker 重建而失败，需要重试。
