# 2026-10-25 审查修复与在途改动归档

按 `docs/release-workflow.md` 执行：设计稿先行、相关测试、按主题拆分暂存，前端源码与重建 dist 同提交。

## 审查修复

- Python 3.10 插件上下文总预算超时正确降级；目录回退读取移出事件循环。
- 桌面导航校验 URL origin；补齐特权 IPC 来源校验，收紧非媒体权限。
- 工作区切换缺少原目录时明确拒绝，保留审批的比较并交换语义。
- 用量聚合按请求流式读取 JSON；详情展开态恢复、动态标签统一转义。
- 设置标题使用纯文本；会话 ID 属性转义；图片 metadata 缓存有界。
- 收尾时新增的并行在途改动另行提交：普通发送与 steer 的乐观气泡立即携带耐久附件引用，不再等待历史回放显示图片；15 项附件/追问/会话流 Node 回归通过并重建 dist。
- 删除会话后释放其独占保活页面；guest 关闭等待与工作区分区数量有界。
- 加锁维护诊断丢弃计数，记录可重建索引降级原因。

## 在途改动分组

插件上下文、会话工作区与草稿、工具检索与历史索引、运行时提交与恢复、加载诊断与缓存、桌面浏览器与页面托管、用量统计、订阅接入插件、直播插件、线程监测插件，以及配套设计与诊断文档。共享文件按实际 hunk 归属提交。

## 验证与交付

- 89 个相关 Python 测试文件（含订阅插件）：1415 passed、3 skipped。
- 详情栏、设置、上下文、用户展示、人工交互与直播插件的真实浏览器回归：138 passed。
- 桌面外壳与 browser guest 策略：45 个 Node 测试通过。
- 乐观附件预览及相关追问、会话流：15 个 Node 测试通过。
- 语音浏览器冒烟通过：设置导航、浮动录音、草稿冲突、PCM 流式朗读、停止及回收。夹具同步到新的插件目录接口和流式音频接口。
- `compileall app plugins`、61 个变动 JavaScript 文件语法检查通过；插件 manifest JSON 可解析。
- 桌面前端提交通过正常 pre-commit 钩子：当天版本戳、临时目录全新 Vite 构建、源码与 dist 一致性检查均通过，未绕过钩子。
- 隐藏 Electron 窗口复测：userinfo 伪装 URL 的弹窗与主窗口跳转均被拒绝，原应用 origin 保持不变。
- 用量流式解析样本：12000 条请求、12.47 MiB 输入；`tracemalloc` 记录的 Python 分配峰值约 0.25 MiB，不代表进程 RSS。
- 常见私钥/API 凭据格式扫描初检 381 个路径、零命中；扫描规则及原始工作区备份保存在本地 `.git/codex-review-20261025/`，不入版本库。
- 扩展回归同时修正旧的 SSE 函数出现次数断言，以及图片夹具在模块首次导入时泄漏工厂绑定的问题。

此次请求范围为修复与本地分组提交；未推送或生成安装包，未变更发布版本号。

## 审查边界

- 浏览器继续允许本地开发服务器；全面阻断内网不是当前产品策略。
- 同源插件继续采用可信网页模型，sender 校验不构成第三方插件沙箱。
- 普通会话切换保活属于既定功能；删除成功才回收独占页面。工作区分区上限为 64，保留已分配工作区的登录状态；guest 关闭等待上限 5 秒，图片 metadata LRU 上限 2048 条。
- 工作区批准缺少 `previous_root` 时明确拒绝，不以空值跳过目录比较。
- 未将测试临时路径过深直接等同为产品缺陷，没有批量添加 `\\?\` 路径前缀。

## 分组提交清单

11 个共享文件按 hunk 分配；每组执行暂存差异检查与 Python 语法检查。全部提交保留在现有 `master` 分支。

| Commit | Topic |
|---|---|
| `6301cdc` | feat(runtime): coordinate durable execution and confirmed restarts |
| `dd7f652` | feat(sessions): support approved workspaces and reserved drafts |
| `765103d` | perf(tools): isolate grep and index streaming history search |
| `cfe179e` | feat(plugins): inject bounded context snapshots and scoped tools |
| `6474b99` | feat(interactions): admit question images and present user content |
| `164720b` | perf(subagents): coordinate results and resume parent sessions |
| `d238f77` | perf(ui): cache catalogs and bound session loading work |
| `9989a11` | feat(models): probe connectivity and preserve configured credentials |
| `07d7dc5` | feat(usage): stream usage aggregation and retain detail expansion |
| `1ad81d4` | fix(desktop): validate navigation and bound retained page resources |
| `2ed6a81` | feat(subscription): add protected OAuth subscription integration |
| `eba0911` | feat(bili): add multi-account live stream workflows |
| `a512cd2` | feat(monitor): sample thread activity through a managed plugin |
| `f8ffc4a` | test(voice): cover microphone and read-aloud browser integration |
| `8c36076` | fix(frontend): render optimistic attachment previews immediately |
| This commit | docs(review): record verified fixes and the grouped delivery |

## 技能目录重命名与手册扩写（2026-10-25）

- 原 use-myagent-features 重命名为 sugar-agent-manual，正文与描述统一改用 SugarAgent 品牌；packaging/skills.allowlist.txt 同步。
- 手册从 4 篇扩到 8 篇参考 + 路由式 SKILL.md：产品概览、前端功能地图、内置工具、插件与技能、设置中心（10 个分区 + 环境变量分组）、Goal/Hooks/MCP、报障排障、Agent 自我认知。
- 事实来源：README.md、pp/.env.example、plugins/*/plugin.json、pp/templates/static/settings/sections_*.js、docs/tool-disclosure.md、docs/tool_result_status.md。
- 校验：frontmatter 可解析（name/description），8 个参考链接全部存在；gent_tools.discover_skills() 返回新名称，旧名称不再出现。
