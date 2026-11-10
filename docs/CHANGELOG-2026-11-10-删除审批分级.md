# 删除审批分级：普通文件删除不再走红色强制审批

日期：2026-11-10
涉及：`app/security/policy.py`、`app/security/runtime.py`、`tests/test_security_core.py`、`scripts/audit_red_impact.py`

## 1. 问题

删一个具体文件（`Remove-Item -Force xxx.json`、清理 `%LOCALAPPDATA%\Temp\...`）也会弹**红色**审批卡：

- 标题「危险命令，需要确认」，后果写「文件永久丢失或系统无法恢复」；
- 不能「始终允许同类」、不能会话记忆、自动审查也不能覆盖；
- 每删一个临时文件都要人工点一次。

回放本机 2026-10-01 起的 97 条历史红卡，其中大量是工作区外一次性的临时目录/单文件清理，与「格式化磁盘、写裸设备、关机」同级处理，明显过重。

## 2. 判定规则（改后）

```
命中删除语句              → deletion
全部危险类别都是 delete.* → 只删文件（没有 format/diskpart/dd/关机/网卡/fork bomb）
删除目标不是根/系统树     → 普通删除
```

满足三条 → 普通审批；否则仍为红色。落到规则上：

| 情形 | 规则 | 卡片 |
|---|---|---|
| 授权目录内删除，无其它红线 | `process.workspace_delete` | 黄（原样） |
| 授权目录外删除，目标具体 | `delete.review` | 黄（**本次**） |
| 目标是磁盘根、家目录/家目录父级、`C:\Windows`、`Program Files*`、`ProgramData`、`/etc`、`/usr` 等 | `process.destructive` | 红 |
| 删除 + 其它红线（`rm -rf x && reboot`、`format`、`shutdown`…） | `process.destructive` | 红 |
| `os.remove` / `shutil.rmtree` 脚本式删除 | 同上按目标判定 | — |

三条实现要点：

1. `deletion_only_destructive()`：只看 `destructive_kinds` 是否全为 `delete.*`。混合红线保持红。
2. `deletion_hits_protected_target()`：读取新增的 `deletion_targets`，命中根目录/系统树/家目录 → 保持红。
3. `_delete_targets_text()`：**只从删除语句里取路径**。同一条命令里 `Remove-Item` 一个 flag 文件、又启动 `C:\Windows\System32\OpenSSH\ssh.exe` 时，ssh 路径不算删除目标——否则会把普通清理误判成删系统目录。

## 3. 安全边界没有被放宽的地方

- **删除不生成 `rm:*` 前缀规则**（`suggest_rule_pattern` 对 `deletion` 直接返回 `None`）。原先靠「红卡不能用规则」兜底；降级后若仍允许前缀规则，一次授权会永久放行任意 `rm`。
- 目录授权仍按目录粒度：删别的目录照旧要审批。
- `format`、`diskpart`、`dd`、`shutdown`/`reboot`、`Stop-Computer`、禁用网卡、fork bomb 一条都没动。
- 变量/环境变量形式的删除目标（`Remove-Item $f`）不参与「系统树」判定，也不会因此变成安全——它仍要审批，只是不再冒充红色。

## 4. 顺带修掉的误伤

`_POLICY_TAMPER` 原本「命令里出现 `app/security`（或 `permission_mode`、`security_enabled`）即判策略篡改」，导致只读命令也被拒：

```
git status --porcelain -- app/security/policy.py     → 之前 DENY，现在放行
grep -rn permission_mode app/security                → 之前 DENY，现在放行
```

新增 `_policy_tamper_match()`：命令以只读检查（`git status/diff/log/show/ls-files/grep`、`rg`、`grep`、`Get-Content`、`Select-String`、`ls`、`dir`…）开头，且不含重定向、管道、`Set-Content`/`Remove-Item`/`python`/`node`/`powershell` 等写或执行手段时，不判篡改。写入路径不变：`Set-Content app/security/policy.py`、`git status -- … > out.txt`、`python -c "open('app/security/policy.py','w')"` 仍为 `policy_change` → DENY。

## 5. 验证

| 项 | 结果 |
|---|---|
| `tests/test_security_core.py` + `test_destructive_approval_labels.py` | 127 passed, 1 skipped |
| 上述 + `test_security_store_rename` / `test_execution_integration` / `test_hooks_core` / `test_session_workspace_paths` / `test_tool_review_preparation` / `test_tool_search` | 232 passed, 1 skipped |
| `scripts/audit_red_impact.py --since 2026-10-01` | 97 条历史红卡 → **仍红 1 条、降级 96 条** |

唯一仍红的是 `Remove-Item -Recurse -Force C:\Windows\Temp\prereq_tree`（目标在 Windows 树内），符合预期。

回放口径也改了：`audit_red_impact.py` 原先用 metadata 的 `destructive and not workspace_delete` 判「是否仍红」，那是旧规则；现在直接跑 `PolicyEngine.decide` + `forced_approval_for`，规则一改就自动跟随。

## 6. 已知边界

- `rm -rf /` 被当作 POSIX 特殊路径跳过外部检测，落进 `process.workspace_delete`（黄）。**改动前就是这样**，本次未动；如需收紧，应在 `_is_posix_special_path_skip_workspace_check` 里区分「跳过基准」与「根目录删除」。
- 删除目标写在变量里（`Remove-Item $dir\$f`）时无法判定是否触及系统树，按普通审批处理。
- `C:\Windows\Temp` 下的清理仍为红（整个 Windows 树受保护）。若嫌严，可把保护范围收窄到 `System32`/`SysWOW64`/`WinSxS`。
