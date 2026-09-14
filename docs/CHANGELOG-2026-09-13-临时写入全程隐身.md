# CHANGELOG — 临时写入（temporary=True）全程隐身修复（2026-09-13）

## 1. 问题（对/错定性结论）

对 `temporary=True` 写入的生命周期做了三组实测，结论：

| 情况 | 修复前行为 | 定性 |
|---|---|---|
| 非 Git 根 / 忽略路径 + shell 删除 | 全无痕 | ✅ 正确 |
| 非 Git 根 / 忽略路径 + `delete_file` 删除 | **孤儿 `delete −N` 行**（只删无建） | ❌ 不正确 |
| Git 根（未忽略路径）+ temporary 写 | **被 Git 扫描记录 `create +N`** | ❌ 不正确（跨根不一致） |
| Git 根 + temporary 写 + 回合末清理 | 残留 `+N` 行，文件已不在 | ❌ 不正确（误导） |

三个错误的共同根因：`temporary` 只是"声明路径"这一层的单点跳过，其他采集通道（Git 工作区扫描、删除工具、清理）不认这个标志。

## 2. 修复设计（store.py）

引入**临时路径登记表** `index["temporaries"]`，让临时路径在存储层"全程隐身"：

1. **登记（在写之前）**：`write_file(temporary=True)` 在 `begin_capture` 即解析路径、抓取写前原始状态（内容或 missing），登记进 `temporaries`（首次登记保留最初起点），并直接结束本次捕获——**不产生任何审查行**；Git 根下不再走 `finish_capture` 的扫描路径。
2. **隐身（三源）**：
   - Git 工作区扫描：命中登记路径一律 `continue`（创建、修改、shell 删除都不出现）；
   - 声明路径：删除登记路径时静默并注销登记（不再产生孤儿 `delete` 行）；
   - 回合末清理：本就不过采集通道，无变化。
3. **毕业（graduation）**：如果之后同一路径被**正常写**（`write_file` 不带 temporary / `edit_file` / `apply_patch`），登记转为正式记录：记录的 `before` 使用登记时保存的"最初起点"——文件终态与真实起点的累计 diff，不会丢失临时阶段创建的内容。
4. **生命周期**：GC 保留登记表的 `before_blob`；分支复制（`copy_referenced_to`）连同登记表一起复制，避免分支后出现孤儿删除行。
5. **边界说明**：shell 删除登记路径不会经过声明通道，登记条目会保留到（a）该路径被正常写毕业，或（b）被 `delete_file` 类删除注销；对统计无影响，条目是会话级、有界的。

## 3. 测试与验证

- 新增 4 个后端测试：
  - `test_temporary_write_and_delete_stay_invisible_even_in_git`
  - `test_temporary_write_shell_delete_stays_invisible`
  - `test_temporary_then_normal_write_graduates_with_original_origin`
  - `test_temporary_graduation_keeps_preexisting_origin`
- 复跑历史探针（E1–E4）：修复前"孤儿删除行 / Git 根残留添加行"的四个场景现在全部为"无行"。
- `test_change_review_plugin.py` + `test_plugin_ui_frontend.py`：48 通过；全仓 plugin 相关：208 通过 / 3 跳过。

## 4. 涉及文件

- `plugins/change-review/store.py`（`temporaries` 登记表、`_register_temporary` / `_temporary_entry`、begin/finish 分支、GC 保留、分支复制）
- `tests/test_change_review_plugin.py`（4 个新测试）
- 验证脚本：`workspace/改动审查自检_20260910/run_temp_delete_probe.py`、`run_temp_delete_probe4.py`
