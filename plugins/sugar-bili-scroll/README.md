# 刷 B站 · sugar-bili-scroll

SugarAgent 的 `trusted_host` 原生插件，承接 dsh-bili-scroll 的刷视频能力，新增表情库、入站互动、多任务管理、发现与互动工具。当前源码版本 **0.7.1**。

本次实现和验证结果见 [实施与验收记录](IMPLEMENTATION.md)；接手时发现的问题保留在 [历史审查](DEVELOPMENT.md)。源码验证与线上运行分别记录，不用原会话的完成标记代替验收。

原项目已有 UC、迁移状态、新增 UC 及未完整迁移项见 [DSH → Sugar UC 对照清单](UC_COMPARISON.md)。

## MCP 与随包 Skill（0.7.1）

23 个 B站业务工具通过 `.mcp.json` 的 `sugar-bili-scroll/bili` 服务注册，使用宿主同进程 Streamable HTTP，入口 `/api/sugar-bili-scroll/mcp/`。原生 `tool_definitions()` 不再注册 B站工具，避免重复。控制台、值班调度、入站回复、多账号和宿主转写继续由 trusted_host 提供。

服务端工具短名仍为 `bili_*`，SugarAgent 模型目录中的名称为 `mcp_sugar_bili_scroll_bili_bili_*`。自动会话的工具范围及系统提示词同步转换，SQLite运行权限仍保存短名；每次调用通过宿主一次性元数据票据验证会话身份、参数和运行权限，模型不能自行指定身份。MCP目录固定发布22个schema，调用时校验开关和最新权限。其他MCP客户端不具备SugarAgent身份票据，当前版本用于宿主内部连接。

随包 [bili-scroll Skill](skills/bili-scroll/SKILL.md) 由宿主发现为 `sugar-bili-scroll:bili-scroll`，覆盖 Agent注册/自检/卸载、工具使用、用户配置和功能介绍。附管理助手：

```powershell
.\python\python.exe plugins/sugar-bili-scroll/skills/bili-scroll/scripts/manage.py doctor
```

`doctor/status`只读；`register/disable/uninstall`改变对应运行态。bundled源码通常不在宿主可写卸载目录，需按Skill说明先停用，再按用户意图保留或移走源码；默认保留所有运行数据。改插件目录里的文件后，用设置页的「重新发现 / 热重载」或插件开关（停用→启用）即可生效，不必重启后端；只有改宿主自己的 `app/*.py` 或 `.env` 才需要重启。判定口径见 [插件热重载](../../docs/plugin_hot_reload.md)。投币、三连、关注默认关闭，未对真实B站账号做写入验证。

## 使用

1. 在插件页“添加账号（扫码）”；可以保存多个账号，在列表中选择一个运行。退出保留登录态，移除才删除保存的凭证，详见 [多账号说明](MULTI_ACCOUNT.md)。
2. 在“值班任务”中新建或编辑任务，配置关键词、每天额度、谷时窗口及间隔。
3. 根据需要开启任务的自动评论、私信投递、图片评论；公开评论还需填写要 @ 的名称。设置收藏夹后，由宿主收藏挑中的视频。
4. 点该任务的“立即跑”可手动执行；自动调度每 60 秒检查一次，只执行第一条满足条件的任务，值班任务依次运行。
5. 需要接收私聊、评论或 @ 时，开启“入站自动回复”，选择渠道并填写白名单。“回复评论和 @”独立于值班任务，覆盖从未刷过的视频。

任务可增删改、启停、立即运行、查看各自日报。页面显示每任务今日挑中数、剩余额度、轮数、运行状态和错误。删光任务后保持为空，不会重新创建默认任务。

## 三类会话

三类会话均使用独立完整系统提示词，替换普通会话的基础提示词。页面“插件会话系统提示词”可分别编辑值班、私聊、评论模板，下一轮生效且保留聊天记录；留空或恢复默认使用插件默认模板。详见 [独立系统提示词](SYSTEM_PROMPTS.md)。

| 类型 | 会话复用 | 模型能使用的工具 | 投递方式 |
| --- | --- | --- | --- |
| 值班任务 | 每任务一条 | 当前任务允许的 B站业务工具及视频记账工具 | 模型按开关评论或向配置 UID 私信 |
| 入站私聊 | 每 UID 一条 | 白名单：全部已启用的 B站业务能力；陌生人：无工具 | 宿主发送完整普通回复条目 |
| 评论 / @ / 回复评论 | 同一视频、同一根评论楼层一条 | 白名单：已启用的 B站业务能力；陌生人：无工具 | 白名单用评论工具；陌生人由宿主投递普通回复到原楼层 |

