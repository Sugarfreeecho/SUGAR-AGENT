# Web Search Providers · SugarAgent 插件

为内置 `web_search` 工具提供 DuckDuckGo、Tavily、Brave Search、SearXNG 与 Jina 搜索传输。
1.1.0 起在 **设置 → 联网搜索** 中提供内嵌设置页，可直接选择引擎、写入凭据并测试连通性。

## 设置页

- **搜索引擎**：选择 `WEB_SEARCH_PROVIDER`，并设置单次结果上限 `WEB_SEARCH_MAX_RESULTS`。
- **访问凭据**：按当前引擎显示 Tavily / Brave / Jina API Key 或 SearXNG 实例地址。
- **测试搜索**：使用已保存的配置直接测试当前引擎，返回耗时和工具实际看到的搜索结果。
- 设置写入与设置中心相同的 `.env`，并立即应用到当前进程；无需重启。
- 首次安装或更新插件后，点「重新发现 / 热重载」（或停用再启用）即可让宿主 API 随插件生命周期重新加载，不必重启；只有改宿主 `app/*.py` 或 `.env` 才需要重启。判定口径见 [插件热重载](../../docs/plugin_hot_reload.md)。
- 密钥只保存在本机 `.env`，页面仅显示掩码后缀。输入框留空不会覆盖已保存的密钥。

## 配置项

| 变量 | 说明 |
| --- | --- |
| `WEB_SEARCH_PROVIDER` | `duckduckgo` / `tavily` / `brave` / `searxng` / `jina`，默认 `duckduckgo` |
| `WEB_SEARCH_MAX_RESULTS` | 单次搜索返回条数上限，默认 20 |
| `TAVILY_API_KEY` | Tavily API Key |
| `BRAVE_API_KEY` | Brave Search API Key |
| `JINA_API_KEY` | Jina API Key |
| `SEARXNG_BASE_URL` | SearXNG 实例根地址，需公网可访问并开启 JSON 输出 |

## 行为说明

- 未配置密钥时，Tavily / Brave / Jina 搜索会失败；工具运行时会按原有逻辑回退到 DuckDuckGo。
- 设置页的 **测试搜索** 直接调用当前引擎，不走回退，便于定位凭据问题。
- DuckDuckGo 依赖宿主 Python 已安装 `ddgs`（或兼容的 `duckduckgo_search`）。
- SearXNG 地址沿用插件的公网校验，本机、内网、链路本地与保留地址会被拒绝。
- 设置 API 只允许本机同源浏览器访问；插件停用后页面与接口一并不可用。

## 安装位置

保持目录为 `plugins/web-search-providers/`，并保留 `.myagent-plugin/plugin.json`。
宿主适配器需要直接位于程序 `plugins/<插件 id>/` 下，才能加载 `trusted_host` 设置接口。

## 主要文件

- `host.py`：搜索传输、`web_search` 工具注入、设置与测试 API。
- `web/index.html`：内嵌设置页。
- `web/assets/`：页面脚本、样式和首屏主题脚本。
