# Web Search Providers · SugarAgent 插件

为内置联网工具提供传输与实现：

- `web_search`：DuckDuckGo、Tavily、Brave Search、SearXNG 与 Jina 搜索传输；
- `web_fetch`：抓取网页并转换为纯文本（SSRF 防护、重定向校验、长度上限）；
- `web_download`：下载文件到工作区（字节上限、同名自动改名）。

1.1.0 起在 **设置 → 联网搜索** 中提供内嵌设置页，可直接选择引擎、写入凭据并测试连通性。
1.2.0 起 `web_fetch` / `web_download` 从核心 `app/agent_tools.py` 迁入本插件：
**停用插件会同时移除这三个工具**，核心不再内置同名工具。

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
| `WEB_FETCH_MAX_REDIRECTS` | `web_fetch` / `web_download` 的重定向跟随上限，默认 5，最多 10 |
| `WEB_DOWNLOAD_MAX_BYTES` | `web_download` 单次下载字节上限，默认 25 MiB，最多 100 MiB |

## 行为说明

- 未配置密钥时，Tavily / Brave / Jina 搜索会失败；工具运行时会按原有逻辑回退到 DuckDuckGo。
- 设置页的 **测试搜索** 直接调用当前引擎，不走回退，便于定位凭据问题。
- DuckDuckGo 依赖宿主 Python 已安装 `ddgs`（或兼容的 `duckduckgo_search`）。
- SearXNG 地址沿用插件的公网校验，本机、内网、链路本地与保留地址会被拒绝。
- `web_fetch` / `web_download` 只允许 http(s)，每次重定向都会重新做公网地址校验；内网、回环、链路本地与保留地址一律拒绝。
- 审批仍由宿主安全策略执行（`web.search` / `network.connect`），预批准域名、会话执行配置中的 URL 约束继续生效；仅 `core.tools` 与 `web-search-providers` 两个 owner 可声明 URL 约束。
- 下载路径以当前会话工作目录（含子代理 worktree）为根，并沿用该次调用已批准的权限与受保护路径检查。
- 旧配置中的 `host/core.tools` 抓取与下载引用在读取时自动转换为本插件引用；已有允许、禁用、参数绑定和 URL 约束继续生效，运行快照中的旧引用也兼容匹配。
- 设置 API 只允许本机同源浏览器访问；插件停用后页面、接口与三个工具一并不可用。
- 若某个会话/CLI 执行配置把 `web_fetch` 或 `web_download` 绑定为必需工具，停用插件会让该配置校验失败（`required_tool_unavailable`）；需重新启用插件或移除绑定。

## 安装位置

保持目录为 `plugins/web-search-providers/`，并保留 `.myagent-plugin/plugin.json`。
宿主适配器需要直接位于程序 `plugins/<插件 id>/` 下，才能加载 `trusted_host` 设置接口。

## 主要文件

- `host.py`：搜索传输、三个联网工具的注入、设置与测试 API。
- `web_tools.py`：`web_fetch` / `web_download` 实现与 SSRF、长度和下载上限校验。
- `web/index.html`：内嵌设置页。
- `web/assets/`：页面脚本、样式和首屏主题脚本。
