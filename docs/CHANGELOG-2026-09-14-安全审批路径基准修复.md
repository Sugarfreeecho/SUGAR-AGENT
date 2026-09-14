# CHANGELOG — 2026-09-14 安全审批路径基准修复

## 背景

8-28 起，工作区内的删除命令（如 `rm -f`、`Remove-Item`）按设计应为普通审批
（黄色，「请求批准」模式下弹普通确认卡；「完全访问」下直接放行）。

但用户实测发现：**工作区内的删除仍会弹红框单次授权**（`process.destructive`
强制规则）。9-13 会话 `04a2a8de` 的审批记录是一个实例：

```
Remove-Item "..\..\archify_study\dsh_demo\...visual-check.json" -Force
workdir = ./skills/archify
```

目标实际落在 `workspace/archify_study/`（工作区内），却被判为「工作区外」，
进而命中 `process.destructive` 强制审批（只能单次授权、复核模型与复用规则
均不可放行）。

## 根因

路径分类器 `_outside_workspace_tokens` 在解析命令里的相对路径 token 时，
**一律以工作区根为基准**，忽略了 `run_shell` 实际生效的 `workdir`：

- 命令从 `workspace/skills/archify` 执行，`..\..\archify_study\x` 实际解析到
  `workspace/archify_study/x`（区内）；
- 分类器却按工作区根解析为 `项目上级目录/archify_study/x`（区外）→
  误判外部访问 → `workspace_delete=False` → 红框强制审批。

`security/runtime.authorize_request` 的 `required_dirs` 复核环节同样不感知
`workdir`，会在二次计算中复现该误判。

## 修复内容

1. `app/agent_tools.py`
   - `_resolve_shell_token_for_workspace_restrict(raw, workspace, base=None)`：
     相对路径优先按 `base`（生效工作目录）解析；未提供时的回退与旧行为一致。
   - `_outside_workspace_tokens` / `_paths_inside_workspace` /
     `_readonly_git_scope_ok` 增加可选 `base` 并透传。
   - Windows 虚拟根（`/foo` → `WORK_DIR/foo`）语义保持不变。

2. `app/security/runtime.py`
   - 新增 `_effective_shell_base()`：按 `agent_tools._resolve_shell_working_dir`
     的口径解析 `workdir`。
   - `classify_tool`：run_shell 分类全程携带 `base=exec_base`，并在
     metadata 中记录 `workdir` / `effective_workdir`。
   - `authorize_request` 的 process.exec 复核：改用与 classify 相同的
     基准解析与 `_outside_workspace_tokens` 扫描（替代原「仅扫描绝对路径」
     的实现），保留只读 git `-C` 豁免与按会话授权目录语义。

3. `tests/test_security_core.py` 新增 3 条回归：
   - workdir 子目录 + `..` 回到工作区内 → 普通审批（`process.workspace_delete`）；
   - 按 workdir 解析后仍逃出工作区 → 保持红框强制（`process.destructive`）；
   - 只读 git `-C` 区外经 `authorize_tool` 全链路 → 仍为 ALLOW。

4. `docs/Agent 设计（用户方案）/` 审查文档同步更新：
   - 04-工作区/01：新增 UC-4A5（Shell 路径解析基准），UC-4A3 补交叉引用；
   - 03-工具系统/03：UC-3C4 工作区收窄改为含相对路径与 workdir 基准；
   - 07-权限审批/02、05：UC-7B3/7E5 明确"工作区删除=普通审批 / 越界或非删除高危=强制单次"；
   - 00-总览、04/07 模块整体设计与三份能力清单同步（版本记录已追加）。

## 修复后的行为

| 场景 | 分类结果 | 审批表现 |
|---|---|---|
| workdir 子目录 + `..` 回到工作区内 | 工作区内删除 | 普通审批（完全访问下免审批） |
| 按 workdir 解析后逃出工作区 | 外部删除 | 红框单次授权（所有模式） |
| 默认 workdir（工作区根）的相对/绝对路径 | 与旧行为一致 | 不变 |
| 只读 git `-C` 指向区外 | 非外部访问 | ALLOW |
| 绝对路径含空格但**未加引号** | 仍判外部（保守） | 红框；建议加引号或改用相对路径 |

## 已知残余限制

- 命令内自行 `cd` 切换目录后再使用 `..` 相对路径的组合，分类器仍以
  `workdir` 参数为基准（不模拟 `cd`），可能保持保守的外部判定；
- 未加引号且含空格的绝对路径本身存在歧义（shell 也会拆错），不自动放宽。

## 验证

- `pytest tests/test_security_core.py`：93 passed, 1 skipped；
- `pytest tests/test_run_shell_self_protection.py tests/test_shell_egress_analysis.py tests/test_agent_tools_performance_paths.py tests/test_security_store_rename.py`：68 passed；
- 分类探针复核：9-13 实际案例已判定为工作区内删除（`workspace_delete=True`），
  真外逃与复合红线（`rm -rf ... && reboot`）保持强制审批。
