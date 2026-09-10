# CHANGELOG — 改动审查统计口径修复（2026-09-10）

> 注：本版记录的「非 Git 全量兜底扫描」方案已于同日按决策撤除，最终状态见
> `CHANGELOG-2026-09-10-改动审查统计修复_v2.md`。

本批改动回应「改动审查统计总是不准」的自检结论（见 `workspace/改动审查自检_20260910/自检报告.md`）。

**口径决策：保留「以 run（执行过程）为边界」的统计语义**——每轮相对本轮起点的净变更，不做跨轮累计；跨轮记录各归各的执行过程。

## 一、后端（`plugins/change-review/store.py`）

### 1. 非 Git 工作根兜底观测（覆盖缺口修复）

- 新增 `_fallback_inventory` / `_resolve_inventory`：当 `git ls-files` 找不到仓库（或清单为空，如被外层仓库整体忽略的 `workspace/`）时，改为**有界全量遍历**，使 `run_shell`、脚本、MCP/Plugin 工具产生的改动可见。
- 排除项：`.git`/`.hg`/`.svn`、`node_modules`/`.venv`/`venv`/`__pycache__`/各种缓存、`.trash`/`.tool_results`/`.run_shell_temp`/`.playwright-mcp`/`.sugaragent`/`.myagent`，以及 App 运行时目录 `sessions/`（`sessions.json` 标记）、`skills/`（`agent_tools.SKILLS_DIR`）。
- 配额：`MAX_FALLBACK_FILES=40000`、`MAX_FALLBACK_CONTENT_BYTES=16MiB`、`MAX_FALLBACK_FILE_BYTES=512KiB`；超文件数上限时放弃兜底（仅声明路径）。
- 性能保护：兜底路径使用**轻量签名**（`_fast_file_signature`，仅 lstat，不做每文件 Windows 句柄查询）、内容读取受预算约束、路径计算改为前缀切片；`_key` 去掉多余的 `abspath`。
- Git 仓库路径行为完全不变（精确签名、全量内容归档）。

### 2. 缺失基线的降级记录

- 兜底基线对超出 `512KiB` 或预算耗尽的大文件只记签名，不存内容；变更时生成 `diff_omitted_reason="snapshot_missing"` 的记录（可见、可计数，暂不可撤销），不再整批丢弃工具结果。
- `finish_capture` 中 `_baseline_bytes` 失败改为单文件降级（原实现会让整次工具结果全部丢失）。
- 工作区比对循环：对"已有真实起点（文件/目录/被忽略路径）"的记录不再用合成的 missing 状态重写其 before（修复空目录删除等记录被覆盖的问题）。

## 二、前端（`plugins/change-review/web/change-review.js`）

- `stats()`：`added/removed` 为 `null` 的行正确计为「未统计」，修复 `Number(null)=0` 导致的漏报；新增按原因分类统计（binary / too_large / too_many_lines / too_complex / snapshot_missing）。
- 徽标与汇总：`+A −R · N 个文件未统计行数`，并在 `title` 中给出**口径说明**（本轮净变更、同文件合并、已还原不计）与原因分布。
- 单文件行：无行统计时显示「未统计」，悬停给出具体原因；`snapshot_missing` 明确提示"无法预览或撤销"。
- `acceptChangeUpdate()`（导出、可单测）：跨 run 的 revision 重置不再吞掉新记录——仅同一 snapshot 的迟到事件会被忽略；steer 场景丢更新的问题修复。
- 「全部撤销」按钮补充 tooltip：说明作用域是本轮（该执行过程）。

## 三、测试与验证

- `tests/test_change_review_plugin.py` 新增 4 例：非 Git 根 shell 改动可见并可撤销、内部目录排除、文件级内容上限降级、文件数上限禁用兜底（声明工具不受影响）。
- `tests/js/change_review_stats_runtime.mjs` 扩充：null 行数统计、原因分类、跨 run revision 接受逻辑；由 `tests/test_plugin_ui_frontend.py` 注册执行。
- 全量：`tests/test_change_review_plugin.py` + `test_plugin_ui_frontend.py` 39 通过；`-k plugin` 全仓 199 通过 / 3 跳过。

## 四、实测性能（workspace 根，8,696 个观测文件）

| 阶段 | 修复前（兜底未启用） | 初版兜底 | 优化后 |
|---|---|---|---|
| 首次工具基线 | ~0（无观测） | 72 s | ≈2 s |
| 后续工具扫描 | ~0 | 5.2–6.4 s | ≈2 s |

- 优化手段：排除 `sessions/`、`skills/`（约 2 万文件 → 8.7 千）、轻量签名免除每文件 Windows 句柄、内容预算、路径计算优化。
- 残余边界：Git 仓库中被忽略的文件仍按仓库策略不观测（设计保留）；兜底未存内容的大文件变更显示为 `snapshot_missing`；兜底根每次文件工具都要重新遍历目录（当前量级见上表）。

## 五、涉及文件

- `plugins/change-review/store.py`
- `plugins/change-review/web/change-review.js`
- `tests/test_change_review_plugin.py`、`tests/js/change_review_stats_runtime.mjs`、`tests/test_plugin_ui_frontend.py`
- 验证脚本：`workspace/改动审查自检_20260910/`（probe、bench、micro、自检报告）
