# 检索提速与 Web 工具 · 功能方案设计（UseCase 清单）

- 版本：2026-09-13（覆盖至：HEAD `6acc6bf`）
- 用途：逐条审查（四字段格式）。
- 适用实现：`app/agent_tools.py`（Web 段 L3652–3997）、搜索提供方注册表。
- 上级：`00-工具系统整体设计.md`

---

## 1. 功能定位

对外世界的三个窗口：web_search（搜）、web_fetch（读页）、web_download（下文件）——全部带防护。

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

## 3. 边界

- 出口域名审批（预批准清单）见 ../07-权限审批/09；
- 抓取内容的"进入上下文前的截断"见 06。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-3E1 | `agent_tools.py` L3724–3762 |
| UC-3E2 | L3652–3866 |
| UC-3E3 | L3866–3997 |

## 5. 版本记录

- 2026-09-13 v1：拆分首版（承接 UC-310/311）。
