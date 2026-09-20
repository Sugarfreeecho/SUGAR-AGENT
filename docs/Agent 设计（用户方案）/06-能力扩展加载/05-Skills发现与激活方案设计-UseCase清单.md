# Skills 发现与激活 · 功能方案设计（UseCase 清单）

- 版本：2026-09-20 v3（覆盖至：当前工作区）
- 用途：逐条审查（四字段格式）。
- 适用实现：`app/agent_tools.py`（L109–214、L4055–4199）、`workspace/skills/**`、`skill_states.json`。
- 上级：`00-能力扩展加载整体设计.md`

---

## 1. 功能定位

把"技能文档"（SKILL.md + 资源）变成 Agent 可用的能力：目录扫描、启停持久、会话内激活。

## 2. UseCase

### UC-6E1 技能发现
- **触发**：扫描 `workspace/skills/`（含插件携带的技能目录）。
- **预期现象**：合法技能（frontmatter 含 name+description）进入目录；同名技能按覆盖规则处理（后见者胜/项目优先）；坏技能被跳过并记录。
- **规则与边界**：发现基于**目录树签名**缓存（改动才重扫）；插件技能与用户技能来源可区分。
- **依据**：`discover_skills / _skills_tree_signature / _plugin_skill_directories`（`agent_tools.py` L163）。

### UC-6E2 启停状态持久化
- **触发**：开启/关闭某技能。
- **预期现象**：状态写入 `skill_states.json`，重启保持；关闭的技能不出现在目录**且不可激活**。
- **依据**：`set_skill_enabled / _load_skill_enabled_states / get_skills_catalog`。

### UC-6E3 技能激活
- **触发**：模型或用户激活某技能。
- **预期现象**：SKILL.md 正文与资源根注入当前对话；激活后模型行为按技能指引变化。
- **规则与边界**：未启用/不存在 → 明确报错；重复激活幂等（不重复注入）；激活内容受上下文预算约束。
- **依据**：`activate_skill`。

### UC-6E4 目录生成与缓存
- **触发**：构建系统提示（技能目录段）。
- **预期现象**：目录文本稳定生成（供模型选择）；SKILL.md 或目录树在磁盘上直接变化时，`get_skills_catalog()` 检测到签名变化并递增 generation，使静态提示段在下一次请求刷新（最多滞后一次）。
- **规则与边界**：generation 不只依赖显式 `invalidate_skills_cache()`；目录树签名变化也必须推进代际，否则发现结果虽刷新，模型仍可能看到旧静态段。
- **依据**：`get_skills_catalog / _skills_tree_signature / _bump_skills_catalog_generation / skills_catalog_generation`。

## 3. 边界

- 技能**激活后的工具**（如技能脚本）仍走工具/审批体系；
- 技能与插件的区别：技能是"说明书+资源"，插件是"可执行扩展"。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-6E1 | `agent_tools.py` L163–214、L4055 |
| UC-6E2 | L122–163 |
| UC-6E3 | L4180 |
| UC-6E4 | `get_skills_catalog`、`_skills_tree_signature`、`_bump_skills_catalog_generation`、`skills_catalog_generation` |

## 5. 版本记录

- 2026-09-20 v3：明确磁盘技能树签名变化会推进 catalog generation，并联动失效提示静态段。
- 2026-09-14 v2：修正技能符号与行号（`_plugin_skill_directories` L163、L4169/L118）；版本线更新至 `d022831`。
- 2026-09-13 v1：拆分首版（承接 UC-606/607）。
