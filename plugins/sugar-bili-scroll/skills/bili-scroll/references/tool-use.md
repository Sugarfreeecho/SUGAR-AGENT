# Agent：工具使用

## 工具目录

服务端短名如下，实际调用从 MCP 目录选择 `mcp_sugar_bili_scroll_bili_` 前缀工具。工具 schema 为准，不能额外传入会话/权限字段。MCP 固定发布22个schema；实际可执行范围在每次调用时根据开关和运行身份重新校验，插件自动会话的模型目录还会按本轮范围收窄。

| 短名 | 参数与用途 |
|---|---|
| bili_search | `keyword`必填；`num`1–50，`order`为totalrank/click/pubdate/dm，`page`1–50；结果`seen`表示全局看过 |
| bili_video_info | `bvid`，`detail`默认false；标题、简介、UP、`cid`、分P列表、标签、封面地址、分辨率、播放和收藏；`detail=true`加在线人数与官方AI摘要 |
| bili_subtitle | `bvid`；字幕原文，先读字幕再判断内容 |
| bili_comments | `bvid`，`num`1–100，`sort=hot/time`，`root`给某条 rpid 就抓楼中楼，`page`顶层起始页；返回表情码和评论图地址 |
| bili_danmaku | `bvid`，`num`1–500；弹幕 |
| bili_favorite_folders | `uid`默认0，表示当前账号；只读列出收藏夹 |
| bili_verify_comment | `bvid/rpid`必填，`root`可选；可见性复核（最新+热门各扫 3 页，或扫楼中楼 60 条） |
| bili_transcribe | `bvid`；需开启转写、满足时长上限，先尝试字幕 |
| bili_emotes | `query`、`scope=all/local/panel`、`limit`1–60；本地图返回id，面板返回code |
| bili_emote_save | `code`或`url`二选一；`name/tags/bvid`可选；保存本地表情，自动会话每轮最多3个 |
| bili_record_video | `bvid/picked/reason`必填，`title/author`可选；仅值班运行，用于配额、日报与全局判重 |
| bili_favorite_add | `bvid`必填，`fid`默认0；0使用设置`fav_folder_id`，未设置则需要显式fid；必须是当前账号的收藏夹 |
| bili_reply | `bvid/text`必填；可选`rpid/root/emote/sticker`；评论150字内，sticker必须来自本地表情库且允许图片评论 |
| bili_send_message | `receiver_uid/text`；仅配置允许的值班或普通会话向配置收件人发送，500字以内 |
| bili_discover | `source`必填：hot/weekly/rank/up/feed/related；`limit`1–50、`tid`分区名、`mid`UP主UID、`bvid`相关推荐的源视频、`page` |
| bili_my_list | `kind`必填：toview/favorites/history；`favorites`要给`fid`；`limit`1–50 |
| bili_highlights | `bvid`，`window`10–120秒、`top`1–10；按弹幕密度找最热闹的时间段 |
| bili_capabilities | 无参数；返回账号、各开关和本轮可用工具，不确定权限时先问它 |
| bili_cover | `bvid`，`size=original/small`；封面存本地，返回路径/尺寸/字节，24小时内复用 |
| bili_frame | `bvid`，`at`为秒数（`"120,3:30"`）或留空/`highlights`取弹幕峰值；`source=storyboard/stream`；`width`320–1920、`top`1–5；一次最多5张 |
| bili_watch_later_add | `bvid`；受`allow_toview`控制，只添加不取消 |
| bili_interact | `action`必填：like/unlike/triple/coin/follow；`bvid`（前四种）、`uid`（follow）、`num`1–2（coin）；受对应开关和每轮投币额度控制 |

所有带 `bvid` 的工具都接受裸 BV 号、`av` 号、完整链接和 `b23.tv` 短链；解析在权限校验前完成，贴链接不会绕过值班的 `picked` 校验。

## 操作流程

