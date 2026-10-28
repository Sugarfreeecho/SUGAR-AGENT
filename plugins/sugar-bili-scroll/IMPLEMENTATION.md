# 开发接手 · 实施与验收记录

> **读法提示（2026-10-27 补）**：下面的部署记录写于 0.2–0.5 阶段，当时插件路由清理还没按路径实现，所以多条记录写着「首次加载需重启」。当前口径已变：插件目录内的任何改动（含 `host.py` 路由、兄弟模块、MCP）用「重新发现 / 热重载」即可生效，只有改宿主 `app/*.py` 或 `.env` 才需要重启，见 [插件热重载](../../docs/plugin_hot_reload.md)。历史记录按阶段保留，不作为当前操作依据。

记录始于 2026-10-23，更新至 2026-10-25（Asia/Shanghai）。承接 MyAgent 会话 `4bc203cb-adb5-4a8e-8ada-c9f299c3e7c6` 的 dsh-bili-scroll → sugar-bili-scroll UC 项目。当前清单版本为 0.5.0；新增独立完整系统提示词的实现和 210 项回归见 [SYSTEM_PROMPTS.md](SYSTEM_PROMPTS.md)，多账号功能见 [MULTI_ACCOUNT.md](MULTI_ACCOUNT.md)。下文按阶段保留验收记录。

## 原 10 项逐项结论

以下“完成”指源码与隔离验证；生产宿主重启和真实平台发送另列，不能混为上线验收。

| 原任务 | 接手发现 | 此次交付 |
| --- | --- | --- |
| 1. 修复工具不可用 | 冷实例修复已有真实运行证据，调度仍会自阻塞 | 保留冷实例恢复；修正调度 busy 自阻塞并回归 |
| 2. 固定 system_context | 会话具备该字段，任务新会话 ID 没可靠保存 | 每任务 / UID / 评论楼层固定上下文，持久会话绑定；新会话 ID 保存正确 |
| 3. 补齐其他工作 | UC 接线和维护项未完 | 表情组合链路、日志轮转、迁移、错误记录及文档统一 |
| 4. 会话执行与单轮工具范围 | 全局 session_id 字典不是真正运行隔离 | ContextVar 执行范围、run_id 持久授权、会话占用和 finally 清理 |
| 5. 范围、可见性、缓存 | 空列表可能回退全工具，任务设置未贯穿 | 显式零工具、目录过滤、调用时最新校验，缓存键包含空范围语义；发现桥接不能恢复被禁工具 |
| 6. 白名单、steer、发送记录 | 白名单未真正控制会话能力，sent 标记失真 | 白名单拥有启用业务工具，陌生人零工具；插入当前会话；真实发送意图与回执 |
| 7. 即时私聊与任务回复 | 私聊仍要求调用发送工具，公开回复目标读取错位 | 每 UID 普通回复投递；评论按 BV + 根楼层排队；目标固定；500 字整轮校验 |
| 8. 多任务调度与隔离 | A 的额度、间隔和报告会影响 B | 每任务独立状态、额度、窗口、间隔、预算、会话、日报 / 归档；全局判重；入站不阻塞值班轮询 |
| 9. 任务 CRUD / 运行接口 | 有路由但无效 ID 会回退、停用仍可跑 | GET/POST/PATCH/DELETE/运行接口验证、精确 ID、同源写入和路径校验，保留显式 0 |
| 10. 页面编辑、立即跑和今日数 | 编辑与真实计数不完整 | 完整编辑表单、任务今日 / 剩余 / 轮数 / 错误、分任务日报、入站状态 / 重试 / 核对；桌面与窄屏浏览器验收 |

## 本次确认并落实的设计

