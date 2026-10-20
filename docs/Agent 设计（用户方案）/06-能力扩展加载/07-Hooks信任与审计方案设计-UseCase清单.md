# Hooks、信任与审计 · 功能方案设计（UseCase 清单）

- 版本：2026-10-18 v2（同次派发复用插件目录）
- 用途：逐条审查（四字段格式）。
- 适用实现：`app/hooks.json.example`、`agent_extensions.py`（L106–1060、L1202–1398）、`security/extensions.py`。
- 上级：`00-能力扩展加载整体设计.md`

---

## 1. 功能定位

扩展体系的安全侧：钩子定义/装载、信任门槛、审计留痕——"谁能动、动了记什么"。

## 2. UseCase

### UC-6G1 hooks.json 定义与装载
- **触发**：配置 `hooks.json`（事件/matcher/命令/超时/env 白名单）。
- **预期现象**：钩子按平台选择命令（windows_command/unix_command）；matcher 精确命中（如只拦写类工具名）；超时受控。
- **依据**：`hooks.json.example`、`_build_hook_manager / _runtime_hook_definitions`。

### UC-6G2 钩子签名与重建
- **触发**：hooks 文件或插件钩子变化。
- **预期现象**：签名变化触发管理器重建（SWR）；重建期间旧集合可用；无重复执行。
- **依据**：`_hook_signature / _schedule_hook_manager_rebuild / hook_manager_for_current_loop`。
- **10-18补充**：一次`dispatch_hook`或预热已取得的`PluginLoadResult`继续用于本次manager签名计算，不在同次派发里再次解析插件manager和目录。`force=True`仍强制重新加载；没有新增跨派发缓存或延长TTL。Hook实际执行、信任检查、文件签名、启停与审计路径保留。覆盖见`tests/test_runtime_noop_persistence.py`及插件集成/runtime回归。

### UC-6G3 钩子审计三件套
- **触发**：钩子开始/结束/失败。
- **预期现象**：分别记录"开始（决策前）""结果（允许/拒绝理由）""分发失败"三类审计事件；可追溯"谁因哪条钩子被拦"。
- **依据**：`_audit_hook_started / _audit_hook_result / _audit_hook_dispatch_failure`。

### UC-6G4 扩展信任与撤销
- **触发**：新扩展首次出现；用户信任/撤销信任。
- **预期现象**：未信任 → 不生效（工具不发、UI 不注入）；信任后放行；撤销后立即回退效果。
- **依据**：`security/extensions.py`、`get_security_extensions / trust_security_extension / revoke_security_extension`。

### UC-6G5 清单审计
- **触发**：诊断/排查。
- **预期现象**：`audit_plugin_inventory` 给出全量扩展清单（含来源、版本、信任、启用态）；缺项可见。
- **依据**：`audit_plugin_inventory`（L1398）。

## 3. 边界

- 钩子**运行时**的调用点语义见 ../02-ReAct运行时/06；
- MCP 的信任决策单独流程（../06-能力扩展加载/06 UC-6F6）。

## 4. 依据映射

见上表。

## 5. 版本记录

- 2026-10-18 v2：同次Hook派发/预热复用已加载资源，保留强制刷新、信任、开关和审计。
- 2026-09-13 v1：拆分首版（承接 UC-610~612）。