所有插件自动会话均不开放本机命令、文件工具。白名单私聊可以要求在指定视频发布公开评论，由单独开关控制；私聊模型始终没有向其他 UID 发私信的工具。转写只有开启后才可用，图片评论由对应开关控制。

同一 UID 在生成中继续发消息，使用 append/steer 插入当前会话；未消费的消息重新排队。公开回复串行执行，私聊按 UID 隔离，总计最多四个入站工作任务。值班任务和入站工作任务使用独立会话及运行权限。

## 私聊长度与发送记录

每条普通回复最多 **500 字符**。整轮生成结束后先校验全部条目，任一超长则本轮私聊不发送并记录失败；不拆分、不截断、不自动重新生成。思考、工具结果、未完成片段不转发，重复的最终正文只发送一次。

通过校验的整轮正文先一起保存，再按顺序投递。限流时保留原文等待续发。入站默认同人冷却 1 分钟、全站每小时 6 条，0 表示不限；模型启动和实际发送分别受限。模型主动调用的公开评论工具可能先于普通私聊校验执行，其真实回执单独保留。

游标和入站事件在同一 SQLite 事务内保存。初次成功拉取每个渠道只建游标，不回复旧消息。明确失败可重试；超时等无法判断是否发送的结果标为“待核对”，不会自动重发。详情见 [入站说明](INBOUND.md)。接口成功与评论公开可见是两个状态，公开可见需用 `bili_verify_comment` 单独确认。

0.3.1 修复失效凭证被当作已登录、旧凭证阻止重新扫码的问题。B站返回 `-101` 后页面标记凭证失效，保留轮询错误；凭证失效期间不启动回复模型。扫码保存新凭证后自动尽快重新检查，新凭证不继承旧凭证的失败标记。

## 任务事实与迁移

模型用 `bili_record_video` 记录每条看过的视频，包含挑中 / 跳过及原因。宿主校验全局判重和当天额度，然后生成任务日报与归档。关闭日报仍消耗额度、保留判重和归档。空结果或模型失败的运行也会留下简短运行记录（日报关闭除外）。

每任务独立拥有额度、窗口、间隔、预算、会话、轮数、日报及归档；全局只共享判重表和表情库。MCP 发布固定 schema，自动会话按本轮权限收窄工具范围，真正调用时再读取最新状态。运行中关闭任务、撤销白名单或关闭写入能力后，后续调用会被拒绝。

旧单任务数据只迁移给能匹配原会话的任务，或唯一的“默认任务”；不会复制给每个任务。旧数据保留，迁移账本标记已导入内容。无法可靠匹配时保留原数据，避免猜测归属。

插件数据在 `<workspace>/.config/plugins/sugar-bili-scroll/data/`：

| 路径 | 内容 |
| --- | --- |
| `bili_credential.json` | 当前启用账号凭证 |
| `tasks.json`、`tasks/<id>/` | 任务配置、状态、`out/` 日报和 `digest/` 归档 |
| `runtime.sqlite3` | 已保存账号凭证、记账、消息队列、会话绑定、运行权限、发送意图及回执 |
| `system-prompts.json` | 自定义的三类完整系统提示词；未配置时使用插件默认 |
| `seen.md` | 全局判重表 |
| `emotes/` | 表情图片与标签索引 |
| `duty.md` | 值班章程；用户修改过的版本保留，新版另存 `.new` |
| `duty.log` | 运行日志；1 MiB 轮转，保留 3 份历史 |

不要通过删数据库来处理“待核对”发送记录，否则会丢失防重复发送事实。

## 表情与转写

`bili_comments` 返回评论表情码和图片地址；白名单或值班会话可用 `bili_emote_save` 收藏、打标签，再用 `bili_emotes` 搜索。面板结果提供合法表情码，本地结果提供可传给 `bili_reply(sticker=...)` 的 ID。

单张收藏上限 6 MiB，评论上传上限 2 MiB；每轮最多收 3 个表情、发 1 张图片。限额保存到运行记录，冷工具实例也共用计数。

转写默认 `asr_engine=host`：下载音频、ffmpeg 转成 16 kHz 单声道 PCM WAV 并切片，调用宿主语音输入服务。`asr_engine=local` 使用 faster-whisper。时长上限 0 表示不限制；跨会话串行转写，避免重复占用资源。空文本是有效结果，不应反复重试。

现有能力层依赖 `bilibili-api-python==17.4.2`、`qrcode` 及其相关依赖；选择 local 引擎还需 `faster-whisper`、`av`。宿主引擎需可用的语音输入服务和 ffmpeg。

## 收藏视频工具