1. 评论、@、回复评论按同视频同根楼层复用会话。
2. 白名单使用全部已启用的 B站业务能力，包括转写、表情收藏、评论回复；不开放命令和文件工具。
3. 从未刷过的视频下的 @ 也回复，由独立“回复评论”开关控制。
4. 白名单可通过私聊要求在指定视频发布公开评论，私聊正文仍由宿主按回复条目发送。
5. 私聊每条不超过 500 字符；任一条超长则整轮私聊不发、记录错误，不拆分、不截断、不自动重生成。

## 重要修复

- SQLite 事务同时提交轮询游标与待处理项，避免推进游标后丢失失败消息；首个成功拉取按渠道静默初始化。
- 整轮私聊正文通过校验后一起保存，限流或重启按原文续发；发送不确定时停止自动重发，支持人工核对后继续其余条目。
- 运行授权和图片 / 评论 / 表情额度保存到同一数据库，冷实例共用限额。调用时及队列重放时重新校验相应写入授权。
- 新增 `bili_record_video`，让宿主掌握挑选、跳过、额度和判重事实；模型无需文件或命令工具。报告文字不能伪造额外 BV 配额标题。
- 旧报告和状态只映射给原任务，不复制给所有任务；保持原数据并记录固定额度基线。
- 转写跨会话共用串行锁，宿主引擎正确接受 0 分钟“不限制”；表情库改用跨循环可用的磁盘锁。
- `duty.log` 1 MiB 轮转、保留 3 份历史。空结果 / 模型失败的值班轮也留下简短日报记录（关闭日报除外）。

## 验证

0.3.1 实机排查确认私信无响应同时涉及入站总开关关闭与 B站接口 `-101`。已打开总开关，修复凭证有效性检查、重新扫码入口、轮询错误显示和认证失败暂停模型；相关会话、UC、权限及浏览器回归 96 项通过。重新授权需要用户扫码，不能将保存了旧凭证当作已经登录。

后续测试准备补充：核对在线设置 API 发现真实响应为 `settings.fields`，页面误读顶层 `fields`。已修复并增加按真实响应结构加载、保存设置的浏览器回归，3 项通过。此结果单列，不把此前 164 项视作已经覆盖该缺陷。逐项手工步骤见 [UC_TESTING.md](UC_TESTING.md)。

最终综合回归：**164 通过、2 跳过**。跳过的两项均为 Windows 无目录符号链接权限（WinError 1314），不涉及本插件业务。浏览器两项包含在 164 项内；使用临时数据和被拦截的 HTTP 请求。

```powershell
.\python\python.exe -m pytest tests\test_sugar_bili_scroll_tasks.py tests\test_sugar_bili_scroll_workflows.py tests\test_run_tool_scope.py tests\test_session_system_context.py tests\test_host_catalog_availability_scope.py tests\test_agent_subagent_runtime_v2.py tests\test_tool_registry.py tests\test_tool_search.py tests\test_tool_naming.py tests\test_plugin_storage.py tests\test_sugar_bili_scroll_browser.py -q
```

插件清单经宿主 `load_plugin` 校验，可识别 `sugar-bili-scroll 0.2.0`；插件及两份宿主源码共 12 个 Python 文件通过 AST 解析。相关已跟踪文件通过 `git diff --check`。

覆盖行为：

- 任务独立性、零值、全局判重、迁移、调度 tick、持久会话。
- 白名单 / 陌生人目录与实际调用，撤销开关及白名单、目标固定、跨运行隔离。
- 私聊完整条目、500 / 501 字、重复最终正文、steer、线程复用。
- 游标与队列、同秒事件、失败首轮渠道、限流续发、超时不确定、重启续发及人工核对。
- 表情收藏 → 标签 → 搜索 → 带图评论组合，6 MiB 收藏 / 2 MiB 上传边界。
- 真实宿主执行入口（模型和传输替身）、真实 HTTP 路由、浏览器编辑与窄屏布局。

`tests/evidence_check.py` 只启动隔离 pytest，不再操作真实会话或账号。浏览器测试拦截所有 HTTP 请求。

## 部署边界与材料

