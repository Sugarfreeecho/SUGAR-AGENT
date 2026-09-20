# 检索提速、会话历史与 Web 工具 · 功能方案设计（UseCase 清单）

- 版本：2026-09-20 v3（覆盖至：当前工作区）
- 用途：逐条审查（四字段格式）。
- 适用实现：`app/agent_tools.py`（工具定义）、`app/history_context.py`（会话历史搜索/读取）、`app/builtin_host_tools.py`（只读宿主调用）、搜索提供方注册表。
- 上级：`00-工具系统整体设计.md`

---

## 1. 功能定位

两类检索窗口：`history_context` 从本地耐久会话记录找回被压缩的上下文；web_search/web_fetch/web_download 访问外部信息与文件。两类入口都限制作用域和返回规模。

## 2. UseCase

### UC-3E1 web_search
- **触发**：搜索请求。
- **预期现象**：按提供方返回结构化结果（标题/链接/摘要）；结果数有上限；提供方不可用时明确报错（不编造结果）。
- **规则与边界**：搜索提供方可插拔（provider registry / 插件扩展）；预批准域名策略不适用（搜索是出站查询）。
- **依据**：`web_search / search_provider_registry`、`_web_search_max_results_cap`。

### UC-3E2 web_fetch（含 SSRF 防护）
- **触发**：抓取 URL 内容。
- **预期现象**：公网目标正常抓取并转纯文本；**内网/回环/畸形目标被拒**（理由明确）；重定向有限次跟随；超长内容按保留策略截断。
- **规则与边界**：每次重定向目标重新做安全校验（防跳跃绕过）；代理可用（`_httpx_proxy`）；标题抽取供展示。
- **依据**：`web_fetch / _url_safe_for_fetch / _is_public_ip / _safe_redirect_target / _web_redirect_cap`。

### UC-3E3 web_download
- **触发**：下载文件到本地。
- **预期现象**：默认保存到工作区（路径可查）；同名自动去重；**有字节上限**（超限拒绝而不是写爆磁盘）；回执给出保存路径与大小。
- **依据**：`web_download / resolve_default_download_path / _web_download_max_bytes`。

### UC-3E4 history_context 当前会话检索
- **触发**：模型需要核对当前会话中可能已经被压缩的事实或工具细节。
- **预期现象**：`action="search", scope="current"` 同时搜索当前会话的压缩归档与 `events.jsonl`，默认每项只返回稳定 `history:` 引用和清洗后的正文片段；再以 `action="read"` 对引用做有界、可分页的可读文本读取。
- **规则与边界**：时间戳、seq、schema_version、kind、索引和内部计数等存储字段不进入默认结果；完全相同的语义内容在同一会话内去重。搜索词不能为空；最多返回 50 条；读取单页为 200～50,000 字符；当前作用域拒绝读取其他会话引用。工具不修改事件或归档，并以 `effect=read`、`parallel_safe=true` 注册。
- **依据**：`history_context.history_context / _search_session / _read_ref`、`builtin_host_tools._invoke_history_context`。

### UC-3E5 history_context 全局会话检索与原文件兜底
- **触发**：用户明确要求从其他会话或全部历史中寻找信息。
- **预期现象**：`scope="global"` 按会话事件文件新近程度扫描本地会话；默认结果仅比当前作用域多返回 `session_id`，允许读取跨会话稳定引用。确需检查原文件时显式设置 `include_source=true`：命中项返回 `source_file`，零命中则返回最多 20 个已扫描 `source_files`。
- **规则与边界**：默认必须先用 current，不能因当前会话未命中就擅自扩大到 global；JSONL 先做原始行预筛，再以清洗后的语义文本复核，避免内部元数据造成假命中；结果达到上限即停止；全局模式只扩大读取范围，不改变只读权限。
- **依据**：`history_context._session_dirs / _matching_jsonl / history_context`、`prompt.md / prompt.en.md`。

## 3. 边界

- 出口域名审批（预批准清单）见 ../07-权限审批/06-出口守卫与Shell沙箱方案设计-UseCase清单.md；
- 抓取内容的"进入上下文前的截断"见 06。
- 压缩归档的创建、活跃摘录和摘要兜底见 ../09-横切能力/01；`history_context` 只负责检索，不参与摘要生成。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-3E1 | `agent_tools.py` L3724–3762 |
| UC-3E2 | L3652–3866 |
| UC-3E3 | L3866–3997 |
| UC-3E4 | `history_context.py`、`builtin_host_tools.py` |
| UC-3E5 | `history_context.py`、`prompt.md`、`prompt.en.md` |

## 5. 版本记录

- 2026-09-20 v3：新增 `history_context` 当前/全局会话检索、稳定引用分页读取、默认干净语义结果、同会话去重、显式原文件路径和只读范围边界。
- 2026-09-14 v2：修正出口审批交叉引用（07/06）并更新版本线至 `d022831`。
- 2026-09-13 v1：拆分首版（承接 UC-310/311）。
