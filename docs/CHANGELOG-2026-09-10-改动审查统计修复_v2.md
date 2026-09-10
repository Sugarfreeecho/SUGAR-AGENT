# CHANGELOG（v2）— 改动审查统计修复 · 撤除全量扫描（2026-09-10）

> v1 见 `CHANGELOG-2026-09-10-改动审查统计修复.md`（记录了当时引入全量兜底扫描的方案）。
> 本版反映最终决策：**撤除全量扫描**，后端回到「Git 清单 + 声明路径」的观测面。

## 1. 已撤除：非 Git 全量兜底扫描

撤除内容（全部位于 `plugins/change-review/store.py`）：

- `_fallback_inventory` / `_resolve_inventory`：Git 清单为空时的有界全量遍历。
- 配额与常量：`MAX_FALLBACK_FILES` / `MAX_FALLBACK_CONTENT_BYTES` / `MAX_FALLBACK_FILE_BYTES` / `_FALLBACK_EXCLUDED_DIR_NAMES`。
- `_fast_file_signature`（轻量签名，仅兜底使用）、基线内容预算、`snapshot_missing` 降级分支、`_display_path` / `_key` 微优化。

撤除原因：

- 单步同步成本约 2 秒（观测面 8.7k 文件；见 v1 性能节），且需维护排除集与配额。
- 四家参考实现（Claude Code / DeepSeek Harness / Hermes Agent / OpenCode）均不采用全量扫描——它们要么工具内即时计算，要么用 Git 快照。

存档：`workspace/改动审查自检_20260910/removed_full_scan.diff`（13 个 hunk 的完整差异，可反向恢复）。

## 2. 撤除后的行为（= 加全量扫描前的原版口径）

| 场景 | 原生文件工具（write_file / edit_file / apply_patch / delete_file） | run_shell / 脚本 / MCP / Plugin |
|---|---|---|
| Git 仓库 · tracked 或未忽略的 untracked | ✅ 可见 | ✅ 可见 |
| Git 仓库 · 被 .gitignore 忽略 | ✅ 可见（声明路径） | ❌ 不可见 |
| 非 Git 工作根（含默认 workspace/） | ✅ 可见（声明路径） | ❌ 不可见 |

其余口径不变：`temporary=True` 的写不进入声明路径；同一 run 内同文件多次修改合并；统计仍以 run 为边界。

## 3. 保留的修复

### 前端（`plugins/change-review/web/change-review.js`）

- `stats()`：`added/removed` 为 `null` 的行正确计为「未统计」（修复 `Number(null) = 0` 漏报），按原因分类并在 tooltip 说明口径。
- `acceptChangeUpdate()`：跨 run 的 revision 重置不再吞掉新记录（仅同一 snapshot 的迟到事件被忽略）。
- 「全部撤销」作用域 tooltip；`snapshot_missing` 文案保留（防止历史数据或未来降级显示错乱）。

### 后端（唯一保留改动，独立于扫描的正确性修复）

- `finish_capture` 工作区循环：对「已有真实起点（声明文件/目录，或被忽略文件）」的记录，不再用合成的 missing 基线覆盖其 before。
- 缘由（探针实测，见 `probe_ignored_modify.py`）：Git 仓库中被忽略文件经 `write_file` 修改后，第二次捕获会被改写成伪「新建」，**撤销会直接把文件删除**。该缺陷在无扫描版本（HEAD）同样存在。
- 回归测试：`test_ignored_file_modify_keeps_origin_and_undo_restores`。
- 固定测试：`test_non_git_workspace_observes_declared_file_tools_only`（钉住撤除后的观测面）。

## 4. 测试与验证

- `tests/test_change_review_plugin.py` + `tests/test_plugin_ui_frontend.py`：37 通过。
- 11 场景探针复跑：B / D / G 回到「不可见」（符合撤除预期），A / C / E / F / H / I / J / K 不变。
- 被忽略文件探针（`probe_ignored_modify.py`）：撤除后先复现缺陷，补回保护后恢复「修改保持 modify、撤销还原原文」。

## 5. 涉及文件

- `plugins/change-review/store.py`（回退至原版 + 1 处保护）
- `plugins/change-review/web/change-review.js`（保留）
- `tests/test_change_review_plugin.py`、`tests/js/change_review_stats_runtime.mjs`、`tests/test_plugin_ui_frontend.py`
- 存档与探针：`workspace/改动审查自检_20260910/`（`removed_full_scan.diff`、`probe_change_review_stats.py`、`probe_ignored_modify.py` 等）