更新：0.3.0 独立系统提示词已按用户授权经托盘重启加载，并完成在线接口及真实浏览器检查，见 [SYSTEM_PROMPTS.md](SYSTEM_PROMPTS.md)。下面保留 0.2.0 主开发阶段的部署边界。

本次未重启现有宿主，未调用真实评论 / 私信发送接口，未修改实际任务配置、凭证或原会话事实日志。现有宿主仍需在合适窗口重启后确认加载 0.2.0，再用可控账号做真实消息与公开可见性验收。

接手前副本在 `.analysis/sugar-bili-scroll-implementation-20261023/before/`；浏览器截图在同目录 `screenshots/`。宿主 `app/agent_loop.py`、`app/agent_subagent.py` 只在已有修改上补充运行工具范围语义；其他会话原有工作保留。

历史审查见 [DEVELOPMENT.md](DEVELOPMENT.md)，当前使用说明见 [README.md](README.md)、[INBOUND.md](INBOUND.md)。

0.3.2：新增本地退出登录、强制切换账号、取消扫码和登录 UID 显示。正在进行的 B站任务阻止退出/换号；扫码取消采用代次校验，丢弃取消后的请求结果；入站消息按账号独立去重与绑定回复会话，换号后停止旧任务、重新静默初始化，保留旧回执。相关任务、消息流程、浏览器、工具权限与会话系统提示词回归 **104 项通过**。

0.4.0（2026-10-24）：按用户选择实现保存多个登录态、每次启用一个账号。SQLite 保存账号凭证，当前文件表示单一启用账号；原凭证自动纳入，新增扫码保留旧账号，同 UID 更新而不重复；退出保留，显式移除才删除。切换前验证，失效、网络错误和 UID 不匹配时保留当前账号；切换验证期间暂停新任务，运行中禁止切换／移除。账号 API 只返回元信息。账号存储、HTTP、浏览器、原 UC、工具范围和系统提示词相关回归 **114 项通过**。测试使用临时凭证与认证替身，没有真实消息投递。

0.4.0 已在无运行中会话／B站任务时通过常驻托盘重载。在线账号列表接口可用，跨来源启用／移除均返回 403；真实浏览器桌面和 390 px 窄屏均显示账号控件，无 JS 错误和水平溢出。核对时没有启用或保存账号，入站总开关继续关闭；没有自动启用账号、发起真实扫码或发送消息。记录及截图位于 `.analysis/sugar-bili-scroll-multi-account-20261024/`。

0.4.1（2026-10-25）：新增模型可调用的 `bili_favorite_add(bvid, fid=0)`。普通会话和白名单互动可使用；值班自动收藏仍由宿主执行。显式收藏夹优先于配置，未配置时不猜目标；校验当前账号收藏夹、参数及最新白名单，查询期间换号或撤销权限会阻止写入。收藏失败返回失败结果。相关 UC、账号、浏览器、工具范围和系统提示词回归 **129 项通过**，含 15 项新增收藏工具用例；全部使用传输替身，没有向真实 B站账号收藏视频。

0.4.1 部署状态：在线核对有 1 个其他运行中的 Agent 会话。用户明确选择“暂不重启，保留已完成代码”，因此未重启后端，新工具尚未完成在线加载验证，待下一次后端重启生效。


## 0.5.0：MCP工具与随包Skill（2026-10-25）

按用户要求将14个B站业务工具改为MCP注册：manifest声明`.mcp.json`，服务名`sugar-bili-scroll/bili`，使用宿主进程内的Streamable HTTP端点`/api/sugar-bili-scroll/mcp/`。trusted_host继续提供调度、入站、控制台和ASR服务；原生工具目录入口返回空，避免同时注册两套工具。传输端口随`MYAGENT_SERVER_PORT`，默认8192。

