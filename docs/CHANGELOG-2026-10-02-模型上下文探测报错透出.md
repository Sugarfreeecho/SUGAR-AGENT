# 2026-10-02 获取模型上下文失败时直接透出真实报错

## 现象

在「高级设置 → 模型配置」点击「获取模型上下文」（首次配置向导同名按钮）后，只要探测没成功，状态栏只有一句泛化提示——「未从 API 错误消息取得真实上下文窗口，已保留列表/默认窗口；探测请求可能已消耗 API 额度。」——看不到真正的失败原因：鉴权被拒（401）、模型名不存在（404）、端点不可达（连接超时），还是 400 响应里没有可解析的窗口 tokens，全都显示同一句话。

## 根因

- 后端 `model_profiles.probe_context_window_from_error` 把所有失败路径（网络异常、非 400 状态、400 但没匹配到窗口数字）统一吞成 `return 0`；调用方 `probe_model_context` 只上报 `probe_succeeded: false`，原始 HTTP 状态与响应体、异常文本全部丢失。
- 前端只能拿到布尔结果，因此只能显示泛化文案。
- 历史对照：最初实现（4aaca8b）在失败时状态栏是「上下文探测失败，已使用列表/默认窗口：<err.message>」；26608d3 换成泛化文案后该信息消失，但 `setup_i18n.js` 中对应的翻译规则 `^上下文探测失败，已使用列表\/默认窗口：(.+)$` 一直保留至今。

## 变更

- `app/model_profiles.py`
  - 新增 `probe_context_window_from_error_detail()`：保留原探测语义，额外返回失败详情——网络异常为 `异常类名: 消息`；HTTP 响应为 `HTTP <状态码> <原因短语>: <响应体片段>`（空白折叠、截断 400 字符）。原 `probe_context_window_from_error()` 变成只返回 token 数的兼容包装，既有调用方与测试不受影响。
  - `probe_model_context()` 返回增加 `probe_error` 字段（成功或未发起探测时为空串）。
- `app/webui.py`：`/api/model_profiles/probe` 在探测失败时用 `logger.warning` 打服务端日志（模型 ID + 详情，不含 API Key），便于在日志里直接看到报错。
- `app/templates/advance_config.html`、`app/templates/first_time_config.html`：状态栏拿到 `probe_error` 时直接显示「上下文探测失败，已使用列表/默认窗口：<详情>」（复用既有文案与 i18n 规则，英文模式同步翻译）；没有详情时保留原泛化文案。另把 `resp.json()` 解析失败兜底为 `HTTP <状态码>（响应无法解析为 JSON）`，不再吞成无信息的 SyntaxError。
- i18n：无需新增规则——`setup_i18n.js` 既有规则覆盖新消息，已用脚本验证中英往返。

## 测试与验证

- 新增回归（`tests/test_model_profiles.py`）：400 未匹配响应体返回详情；401 时 `probe_error` 含状态与 API 报错原文；连接异常时含异常文本；成功时 `probe_error == ""`；两个页面与 i18n 的契约断言。
- 定向：`tests/test_model_profiles.py` → 42 passed；`tests/test_llm_transport.py`、`tests/test_enablement_ui_contract.py`、`tests/test_feature_flags.py`、`tests/test_agent_extensions_integration.py` → 146 passed；`tests/test_webui_*.py` → 70 passed；`py_compile` 通过。
- i18n 校验：对「上下文探测失败，已使用列表/默认窗口：HTTP 401 Unauthorized: {...}」执行既有翻译规则，输出 `Context probe failed; using listed/default window: ...`。
- 未做真实浏览器点击验证（按钮会向真实模型 API 发探测请求、消耗额度），改动为状态栏文案与请求兜底逻辑，已由契约测试覆盖。

## 文件

- `app/model_profiles.py`、`app/webui.py`
- `app/templates/advance_config.html`、`app/templates/first_time_config.html`
- `tests/test_model_profiles.py`