`bili_favorite_add(bvid, fid=0)` 将一条视频收藏到当前启用账号的收藏夹。先用 `bili_favorite_folders` 查询收藏夹 ID；`fid` 省略或为 0 时使用设置中的 `fav_folder_id`，未配置则要求明确指定，不自动猜收藏夹。

`bili_favorite_remove(bvid, fid)` 把一条视频从指定收藏夹移出（等于在该收藏夹里取消收藏）。必须显式给 `fid`，且必须是当前账号的收藏夹；不删除收藏夹本身，也不影响视频在其它收藏夹里的记录。2026-11-04 实测：`del_media_ids` 生效，但回执里的 `success_num` 恒为 0，判断成败只能看有没有异常，并可用 `bili_my_list(kind=favorites)` 复核。同一次 `/x/v3/fav/resource/deal` 请求里 `add_media_ids` 新夹 + `del_media_ids` 旧夹也成立，等价于「移动到另一个收藏夹」。

普通 Agent 会话可调用收藏与移出；白名单入站会话只有收藏（`bili_favorite_add`），不开放移出。执行前校验 BV 号、收藏夹归属、当前账号及最新权限；失败返回失败，成功返回 BV／收藏夹／视频 aid 等结果。不会创建收藏夹。切换账号后需要选择该账号自己的收藏夹。

白名单私聊可说“把 BV…… 收藏到收藏夹 123”。值班任务继续由宿主自动收藏挑中的视频，值班模型不额外持有显式收藏工具。收藏动作与普通私信回复分别执行，普通回复超长而未投递时不会撤销已成功收藏。

## 发现、个人列表与互动（0.6.0）

0.6.0 补上了「除了关键词以外怎么找视频」和「自己账号里有什么」两块缺口，共 20 个工具。

| 工具 | 用途 |
|---|---|
| `bili_discover` | 统一发现入口：`hot` 热门 / `weekly` 每周必看 / `rank` 分区排行（`tid` 选分区）/ `up` 某个 UP 的投稿（`mid`）/ `feed` 关注动态 / `related` 相关推荐（`bvid`） |
| `bili_my_list` | 自己账号的库：`toview` 稍后再看 / `favorites` 收藏夹内容（`fid`）/ `history` 观看历史（带进度、是否看完） |
| `bili_highlights` | 按弹幕密度找「哪几分钟最热闹」，用来看长视频值不值得看。只采样前几段，超长视频尾部不在统计内 |
| `bili_capabilities` | 一次问清当前账号和本轮能用哪些能力，不用靠调用失败去试 |
| `bili_watch_later_add` | 加入稍后再看（默认允许，可在设置里关） |
| `bili_interact` | `like`/`unlike` 点赞、`triple` 一键三连、`coin` 投币、`follow` 关注（只关注，不取关） |

**视频标识统一解析**：所有带 `bvid` 参数的工具都接受裸 BV 号、`av170001`、带 `?p=2` 的完整链接和 `b23.tv` 短链。解析在权限校验之前完成，所以「贴个链接」和「贴 BV 号」走同一条权限路径，不存在用链接绕过值班 `picked` 校验的洞。

**互动开关**（`plugin.json`）：`allow_toview` 默认开；`allow_like`、`allow_triple`、`allow_coin`、`allow_follow` 默认关；`coin_per_round` 限制每轮投币次数（0 = 不允许），一次投 1~2 枚。开关关着时工具连会话范围都不给。值班任务调用互动工具前必须先 `bili_record_video` 记录本轮挑中的视频，和评论是同一条规则。

**额度**：投币次数记在 `runtime.sqlite3` 的 `runs.coins`，旧库首次打开自动补列，不影响已有任务与历史记录。

**热重载**：`app/plugins/host.py` 用「入口路径 + `content_signature`」给 trusted_host 模块起名，内容一变就是新模块；`_load_sibling()` 的模块名同样带文件内容摘要，兄弟模块不会留在旧代码上。`install()` 在重新注册前会按路径摘掉上一轮挂的 `/api/sugar-bili-scroll/*` `APIRoute`——`include_router` 会复制 route 对象，且 FastAPI 先注册先匹配，不摘旧处理器就会一直赢；MCP 网关是 `app.mount` 的 `Mount`，只清 `APIRoute` 才不会误删它。MCP 服务、值班与入站调度由 `start()`/`stop()` 对账重建。所以插件文件改完点「重新发现 / 热重载」即可，工具目录、面板和 MCP schema 都会换成新代码。

## 封面与画面截图（0.7.0）

| 工具 | 做什么 |
|---|---|
| `bili_cover` | 下封面到 `<data>/shots/<bvid>/cover.jpg`，返回路径/尺寸/字节；`size=small` 缩到 672 宽。24 小时内复用 |
| `bili_frame` | 按时间点截图：`at` 写秒数（`"120,3:30"`），留空或写 `highlights` 自动取弹幕峰值，正好接 `bili_highlights` |