宿主MCP适配新增可选`host_context`元数据通道：Agent循环传递真实session/run/tool_call，连接器在模型参数之外发出一次性随机票据；服务核对票据绑定的服务、工具、参数和有效期，再使用原有持久运行授权校验。缺少、伪造、重放或目标不匹配均拒绝；停用后关闭服务，重新启用创建新的会话管理器。票据仅保存在当前宿主进程中，外部MCP客户端不能伪造SugarAgent会话权限。无此配置的其他MCP服务保持原调用方式。

自动会话白名单范围映射为MCP函数名，持久业务策略仍用bili_*短名；完整系统提示词和轮次提示中的短名在渲染时转换。固定发布14个schema，每次实际调用重查开关/白名单/楼层/收件人/额度；普通会话也校验转写开关。MCP效应契约区分读取、本地插件数据写入和B站写入；本地写工具不声明Git工作树隔离兼容，受宿主工作树校验约束。

新增随包`skills/bili-scroll/SKILL.md`，宿主识别为`sugar-bili-scroll:bili-scroll`，四份参考指导分别覆盖Agent管理、工具使用、用户配置、功能介绍。管理助手支持status/doctor/register/disable/uninstall；默认doctor只读，不调用会创建诊断会话的diagnose接口。卸载通过宿主安装器；bundled源码不在可写安装目录时如实失败，并在Skill说明停用、保留运行数据和显式移走源码的恢复步骤。

首轮扩展回归发现旧`test_mcp_result_status`替身没有模拟“禁用状态已成功加载”标志，修正测试隔离，保留生产代码读取失败时拒绝调用的行为。综合回归 **203项通过**（包含6项真实MCP协议/身份/生命周期/ASR/收藏测试、7项Skill助手/参考文档测试，其他为原业务、浏览器、工具范围、会话上下文及MCP通用回归）。平台调用均为替身，不使用真实B站写入。

```powershell
.\python\python.exe -m pytest tests/test_sugar_bili_scroll_mcp.py tests/test_sugar_bili_scroll_skill.py tests/test_sugar_bili_scroll_favorite_tool.py tests/test_sugar_bili_scroll_tasks.py tests/test_sugar_bili_scroll_workflows.py tests/test_sugar_bili_scroll_accounts.py tests/test_sugar_bili_scroll_browser.py tests/test_run_tool_scope.py tests/test_session_system_context.py tests/test_mcp_result_status.py tests/test_agent_mcp_cache.py tests/test_mcp_registration_switch.py tests/test_mcp_tool_selection.py tests/test_mcp_background_catalog.py tests/test_mcp_state_read_failures.py -q
```

Skill通过skill-creator的quick_validate；清单由实际插件加载器发现MCP和Skill。实施前备份位于`.analysis/sugar-bili-scroll-mcp-skill-20261025/before/`。保留同工作区其他会话的修改。

部署状态：继续遵守用户“暂不重启，保留已完成代码”的选择；没有重启/重载在线后端，没有修改实际登录态、白名单、任务或自动回复开关。首次加载本版需要重启Agent后端；上述是源码及隔离协议验证，不代替在线版本和真实平台发送验收。


最终合并验收：**356项全部通过**，2项为已安装websockets/uvicorn的弃用提示。包含上述203项，以及工具命名/搜索/注册表、宿主可用性目录、会话工作区、工具审批准备、共享可观测性、Skill管理、插件宿主服务与目录加载检查。扩展检查另修正宿主可用性目录在读取失败时本次目录内重复重读的问题，缓存失败仅限当前检查，下次目录或实际调用重新读；对应替身通过manager.is_enabled模拟真实读路径，执行时再次校验会额外读一次。5项可用性目录检查通过。

最终命令：

