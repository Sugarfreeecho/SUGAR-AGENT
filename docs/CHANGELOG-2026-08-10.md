# CHANGELOG — 2026-08-10

本批次改动围绕 **LLM 传输稳定性、CPU 自适应降级、Goal/Ask 状态机、前端体验与构建性能** 展开，全部来自 2026-08-10 的迭代（对应 Codex 会话记录 `~/.codex/sessions/2026/08/10`）。改动已按主题分类提交。

## 一、Agent 运行时（性能与可靠性）

### 1. CPU 压力自适应降级（新）
- 新增 `app/cpu_pressure.py`：守护线程按 1s 采样主机 CPU，采用 **85% 进入 / 65% 恢复** 的滞回机制防止模式抖动。
- LLM 请求在 CPU 高压时统一切换为**非流式输出**，恢复后还原逐 token 流式输出（`_llm_runtime_policy`）。
- 内部压缩/关键上下文调用遵循同一进程级策略（`agent_harness.py`）。
- 工具并发在高压时降为 2（`CPU_PRESSURE_TOOL_CONCURRENCY`）。
- 新增依赖 `psutil>=5.9,<8`；`app/main.py` 启动/停止监视器。

### 2. 流式输出合并（新）
- `_ThreadToAsyncQueue`：首 token 立即推送，后续文本增量按 **12ms** 帧合并（`LLM_STREAM_COALESCE_MS`），减少浏览器渲染与持久化压力。

### 3. 首 token 并行重试（hedge，新）
- 首 token 30s 未收到时并行发起第二路 API 请求，原连接保持；谁先返回首 token 即采用谁，关闭另一路，避免单次 API 卡顿拖死整个回合。
- 可配置：`OPENAI_FIRST_TOKEN_HEDGE_TIMEOUT_SEC`（默认 30，0 关闭）、`OPENAI_FIRST_TOKEN_HEDGE_MAX_RETRIES`（默认最多 2 次）。
- 相关调优：`OPENAI_HTTP_TIMEOUT` 600→300s、`OPENAI_MAX_RETRIES` 3→4。
- 附带优化：流式正文累积由字符串拼接改为 list 累积 + 末尾 join（`agent_openai.py`）。

### 4. 可观测性缓冲写盘（新）
- `execution_metrics.py` / `runtime_observability.py`：新增内存缓存 + **200ms 防抖整文件重写**（`*_FLUSH_DELAY_MS`）、60s 全量扫描（`RUNTIME_OBSERVABILITY_FULL_SCAN_SECONDS`）、终端状态立即落盘、`atexit` 兜底 flush。
- `runtime_power.py`：每个事件循环共享一个原生挂起监视器（`_RuntimeSuspensionBroker`），避免多 run 重复启动监视线程。

### 5. Goal 状态修正
- Goal 仍为 `active` 时，每轮 `final` 不再把会话标记为"绿色完成"；仅在 Goal 真正完成/暂停/阻塞后标记（`_sync_goal_unread_result`、`session-event-reducer.js`）。
- Goal 使用量按轮次增量记录（`_goal_usage_recorded_calls`），避免重复计费。
- GoalManager 改为 weakref 缓存单例；新增 Goal 活动状态跟踪与订阅。

### 6. 子代理运行时模型切换（新）
- 新增 `switch_subagent_model_profile`：在安全 ReAct 边界原子切换子代理模型，保留 child ID、历史、worktree 与任务归属。
- 元数据记录 `model_switch_history`（保留最近 50 条）与 `last_model_switch`。
- 前端新增 `subagent-actions.js` / `subagent-renderers.js` 支持。

## 二、工具与审批

### 7. `ls` 工具重构
- LLM 工具只暴露 `ls`（执行层保留 `list_dir` 兼容映射）。
- 仅对**已识别的文本/源码文件**统计行数；压缩包（zip/7z/rar/tar/gz 等）大小与行数均显示 `—`。
- 单文件行数统计上限 **5 MiB**（`LS_LINE_COUNT_MAX_BYTES`），超限显示 `— (>5.0 MiB)`。
- 配套检查清单 `docs/ls_tool_change_checklist.md`。

### 8. 审批卡片"替我分析"（新）
- 手动审批卡新增"替我分析"按钮：复用审查模型给出风险等级与建议，**不执行授权**。
- 审查上下文仅存于待审批请求的内存生命周期，审批结束后清除；审批请求携带 `user_intent`。

## 三、前端体验

### 9. 会话操作菜单与归档刷新
- 三点菜单重构：置顶 / 重命名 / 归档会话为一类，导出 / 删除为一类；重命名与导出均改为弹窗交互。
- 标题栏会话名称后常驻显示同一套操作菜单。
- 取消归档后**自动刷新归档目录**；"加载更多"支持自动触发。
- 会话导出：压缩 session 目录并在浏览器下载。

### 10. 输入框发送逻辑统一
- 新增 `input-actions.js`：IME 组合输入判断、Enter 提交 / Ctrl+Enter 换行、隐藏字符清洗。
- 主输入框 `input` 监听由 3 个合并为 1 个，发送时只计算一次运行态/上传态/有效文本/待回答状态。

### 11. 其他前端修复
- hover 浮窗：显示前校验 DOM/hover 状态，鼠标移开/滚动/失焦自动关闭残留浮窗（`toc-todo.js`）。
- 模型 hover 详情新增 `model_porfile_id` 显示。
- Ask 追问：待回答 Ask 会阻塞自动发送队列；切换会话不丢失中间轮次。

## 四、桌面通知

### 12. 通知修复
- 修复 Toast 按钮中文乱码（UTF-8 文本经环境变量传递，PowerShell 脚本保持 ASCII）。
- 通知按钮改为 `rundll32 url.dll,FileProtocolHandler` 无控制台窗口启动浏览器，不再闪现终端。
- 通知 helper 超时 20s 强制终止。

## 五、构建与配置

### 13. 前端构建优化
- Mermaid 改为本地预构建 vendor（`/assets/vendor/mermaid.min.js`），构建时间由约 4 分 48 秒降至 **2.21 秒**（Vite 自报 1.26s，转换模块 1627→45）。
- 生产构建与开发服务器分别处理 vendor 资源（`vite.config.js`）。
- 已重新生成 `app/templates/dist`。

### 14. 配置项
新增环境变量（均已在 `app/.env.example` 登记）：
`CPU_PRESSURE_*`、`LLM_STREAM_COALESCE_MS`、`LLM_FULL_CALL_TRACE`、`OPENAI_FIRST_TOKEN_HEDGE_*`、`EXECUTION_METRICS_FLUSH_DELAY_MS`、`RUNTIME_OBSERVABILITY_FLUSH_DELAY_MS`、`RUNTIME_OBSERVABILITY_FULL_SCAN_SECONDS`、`LS_INCLUDE_LINE_COUNTS`、`LS_LINE_COUNT_MAX_BYTES`。

## 六、其他

- 工作区范围许可入口迁移至「高级设置 → 安全与权限」页签，并补充中英文文案。
- 测试基础设施：`tests/conftest.py` 默认关闭测试进程的桌面通知；新增 CPU 压力、性能优化、LLM 传输计时、输入框运行时、会话菜单/归档/导出、桌面通知等测试。
- 个人审查笔记 `review/` 目录加入 `.gitignore`，不纳入版本库。