# Repo Engineering

仓库工程化工作流：评审、测试、写文档、检查发布。是一份**纯声明式插件**——`source_format: codex`，只有 Skill 与参考资料，没有 Python 代码、没有 HTTP 路由、没有工具。

- 目录：`.codex-plugin/plugin.json`（清单）、`skills/repo-engineering/SKILL.md`（工作流）、`skills/repo-engineering/references/myagent.md`（本仓约定）、`skills/repo-engineering/agents/openai.yaml`。
- 依赖：`requirements.txt` 只是记录，插件本身不安装任何包。
- 状态：`standalone` 级，默认停用；启用后 skill 以 `repo-engineering:repo-engineering` 出现在技能目录。

## 热重载

- 改 `SKILL.md` 或 `references/` → 设置页「重新发现 / 热重载」后，技能缓存失效，下一条消息即按新内容加载，不必重启。
- 判定口径见 [插件热重载](../../docs/plugin_hot_reload.md)。
