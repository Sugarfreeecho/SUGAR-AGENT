# MCP 接入与工具池 · 功能方案设计（UseCase 清单）

- 版本：2026-10-17 v4（已发布目录读取、并行发现与按服务更新）
- 用途：逐条审查（四字段格式）。
- 适用实现：`app/agent_mcp.py`、`.config/mcp_servers.json`。
- 上级：`00-能力扩展加载整体设计.md`

---

## 1. 功能定位

把外部 MCP 服务器变成"会生长的工具池"：三种连接方式、按需保活、单工具可控。

## 2. UseCase

### UC-6F1 三种连接器
- **触发**：配置 MCP 服务器（stdio 子进程 / SSE / streamable-http）。
- **预期现象**：按配置选择连接方式并建立持久会话；连接失败有明确状态与原因（不静默）。
- **规则与边界**：stdio 支持自定义 cwd 与环境变量引用展开；http 类支持自定义 headers。
- **依据**：`_make_stdio_connector / _make_sse_connector / _make_streamable_connector / _PersistentMcpServer / _resolve_stdio_cwd / _expand_env_references`。

### UC-6F2 工具入池
- **触发**：服务器连接成功后。
- **预期现象**：其工具出现在模型工具表（带来源标注）；schema 转换正确（MCP inputSchema → OpenAI parameters）。
- **依据**：`_register_tools_globally / _openai_tool_def / _schema_to_parameters`。

### UC-6F3 单工具开关
- **触发**：对某 MCP 工具禁用/启用。
- **预期现象**：即时生效（目录代际刷新）；禁用后模型不再看到该工具；状态持久。
- **依据**：`set_mcp_tool_enabled / is_mcp_tool_enabled / _bump_tool_catalog_generation`。

### UC-6F4 配置变更与重连
- **触发**：修改 `.config/mcp_servers.json` 或扩展配置签名变化。
- **预期现象**：自动协调按服务器配置与所属插件内容指纹比较，保留未变化的健康连接；更改/移除的服务撤下旧定义后清理，待新发现成功发布。单服务失败按指数退避重试，默认 1 秒起、最大 60 秒；环境变量 `MCP_RETRY_INITIAL_SECONDS / MCP_RETRY_MAX_SECONDS` 可调整。无关插件内容变动不重启配置未变的 MCP；所属插件代码变化则重启其服务。
- **规则与边界**：`force_reload()` 作为现有管理面显式全量重置入口仍关闭全部服务；请求读取目录不等待该重置。单服务手动注册绕过当前退避窗口，仅重试指定服务。实际调用已注册工具不先等待其他服务的初始化。
- **依据**：`_ensure_started_impl / _server_config_signatures / _server_retry_state / register_server / force_reload`。

### UC-6F5 调用与结果
- **触发**：模型调用 MCP 工具。
- **预期现象**：调用转发正确；文字和图片按 MCP ContentBlock 原顺序处理。模型候选支持 image 时，图片经统一准入变成耐久附件引用，并按当前协议投影回工具结果；不支持 image 时返回明确省略说明且不把图片写入附件库。错误以工具失败形式呈现。
- **规则与边界**：图片结果不再直接降成 `[image content omitted]`，也不通过 `str(content)` 丢失结构。日志在序列化和截断前移除图片载荷，避免 base64 短暂进入日志字符串。
- **依据**：`invoke_tool_by_fname / format_call_tool_result / _serialize_call_tool_result_for_log`、`attachments.content.chat_tool_images/redact_image_payloads`。

### UC-6F6 注册决策
- **触发**：新 MCP 服务器首次出现（安全流程）。
- **预期现象**：按注册决策流程处理（信任/拒绝）；未决策前工具不可用。
- **依据**：`decide_mcp_registration`（webui）、`security/extensions` 联动。

### UC-6F7 请求读取已发布目录，发现与启动在后台

- **触发**：WebUI 生命周期启动、ReAct 查询工具目录或读取版本。
- **预期现象**：host 接管关系安装后预热 MCP；各服务并行连接，健康服务完成即发布连接、定义与契约，无需等慢服务。ReAct 使用 `get_published_tool_definitions()`；签名检查/协调在专用 MCP 循环后台执行，重复调度合并，已启动后的检查最多按既有 1 秒窗口安排。迟到发布使目录代际变化，下一请求按原工具搜索/披露规则重建。
- **规则与边界**：保留管理面 `get_tool_definitions()/ensure_started()` 的等待接口。全局禁用、逐工具禁用和当前注册信任撤销均影响目录/版本及执行；使用预先计算的注册描述符检查当前信任，不因后台服务启动锁而延迟撤权。禁用状态读取失败时目录不放行。连接池和工具执行策略不绕过 host 所有权、workspace 隔离或工具搜索的授权范围。
- **依据**：`get_published_tool_definitions / get_tool_catalog_revision / _unapproved_published_servers / schedule_mcp_startup_refresh`、`webui.start_webui_lifecycle`；`tests/test_mcp_background_catalog.py`。

## 3. 边界

- MCP 工具的执行策略（并行/审批）走统一注册表规则（../03-工具系统/01/02）。
- 图片的内容寻址、候选能力门控、请求预算和三协议映射见 [../09-横切能力/02](../09-横切能力/02-识图与多模态投影方案设计-UseCase清单.md)。

## 4. 依据映射

见上表（`agent_mcp.py` 各段）。

## 5. 版本记录

- 2026-10-17 v4：新增 UC-6F7，更新 UC-6F4；区分后台协调与显式全量重置，补录按服务发布、退避、即时禁用/撤权和实际调用不等待无关服务。
- 2026-10-05：服务器级 `tools.include/exclude/pin` 增量筛选（exclude 优先、pin 不复活禁用项）；设置中心批量启停与常驻按钮；旧逐工具开关兼容。
- 2026-09-14 v2：补齐 MCP 图片统一准入、能力门控、协议投影与日志脱敏。
- 2026-09-13 v1：拆分首版（承接 UC-608/609）。