`bili_frame` 两种来源：

| source | 原理 | 分辨率 | 代价 |
|---|---|---|---|
| `storyboard`（默认） | B站官方预览图：3 张 10×10 雪碧图、全片 300 帧，Pillow 按时间点裁格子 | 480×270 | 一次请求拿全片，不下载视频 |
| `stream` | `get_download_url` 取 DASH 视频流，ffmpeg `-ss t -frames:v 1` | 按 `width`，默认 1280×720 | 吃带宽，地址几分钟过期 |

storyboard 拿不到时自动降级成 stream，结果里标 `degraded: true` 并把原因写进 `notes`，不假装成功。一次最多 5 个时间点，同一时间点 24 小时内复用；缺 Pillow 或 ffmpeg 只影响对应来源，错误里说明缺什么。截图落在插件数据目录 `shots/<bvid>/`，文件名 `s<秒>.jpg` / `f<秒>.jpg` 区分两种来源。

`bili_video_info` 同时补齐并修掉三处：

- `tags` 以前读 `info["tag"]`，17.4.2 不返回这个键，所以**一直是空数组**；现在走 `Video.get_tags()`，实测拿到 8 个标签。
- 新增 `cid`、`pages`（每 P 的 page/cid/title/duration）、`cover`、`dimension`、`tid`；`pages` 由「数量」改成列表，数量另给 `page_count`。
- `detail=true` 时再取 `online`（实时在看）和 `ai_summary`（官方摘要 + 大纲），默认不取，避免每条视频多打两个接口。

## 开发与验证

逐项真机操作、测试输入与通过标准见 [UC 验收步骤](UC_TESTING.md)。

主要模块：`mcp_server.py` 提供 MCP 工具，`host.py` 提供 HTTP、管理生命周期；`workflow.py` 负责业务；`store.py` 保存事务事实；`tasks.py` 管理任务及迁移；`inbound.py` 拉消息；`bili_client.py` 适配 B站；`emotes.py` 管理表情；`asr.py` 转写。

```powershell
.\python\python.exe plugins\sugar-bili-scroll\tests\evidence_check.py
.\python\python.exe -m pytest tests\test_sugar_bili_scroll_browser.py -q
```

这些检查用临时数据、模型和发送替身；浏览器测试也拦截所有请求，不向真实用户投递。真实评论或私信验收结果、分阶段部署及完整检查命令见实施记录。

0.3.2：状态页显示当前登录 UID，并提供“退出 B站登录”“切换 B站账号”和“取消扫码”。退出仅清除本插件的本地凭证；切换账号先退出旧账号，再生成二维码。取消扫码后，仍在返回的扫码请求不能写入凭证。B站任务运行期间禁止退出/切换；换号后重新初始化消息游标、隔离回复会话、停止旧账号待回复任务并保留历史回执。白名单和任务设置保留，自动回复总开关保持原值。

0.4.0：保存多个账号登录态，每次启用一个。账号列表可免扫码切换、退出保留、显式移除；切换前验证，失败时保留当前账号；原单账号凭证自动导入。0.3.2 的退出清除行为由本版的“退出保留／移除删除”替代。

0.4.1：新增 `bili_favorite_add` 收藏视频工具，支持指定收藏夹或使用配置值；接入普通会话、白名单权限及当前账号收藏夹校验。

0.6.0：新增 `bili_discover`、`bili_my_list`、`bili_highlights`、`bili_capabilities`、`bili_watch_later_add`、`bili_interact`；`bvid` 参数统一支持 av 号、完整链接和短链；新增五个互动开关与每轮投币额度。

0.7.0：新增 `bili_cover`、`bili_frame`（storyboard 预览图 / ffmpeg 原画抽帧）；`bili_video_info` 修复 `tags` 恒空，补 `cid`、分P 列表、`cover`、`dimension`、`tid`，`detail=true` 取在线人数与官方 AI 摘要。

0.7.1：修 `bili_verify_comment` 恒报「取视频信息失败」——原来用裸 `aiohttp` 打 `x/web-interface/view`，回的 412 HTML 被当成视频不存在；改走库里的 `get_info`，并按「最新+热门各 3 页」或「楼中楼 60 条」实际扫描。`bili_comments` 增加 `sort=hot/time` 与 `root` 楼中楼；`bili_search` 补 `page` 分页（和 `bili_discover` 对齐）。`bili_reply`/`bili_send_message` 的 `ResponseCodeException` 改成可读文案（如 `61001` → 需绑定手机号）。
