# Hooks、信任与审计 · 功能方案设计（UseCase 清单）

- 版本：2026-10-21 v5（整组准备及目录SWR回原loop）
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
- **10-21计时补充**：`hook_runtime_definitions`仍覆盖await to_thread的原包络，新增`hook_runtime_definitions_worker`覆盖同步定义函数在执行线程内的工作。两者属于嵌套关系，差额可能含executor等待、派发和返回后的事件循环延迟，不能直接叫作纯队列或磁盘耗时；调用该同步函数的旧入口不一定使用worker线程，名称不作线程身份保证。复用既有计时ContextVar，无payload、无跨派发授权缓存；单worker被占用的受控测试验证叶子在放行后才开始，返回对象和定义调用保持。原始117.774ms包络尚不能证明是定义计算本身慢。

#### UC-6G2 补充：整组准备离开事件循环

- `dispatch_hook`和`warm_hook_pipeline`通过一次等待线程执行目录加载、runtime定义、签名和manager构造，避免目录I/O在共享事件循环阻塞其他会话。`_hook_manager_for_loop`明确接收原loop；Hook实际dispatch、所属loop锁和审计的先后顺序保持，准备完成之前不能执行Hook或发下一API。
- 陈旧签名仍先用已有manager；worker中的刷新请求经`call_soon_threadsafe`回到原loop，再做去重、future注册及完成清理。没有在worker新建事件循环；已关闭loop不安排刷新。实时信任、启停、配置签名和原force读取继续执行，未增加跨派发权限缓存。
- 旧`hook_runtime_definitions`从“定义函数的线程往返包络”变为同一准备线程内的定义区间；新`hook_prepare_await`才是整次准备往返。`hook_prepare_submitted / worker_entered / worker_finished / resumed`及线程标识区分调度、整组工作和恢复；取消时resumed可早于worker_finished，不能机械相减。
- 新用例覆盖阻塞目录读取时loop仍可运行、构造使用原loop、陈旧刷新回原loop且去重、取消准备不执行Hook。功能组合675 passed/1系统符号链接跳过；受控200ms等待只证明减少其他协程连带阻塞，不代表自身准备工作消失或真实500ms达标。见[报告§13](../../performance/agent-subagent-interround-2026-10-21.md#13-事实提交与hook准备的事件循环隔离补修)。
- **自然加载后补修**：整组worker必须将原loop继续传入`load_plugins(refresh_loop=loop)`。初版遗漏这一点，使TTL过期目录在worker无法安排SWR而同步扫描，实际样本加载区间达11.195秒。现经原loop线程安全调度目录刷新、立即复用同键旧目录，并核对排队与发布generation；force/冷缓存/无可用loop仍等待。6项新增目录用例与既有Hook/启停组合39项通过，完整门禁及该补修未被23:22进程加载的边界见[报告§14](../../performance/agent-subagent-interround-2026-10-21.md#14-2322自然重启与hook目录刷新回退补修)。
- **排队守卫终态**：执行排队回调前还核对同键和新鲜度，目录已更新/配置已切换便不再发起旧扫描。补2例后目录新增例共8项，最终相关定向27项通过、源码无漂移；范围和此前完整门禁的剩余目录退役失败分别记录，不相加测试数。

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

- 2026-10-21 v5：按自然运行补修Hook worker的插件目录SWR调度；原loop、generation、强制读取和无loop回退保持，披露初版加载回退与验证限制。

- 2026-10-21 v4：整组Hook准备合并到一次等待线程执行，保留原loop和实时授权；刷新回所属loop去重，补齐线程/恢复端点及取消验证，旧定义计时口径另行标明。

- 2026-10-21 v3：为同步定义函数增加线程内叶子计时，保留await包络与信任/启停语义；受控排队验证，不把包络预设为定义计算或磁盘成本。

- 2026-10-18 v2：同次Hook派发/预热复用已加载资源，保留强制刷新、信任、开关和审计。
- 2026-09-13 v1：拆分首版（承接 UC-610~612）。