```powershell
.\python\python.exe -m pytest tests/test_sugar_bili_scroll_mcp.py tests/test_sugar_bili_scroll_skill.py tests/test_sugar_bili_scroll_favorite_tool.py tests/test_sugar_bili_scroll_tasks.py tests/test_sugar_bili_scroll_workflows.py tests/test_sugar_bili_scroll_accounts.py tests/test_sugar_bili_scroll_browser.py tests/test_run_tool_scope.py tests/test_session_system_context.py tests/test_mcp_result_status.py tests/test_agent_mcp_cache.py tests/test_mcp_registration_switch.py tests/test_mcp_tool_selection.py tests/test_mcp_background_catalog.py tests/test_mcp_state_read_failures.py tests/test_tool_naming.py tests/test_tool_search.py tests/test_tool_registry.py tests/test_host_catalog_availability_scope.py tests/test_session_workspace_paths.py tests/test_tool_review_preparation.py tests/test_runtime_observability_shared.py tests/test_skills_admin.py tests/test_plugin_host_services.py tests/test_plugin_catalog_loading.py -q
```

## 0.6.0：发现、个人列表与互动工具（2026-10）

按用户「把能加的加上」的要求，工具从 14 个扩到 20 个，新增：

| 工具 | 效应 | 说明 |
|---|---|---|
| `bili_discover` | read | hot / weekly / rank / up / feed / related 六个来源 |
| `bili_my_list` | read | toview / favorites / history |
| `bili_highlights` | read | 弹幕按窗口聚合，找最热闹的几分钟 |
| `bili_capabilities` | read | 账号、开关、本轮可用工具 |
| `bili_watch_later_add` | external_write | 加入稍后再看，`allow_toview` 默认开 |
| `bili_interact` | external_write | like/unlike/triple/coin/follow，四个开关默认关 |

`bvid` 参数改为统一解析：BV 号、`av` 号、带 `?p=` 的完整链接、`b23.tv` 短链。解析放在 `workflow.authorize` 之前，保证「用链接传参」和「用 BV 号传参」走同一条权限路径，值班的 `picked` 校验无法被链接绕过。

权限模型：读取类进 `BUSINESS`（白名单会话按白名单收窄）；写入类只在对应开关打开时进入 `allowed()` 名单，真正调用时 `_authorize_interact` 再查一次，值班任务额外要求本轮 `bili_record_video` 已记录 `picked`。投币次数用 `runs.coins` 计数，旧库通过 `PRAGMA table_info` 检测后 `ALTER TABLE` 补列。

真实接口核对（只读，未做任何 B站 写入）：`hot`/`rank`/`up`/`related`/`history`/`toview` 字段映射正确；`feed` 在该账号（关注 0 人）下返回 0 条并给出 `note`；`highlights` 对一条热门视频采样 5923 条弹幕，输出 0:00（781）、1:00（629）、8:30（313）三个峰值窗口；`av170001 → BV17x411w7KC`、带参数的链接解析正确。核对中发现并修掉两处真实问题：`get_related` 在 17.4.2 返回 list 而非 dict；`User.get_videos` 匿名请求会吃 412，改为带登录态并统一把风控错误压成一句话。

回归：新增 `tests/test_sugar_bili_scroll_discover.py`（9 项，覆盖解析、六个来源映射、个人列表、弹幕分桶、写入失败如实上报、开关与额度、目录效应声明、参数解析在权限校验之前、capabilities）。相关 7 个文件合计 **110 项通过**；`test_new_dm_is_steered_into_existing_run`、`test_real_runner_scopes_tools_forwards_rows_and_releases_reservation`、`test_runner_failure_restores_scope_and_job_can_retry` 三项仍失败，原因是工作区里未提交的 `session_control` 重构（`_bind_session`/`_run_round_blocking` 改走控制面）没有对应的测试替身，属于既有问题，与本版工具无关。

