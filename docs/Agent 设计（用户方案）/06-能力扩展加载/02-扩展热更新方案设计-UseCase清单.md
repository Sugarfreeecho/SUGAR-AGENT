# 扩展热更新 · 功能方案设计（UseCase 清单）

- 版本：2026-09-13（覆盖至：HEAD `d022831`）
- 用途：逐条审查（四字段格式）。
- 适用实现：`agent_extensions.py`（`plugin_registry_signature / invalidate_extension_caches / reload_extensions / _schedule_plugin_cache_refresh / SWR`）、`agent_mcp._compute_config_signature`。
- 上级：`00-能力扩展加载整体设计.md`

---

## 1. 功能定位

"改完即新"的机制说明：什么变化触发什么重建、多快生效、失败时怎样。

## 2. UseCase

### UC-6B1 签名变化检测
- **触发**：插件目录、技能树、MCP 配置、hooks 文件发生修改。
- **预期现象**：签名变化被检测到；无需重启；变更范围可判断（哪个扩展变了）。
- **依据**：`plugin_registry_signature / _skills_tree_signature / _compute_config_signature_cached`。

### UC-6B2 缓存失效与重建（SWR 式）
- **触发**：签名变化后下一次请求。
- **预期现象**：先返回"旧但可用"的数据同时后台重建（Stale-While-Revalidate），**最多一轮请求滞后**后完全生效；期间不报错不空窗。
- **依据**：`invalidate_extension_caches / _schedule_*_rebuild / _swr_work_begin/_end / _drain_background_refreshes`。

### UC-6B3 显式重载
- **触发**：调用 `reload_extensions()`（如"刷新扩展"按钮）。
- **预期现象**：立即重载并给出结果（成功/失败清单）；运行中的任务不被强杀（按安全点处理）。
- **依据**：`reload_extensions() -> PluginReloadResult`。

### UC-6B4 目录代际
- **触发**：任何扩展变更。
- **预期现象**：目录代际递增（供缓存/一致性判断）；工具目录（MCP）同步刷新；界面可见的集合与代际一致。
- **依据**：`_bump_extension_catalog_generation`、`_bump_tool_catalog_generation`。

## 3. 边界

- 热更新**不**重载已发起的模型请求（下一轮生效）；
- 失败的处理：保留上一版可用状态（不半途拆台）。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-6B1 | `agent_extensions.py` L750–845 |
| UC-6B2 | L998–1085 |
| UC-6B3 | L1053 |
| UC-6B4 | L771–782、`agent_mcp` L242 |

## 5. 版本记录

- 2026-09-13 v1：拆分首版（承接 UC-602）。
