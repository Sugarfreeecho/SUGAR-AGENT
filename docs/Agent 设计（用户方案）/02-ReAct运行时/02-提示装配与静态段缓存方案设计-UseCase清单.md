# 提示装配与静态段缓存 · 功能方案设计（UseCase 清单）

- 版本：2026-09-13（覆盖至：HEAD `6acc6bf`）
- 用途：逐条审查（四字段格式）。
- 适用实现：`app/agent_loop.py`（静态段构建与重建）、`app/agent_tokenizer.py`（分词/缓存/估算）。
- 上级：`00-ReAct运行时整体设计.md`

---

## 1. 功能定位

决定"模型每轮到底看到了什么"：系统提示、环境信息、技能目录、工具清单——以及它们的**缓存策略**。

## 2. UseCase

### UC-2B1 系统提示多段装配
- **触发**：每轮请求前构建输入。
- **预期现象**：提示由多段组成（prompt.md + 环境/路径模型 + 插件与技能目录 + 工具清单等），内容完整可复现；用户不可见但可通过调试信息检查。
- **规则与边界**：段拼接顺序稳定（对前缀缓存友好）；环境信息中的动态值不破坏整段缓存。
- **依据**：`_build_static_segments_for_session`、`agent_tokenizer.build_static_system_segments / build_env_static`。

### UC-2B2 静态段进程级缓存
- **触发**：连续多轮 / 多会话。
- **预期现象**：提示静态部分不重复重算（响应更快）；技能/插件/工具变更后**最多滞后一次请求**生效。
- **规则与边界**：重建在后台调度（`_schedule_static_segments_rebuild`），不阻塞当前请求；缓存失效由签名驱动。
- **依据**：`_build_static_segments_for_session` + generation 修订、`_skills_tree_signature`。

### UC-2B3 分词与估算
- **触发**：需要判断"输入多大"（压缩判断、界面显示）。
- **预期现象**：估算与实际用量偏差可控；显示为"上下文 xx%"类提示；同一消息序列的估算有缓存（不重复算）。
- **规则与边界**：估算失败回退字/字符系数法（不阻断）；prompt-usage 基线来自真实用量（回写）。
- **依据**：`agent_tokenizer.py`（count/estimate 系列、prompt-usage 基线）。

### UC-2B4 历史消息规整
- **触发**：把会话历史转成模型消息。
- **预期现象**：工具消息成对完整（无"孤儿工具结果"）；给模型的序列合法（端点不会 400）。
- **依据**：`inject_missing_tool_messages / messages_for_openai_turns`。

## 3. 边界

- 每轮输入的**可变部分**（新用户消息、压缩摘要）不入静态缓存。
- 上下文占用显示属观测（见 08/../09-横切能力/04）。

## 4. 依据映射

| 用例 | 代码 |
|---|---|
| UC-2B1/2B2 | `agent_loop.py` L1930–1961 |
| UC-2B3 | `agent_tokenizer.py`（30+ 函数） |
| UC-2B4 | `agent_tokenizer.py` L488–560 |

## 5. 版本记录

- 2026-09-13 v1：拆分首版。
