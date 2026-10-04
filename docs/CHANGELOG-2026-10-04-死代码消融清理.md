# 2026-10-04 死代码消融清理

涉及提交：`4f32aec`（chore(runtime)，24 文件 +9/−364）、`a83b605`（chore(webui)，16 文件 +1/−373）。

## 目标

排查仓库中的死代码/冗余代码，并以"删除 → 编译 → 全量测试"的消融闭环确认可安全删除，保持代码简洁。

## 方法

1. **文本级引用审计**：AST 定界模块级符号（函数/类/赋值），再对全仓（`app/`、`plugins/`、`scripts/`、`tests/`、`frontend/`；含 HTML/JSON 语料）做 token 级计数；经装饰器（FastAPI 路由）或注册表可达的入口一律排除；文档（`docs/`）提及单独登记，避免"删了代码、文档悬空"。
2. **消融验证**：每个删除批次后跑 `py_compile`、全量 `pytest`、`node --check` + node 运行时套件与定向 pytest；任一红灯即回滚该文件。

## 变更（4f32aec · chore(runtime)）

- **runtime_v2 三个整文件死角**：`health_monitor.py`、`permission_manager.py`、`subagent_repository.py` 从未被 import（`SubagentState` 仅存在于后者）；实际子代理存储路径为 `subagent_store.py` 的 `RuntimeSubagentStore`。《用户方案》08 模块依据与能力清单行同步收敛。
- **agent_harness**：删除 `create_openai_client`（被按档案构建器取代）、`resolve_executor_for_session`、`strip_compress_summary_h2_sections`；`_LEGACY_ENV_MODEL_IMPORT = _register_legacy_dotenv_model_profile()` 改为**裸调用**（保留注册副作用，仅去掉无人读取的绑定）。
- **其余 20+ 个零引用助手**：`agent_loop`（`_queue_get_with_timeout`、`_await_maybe`、`_tool_ui_approval_enabled`）、`agent_memory`、`agent_openai`（`_extract_reasoning_text`、`_drain_response`、`_client_supports_modalities`）、`agent_tokenizer`、`webui`（`_upsert_env_line`、`_user_turns_from_ui_events`、`_runtime_v2_ephemeral_sse_payload`）、`desktop_notify`、`model_profiles`、`path_picker_util`、`platform_lifecycle`、`runtime_observability`、`session_event_bus`、`security`（`_CREDENTIAL_TOKEN`、`is_preapproved_url`）。
- **数据/常量与插件/脚本**：`agent_team/models.py` 四个未用状态集、`attachments`（旧别名 `_has_image_payload`、`referenced_ids`）、`game-arena`（未用 `_get_engine`）、`scripts/audit_runtime_versions.py`（未用匹配器）。
- **webui**：`_vision_jobs = _register_vision_api(...)` 改为**裸调用**（保留路由注册副作用）。

## 变更（a83b605 · chore(webui)）

- 删除 23 个前端死函数：`input-actions.bindInputSubmit`；`message-rendering`（`waitForBranchFinalPersisted`、`clearChat`、`getCurrentSessionDataPath`）；`model-profiles.isChatProfile`；`session-management.resendLastUserMessage`；`session-scroll-history`（`refreshAllFeedChunksUnder`、`showRewriteUndoToast`）；`settings`（`getActiveUiTheme`、已被 `applyFontSize` 取代的 `applyFontLevel`）；`shared-state-and-dialogs.buildUserMessageSummary`；dock 的 `dockActionOpenPage/Undo/Redo`、`dockAddressPath`、`dockIsPaneNode/dockIsSplitNode`；state 的 `selectContextProgress`、`renderMessageRecords`、`clearMessageStateForSession`、`selectMessageEventsInRange/Count`、`selectRunForSession`。
- 同步清理 7 条孤儿 JSDoc 注释；dist 重新构建。

## 本地卫生

- 移除 `app/runtime_v2/history_ops.py.bak`（gitignore 覆盖的僵尸备份；已入 `.trash` 可恢复）。

## 保留观察（本轮有意未删）

- `plugin_command_descriptions`、`_invalidate_workflow_callbacks_cache`、`_truncate_unclosed_tool_call_tail`：代码零引用，但《用户方案》仍作为「依据 / 能力条目」引用——建议先做设计稿取舍再删，避免代码-文档脱钩。
- `CoreContent`、`_encrypt` / `load_encrypted_api_key`（XOR 兼容加密模块）：分别被 API 识图方案文档与安全兼容引用，建议单独确认后处理。
- 未做批量清理：跨文件重导出保护后的"全仓零引用导入"为 0（大量"未用导入"实为他处重导出，属假阳性）；未引用 CSS 类未做全量扫描（动态类名误伤风险高）。

## 数据

- 合计 **−737 行**（−364 / −373），40 个文件；全量 `pytest` **2021 passed / 4 skipped**，node 套件 26/26，`node --check` 14 文件全过。
