# CHANGELOG — 2026-09-01/04（codex-ds 会话批次）

本批次改动全部来自 **codex-ds（DeepSeek 版 Codex）** 在 9/1–9/2 的六个工作会话，按会话分别提交。

## 会话一（9/1 18:51）— 滚动修复接手

- 接手 MyAgent 会话 39049381 的丝滑滚动任务并继续修复；验证结论后落地滚动相关改动。
- 文件：`message-rendering.js`。

## 会话二（9/1 19:45）— 模型配置迁移与模型类型一致性

- 接手 9b324cf9 的模型配置迁移任务：`PROVIDER_SEMANTICS_VERSION`、`canonicalLlmType` 对比；切换模型时模型类型不一致弹窗（"模型类型不一致，有 xxx 风险"，取消则中断切换）。
- 文件：`model_profiles.py`、`llm/__init__.py`、`agent_openai.py`、`advance_config.html`、`model-profiles.js`、`test_model_profiles.py`。

## 会话三（9/2 10:17）— 工作区外审批改为目录授权审批

- **目录授权审批**：授权目录与会话绑定（复制/分支/子 Agent 会话可继承）；默认授权 WORK_DIR，越出目录访问新同级/上层目录需申请授权。
- 删除文件黄框审批范围由 WORK_DIR 改为已授权目录；`session_authorized_dirs.py` 新建。
- 文件：`session_authorized_dirs.py`（新）、`security/policy.py`、`security/runtime.py`、`agent_loop.py`、`webui.py`。

## 会话四（9/2 11:15）— 空会话排查

- 排查"突然蹦出大量空的新会话"问题，修复会话创建/列表相关逻辑。
- 文件：`session-management.js`、`test_agent_harness_executor_session.py`。

## 会话五（9/2 13:11）— 命令拦截原因展示

- 审批卡片在【命令风险】【命令目的】前新增【**拦截原因**】字段，说明命中哪条策略（如"命中工作区删除 process.workspace_delete"）。
- 文件：`security/reviewer.py`。

## 会话六（9/2 17:02）— 模型自动切换失败修复

- 修复 muse-spark-1.2-contributor 自动切换失败（400 错误）：provider 类型/传输层适配（方案 A）。
- 文件：`llm/transport.py`、`agent_harness.py`、`test_llm_transport.py`。

## 相关提交

- `feat(webui): smooth-scroll handoff fixes (codex-ds 9/1 18:51)`
- `feat(llm): model config migration and canonicalLlmType consistency (9/1 19:45)`
- `feat(security): directory-authorized approval outside workspace (9/2 10:17)`
- `fix(webui): stray empty-session creation (9/2 11:15)`
- `feat(approval): show interception reason on approval cards (9/2 13:11)`
- `fix(llm): model auto-switch failure and provider transport (9/2 17:02)`