部署状态：未重启后端，改用 `POST /api/extensions/reload` 热重载。首次重载暴露了两个只热一半的问题：`_load_sibling()` 用固定模块名，`sys.modules` 让 workflow/bili_client/store 继续跑旧代码（表现为 MCP 已是 20 个 schema、`bili_capabilities` 仍只列 9 个工具、`bili_discover` 直接报错）；`install()` 每轮都追加一套路由，旧处理器先匹配。修法：模块名带文件内容摘要；`install()` 注册前摘掉上一轮路由；`manage.py` 的工具数断言从写死 14 改为 `EXPECTED_TOOLS = 20`。修复后再重载验证：MCP 20 个工具已连接、设置 35 项含 6 个新开关、`bili_capabilities` 列出新工具、`bili_discover(hot)` 与 `bili_my_list(history)` 实调成功、`doctor` 回到 `ok: true`。未对真实账号执行点赞、投币、三连、关注或加入稍后再看。

## 统一会话控制接入（2026-10-27）

会话绑定和 Prompt 更新改由宿主公共控制服务处理；业务轮次、单轮工具范围、预算、私信追加与撤回共用持久入箱及执行协调器。来信 job 保存实际 operation/run，按稳定业务键恢复观察；自动重试不会重跑已经失败或结果不明的模型轮次，显式重试增加代次。账号、额度、来信游标、发送 outbox 和业务定时仍由插件持有。

上节记录的三项旧入口测试已改为连接隔离控制后端，验证真实持久执行、受限工具、私信追加、失败清理及显式重试。会话控制与 B站流程定向回归 67 项通过；宿主改造需后端重启加载，本阶段未重启应用，也未调用真实平台写入接口。公共接入规范见 [接口迁移清单](../../docs/session-control-migration.md)。

## 0.7.0：封面与画面截图（2026-10-27）

按用户要求把「看视频时能拿到什么画面」补齐，工具从 20 个扩到 22 个：

| 工具 | 实现 |
|---|---|
| `bili_cover` | `info["pic"]` + `Referer`/`UA` 下载到 `<data>/shots/<bvid>/cover.jpg`；`size=small` 用 Pillow 缩到 672 宽；24 小时内按文件 mtime 复用 |
| `bili_frame` | `at` 支持 `"120,3:30"` 或留空取 `bili_highlights` 峰值；`source=storyboard` 走 `get_video_snapshot`（3 张 10×10 雪碧图、300 帧、480×270，Pillow 按最近时间点裁格）；`source=stream` 走 `get_download_url` 的 DASH 流 + ffmpeg `-ss` 抽帧；storyboard 失败自动降级并标 `degraded` |

同时修掉 `bili_video_info` 的既有缺陷：`tags` 读的是 `info["tag"]`，而 17.4.2 的 `get_info()` 不返回该键，导致标签**恒为空数组**；改为 `Video.get_tags()`。补 `cid`、`pages`（列表）、`cover`、`dimension`、`tid`，`page_count` 另给；`detail=true` 追加 `online` 与官方 `ai_summary`。

真机核对（只读，未做任何 B站 写入）：

- 封面：`BV12qnt6VEM1` → 1002×564、119,885 字节，`source_url` 与详情里的 `cover` 一致。
- storyboard：同一视频请求 `at="60,510"`，命中最近的时间点 58s / 508s，产出两张 480×270 JPEG（30,829 / 18,073 字节），打开确认是真实画面（8:28 的酒店窗景）。
- stream：`at="510"`、`width=1280` → 1280×720、65,913 字节，ffmpeg `rc=0`。
- 详情：`tags` 返回 8 个（了不起的旅行家/美国/生活记录/赛博朋克/旅游/vlog/边缘行者/自驾），`pages` 1 条带 `cid=42989062102`，`online.count=3`，`ai_summary` 110 字 + 3 段大纲。
- 该视频的 `tname` 与 `tname_v2` 在接口里都是空串（B站没填），不是解析问题；因此输出里同时给了 `tid`。

回归：`test_sugar_bili_scroll_discover.py` 新增 5 项（详情字段与 detail、封面只下一次再复用、storyboard 裁最近格、storyboard 失败降级 stream、峰值自动取点与 `3:30` 解析），该文件 13 项全过；MCP 用例的工具数断言改为 22；`manage.py` 的 `EXPECTED_TOOLS` 同步为 22。

