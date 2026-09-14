# MCP 接入与工具池 · 功能方案设计（UseCase 清单）

- 版本：2026-09-14 v2（覆盖至：HEAD `d022831` + API 识图工作区改动）
- 用途：逐条审查（四字段格式）。
- 适用实现：`app/agent_mcp.py`（1.2k 行）、`mcp_servers.json`。
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
- **触发**：修改 `mcp_servers.json`。
- **预期现象**：配置签名变化 → 自动重连（或提示重启点）；旧服务器进程被清理；工具目录同步。
- **依据**：`_compute_config_signature_cached / force_reload / _shutdown_servers_unlocked`。

### UC-6F5 调用与结果
- **触发**：模型调用 MCP 工具。
- **预期现象**：调用转发正确；文字和图片按 MCP ContentBlock 原顺序处理。模型候选支持 image 时，图片经统一准入变成耐久附件引用，并按当前协议投影回工具结果；不支持 image 时返回明确省略说明且不把图片写入附件库。错误以工具失败形式呈现。
- **规则与边界**：图片结果不再直接降成 `[image content omitted]`，也不通过 `str(content)` 丢失结构。日志在序列化和截断前移除图片载荷，避免 base64 短暂进入日志字符串。
- **依据**：`invoke_tool_by_fname / format_call_tool_result / _serialize_call_tool_result_for_log`、`attachments.content.chat_tool_images/redact_image_payloads`。

### UC-6F6 注册决策
- **触发**：新 MCP 服务器首次出现（安全流程）。
- **预期现象**：按注册决策流程处理（信任/拒绝）；未决策前工具不可用。
- **依据**：`decide_mcp_registration`（webui）、`security/extensions` 联动。

## 3. 边界

- MCP 工具的执行策略（并行/审批）走统一注册表规则（../03-工具系统/01/02）。
- 图片的内容寻址、候选能力门控、请求预算和三协议映射见 [../09-横切能力/02](../09-横切能力/02-识图与多模态投影方案设计-UseCase清单.md)。

## 4. 依据映射

见上表（`agent_mcp.py` 各段）。

## 5. 版本记录

- 2026-09-14 v2：补齐 MCP 图片统一准入、能力门控、协议投影与日志脱敏。
- 2026-09-13 v1：拆分首版（承接 UC-608/609）。