- 查询或分析视频：搜索 → 详情 → 字幕 → 需要时评论/弹幕 → 没字幕且值得继续分析时转写。不能把视频标题、摘要或转写失败当作已看完内容。
- 发现视频：关键词搜不到或想换口味时用 `bili_discover`——热门/排行看大盘，`up` 追某个 UP，`feed` 看关注动态（关注 0 人时为空是正常的），`related` 顺着一好视频往下摸。长视频先用 `bili_highlights` 看哪几分钟热闹，再决定要不要读全文。
- 看自己的库：`bili_my_list(kind=toview)` 稍后再看、`favorites` 收藏夹内容、`history` 观看历史。历史条目可能只有 av 号，把 `url` 或 `av` 号交给其它工具也能用。
- 要看画面：`bili_cover` 拿封面；`bili_frame` 截图。默认 `storyboard` 走官方预览图（480×270、不下载视频、快），要看清字或人脸再传 `source=stream`（原画、吃带宽）。`at` 留空会自动取 `bili_highlights` 的峰值，适合“先找高能段再截图”的一条链。截图落在插件数据目录，结果里的 `degraded=true` 表示预览图不可用、已降级成视频流，要如实说明。
- 收藏视频：确认视频和用户意图 → `bili_favorite_folders(uid=0)` → 用户指定或设置的收藏夹 → `bili_favorite_add`。只支持添加，不创建收藏夹、不取消收藏。失败不能报成功；账号切换或白名单撤销会被重新校验。
- 互动：点赞/三连/投币/关注都要先确认开关打开（不确定就问 `bili_capabilities`）。投币是真实消耗硬币，按设置额度用；没有需要就别主动投。`triple` 会花 2 枚硬币并加收藏，代价比 `like` 大得多，别当成普通点赞。关注只做关注，不提供取关。
- 查评论：`bili_comments` 默认按热度；要“谁最新说了什么”传 `sort=time`，要“谁回了我那条”把那条的 `rpid` 传给 `root`。楼中楼接口必须走库里的 `Api` 会话，裸请求会吃 412。
- 发评论：有明确发送意图和目标后使用 `bili_reply`。自动值班必须先通过 `bili_record_video`记为挑中；入站公开回复严格回到原视频原楼层。白名单私聊可在设置允许时要求向指定视频发新评论。工具返回成功只表示B站接口接受；需确认公开可见时再调用复核工具。返回 `61001` 表示账号要先绑定手机号才能评论，换工具或重试都没用。
- 使用表情：先查询合法code或本地id；保存评论中的表情图使用返回的真实URL，不自行拼地址。不要收藏普通截图、封面或带人脸照片。图片评论每轮最多1张。

## 会话权限

| 会话 | 能力 |
|---|---|
| 普通Agent会话 | 登录后使用业务工具；公开评论、私信、转写仍受全局设置约束；视频记账只限值班 |
| 值班任务 | 搜索分析、表情、记账；评论/私信按任务开关、目标和额度控制；自动收藏由宿主执行，不把显式收藏工具交给值班模型 |
| 白名单私聊 | 全部已启用的B站业务能力，包括转写/收藏视频/表情/设置允许的公开评论；普通私聊回复由宿主发送，不提供转发到其他私信对象的工具 |
| 白名单公开回复 | 业务读取/转写/表情/收藏、原楼层公开回复；本轮最多一条公开回复 |
| 非白名单入站 | 零工具；仅生成普通回复，宿主投递 |

互动类工具（`bili_interact`、`bili_watch_later_add`）在上述会话里只在对应开关打开时出现；值班任务还要先 `bili_record_video` 记录挑中的视频。开关没开时调用会被拒，解释为设置未开启，不要换工具或伪造身份绕过。

以上均不开放本机命令、文件工具。公开评论会话按“接收账号+视频+根评论楼层”复用；私聊按“接收账号+对方UID”复用。新私聊会接入同一在途会话；评论入站串行处理。

本地表情保存和视频记账声明为本地数据写入；在宿主管理的Git工作树中会受到工作树隔离检查。若宿主拒绝，不得伪造路径或修改工具契约绕过；这些数据属于插件共享数据目录。

## 结果与失败

- MCP `isError=true`就是失败，不能根据返回文字臆断成功。工具结果中的`ok/success/error`按实际值解释。
- 评论复核只有`visible=true`能确认可见；false/null只表示没查到，不能断言没发出去，也不能据此重发。
- 私聊由完整回复条目投递；每条最多500字，任一条超限时整轮普通私聊不发并记错。不得拆分、截断或重新生成来绕过本轮限制；已经成功执行的评论/收藏是独立结果。
- 没字幕或转写为空应按返回原因解释；不要无限重试。网络和风控错误不等于内容为空。
- 发送结果为unknown时先核对实际发送状态及回执，人工确认后才能重试或标记；不能自动重发造成重复。