热重载：这次用插件开关（停用→启用）而不是全局 `/api/extensions/reload`，只重建本插件的 MCP 连接。过程记录：停用后 `tool_count` 归 0，启用后下一次轮询即 22 且 connected。未重启后端。

## 0.7.1：按用户报错清单逐条核对后的修复（2026-10-27）

用户整理了一份「真的坏了 / 能力缺口 / 用错了 / 没测过」的清单。逐条复现与核对结果：

| 报错 | 结论 | 处理 |
|---|---|---|
| `bili_verify_comment` 两次 `visible:null` + `取视频信息失败` | **属实，是 bug** | 根因：用裸 `aiohttp` 打 `x/web-interface/view`，返回 412 HTML，`_jget` 解不出 JSON 就当成「视频已删」。改走库里的 `Video.get_info()` 取 aid；顶层按「最新+热门各 3 页」扫描，楼中楼走 `Api` 会话扫最多 60 条 |
| `bili_search` 传 `page` 被拒 | **属实，是结构不一致** | `search_videos` 原来把 `page` 写死成 1；补 `page` 1–50 并透传，返回里回显 |
| `bili_comments` 只能取热门 | **属实，是能力缺口** | 增加 `sort=hot/time`、`root`（楼中楼）、`page` |
| `bili_reply` 多次 `61001` | 属实，但属账号侧限制 | 新增 `_response_error` 映射：61001→需绑定手机号、-101→重新登录、-412→风控、12015→太频繁；`uncertain` 对已确定失败为 false |
| `bili_search` 早期「插件尚未激活」 | 已修复的历史问题 | `_home()` 现在自己从 `plugin_storage_layout` 推出数据目录，不再依赖 `start()`；本轮多次调用未复现 |
| 稍后再看/投币 `Unknown or unavailable deferred tool` | **不是工具坏了** | 工具名是 `bili_watch_later_add`，不是 `bili_watch_later`；本轮实调成功并把 BV12qnt6VEM1 加进稍后再看，`bili_my_list(kind=toview)` 能查到。投币/点赞仍受开关限制，四个开关默认关 |
| 收藏没加成 `BV1NKHP63E7h` | **不是只读导致** | `bili_favorite_folders` 本来就是只读；要加收藏得调 `bili_favorite_add(bvid, fid)`。未指定 fid 且没配置 `fav_folder_id` 时按既有契约直接拒绝、不发网络请求（有测试锁定），不会替用户猜收藏夹 |
| `tool_search` 被封 | 宿主执行范围限制 | 报错来自 `app/session_control/configuration.py:319` 的 `tool_scope_denied`，是插件自动会话的 allow 名单只放 B站工具；`tool_describe` 不受影响。属设计如此，不改插件 |
| `bili_discover` 报 `Bound arguments do not match` | 参数用错 | 真参数是 `source`，没有 `mode`；本轮用 `source=hot` 实调通过 |
| `bili_record_video` 标题回显成 BV 号 | 模型少传 `title` | 可选参数，不是丢字段；值班任务里带上标题即可 |

本轮实调覆盖（此前「没测过」的部分）：`bili_discover(hot)`、`bili_highlights`（5980 条弹幕，峰值 0:00/1:00/8:30）、`bili_danmaku`、`bili_emotes(panel)`、`bili_emote_save`（命中已有 [doge]，返回 duplicate）、`bili_favorite_folders`（默认收藏夹 4375066445）、`bili_watch_later_add` + `bili_my_list(toview)`、`bili_comments` 的 hot/time/root 三种模式、`bili_verify_comment` 顶层与楼中楼各一条（均 `visible:true`）。

回归：`test_sugar_bili_scroll_discover.py` 增至 18 项（新增分页透传、时间序与楼中楼、复核命中、61001 文案）；B站相关 7 个测试文件 **122 项通过**。插件用开关热重载，MCP 仍是 22 个工具，未重启后端。
