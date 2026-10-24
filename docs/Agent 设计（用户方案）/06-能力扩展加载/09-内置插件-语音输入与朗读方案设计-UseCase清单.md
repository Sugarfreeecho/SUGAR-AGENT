# 语音输入与朗读 · 功能方案设计（UseCase 清单）

- 版本：2026-10-24 v1（覆盖至：当前工作区；流式朗读、按句预取、PCM 缓存、本地 SenseVoice、桌面麦克风授权）
- 用途：**逐条审查功能与现象是否符合需求**。每条用例给出「触发 → 预期现象 → 规则与边界 → 依据」。审查时按编号逐条勾选；如有不符，反馈编号即可。
- 适用插件：`plugins/voice-input`（speech_input/{api,service,providers,configuration,protocol,worker}.py、web/{chat,settings,shared,capture}.js）
- 所属：能力扩展加载模块 → 插件子系统 → 内置插件实例（本文件夹 09；配套通则见 01–07）

---

## 0. 阅读指南

| 字段 | 含义 |
|---|---|
| **触发** | 谁做了什么操作（用户 / 模型 / 系统） |
| **预期现象** | 界面上应该看到什么（这是审查验收的核心） |
| **规则与边界** | 为什么是这个现象；什么情况下会不同 |
| **依据** | 代码位置或测试名（可复核） |

---

## 1. 功能定位与范围

**一句话**：把「说话变文字」和「文字变声音」做成一个随宿主发布的内置插件，两个方向都可以走云端 API 或本地模型。

**目标**：
1. 语音输入只在用户按下话筒时录音，识别结果插入草稿而不是直接发送；
2. Final 卡片朗读只在点击时合成，长回答的第一句要尽快出声，不要等整篇合成完；
3. 配置与密钥只落在后端，界面不回显密钥；不启用时不加载任何本地模型。

**明确的非目标 / 已知边界**（详见 §9）：
- 不做自动朗读、不做唤醒词，不把生成的音频写入会话或附件；
- 不做本地 TTS 模型（`local` 目前只用于 ASR）；
- 不接管用户自带的成品音频文件。

**能力总览**：

| 能力 | 状态 |
|---|---|
| 云端 ASR（通用 `/audio/transcriptions`、MiMo chat audio） | ✅ |
| 本地 ASR（SenseVoice INT8 + Silero VAD，CPU） | ✅ |
| 云端 TTS（通用 `/audio/speech`、MiMo chat audio） | ✅ |
| MiMo 流式朗读（PCM16 分片边收边播） | ✅ |
| 按句切段 + 下一段预取 | ✅ |
| 合成结果 PCM 缓存（哈希键 + LRU） | ✅ |
| 桌面端麦克风授权（仅回环主框架） | ✅ |
| 本地 TTS | ⚪ 未实现 |

---

## 2. 核心概念与数据模型

| 概念 | 含义 |
|---|---|
| **ASR / TTS** | 语音转文字 / 文字转语音；本插件两者独立配置，可指向不同服务商与密钥 |
| **provider** | `openai-compatible`、`mimo`；ASR 另有 `local`。白名单之外的取值在保存时被拒绝 |
| **段（segment）** | 朗读的最小请求单位；当前按句切，窗口 110 字 |
| **首块（first audio）** | 从点击到第一个 PCM 分片被排期的时间；衡量流式收益的核心指标 |
| **PCM16** | 16 位小端、单声道；MiMo 输出 24 kHz，直接进 Web Audio 而不落地容器格式 |
| **缓存键** | `sha256(provider, base_url, model, voice, speed, instructions, text)` |
| **请求身份** | `(owner, identity)`；`owner` 来自请求主体，`identity` 来自 `requestId` |
| **作用域** | `read`（状态）/ `write`（识别、朗读、取消自己的请求）/ `admin`（改配置、准备模型） |

---

## 3. 插件安装与生命周期（UC-1xx）

| 编号 | 触发 | 预期现象 | 规则与边界 | 依据 |
|---|---|---|---|---|
| UC-101 | 宿主启动并加载内置插件 | 设置导航出现「语音输入与朗读」，输入框旁出现话筒 | 清单声明 `ui.chat.extension` 与 `ui.settings.section`；`host.install` 只在 `app.state.voice_input_service` 为空时注册路由，重复加载不会挂两份 | `.myagent-plugin/plugin.json`、`host.py:install` |
| UC-102 | 插件被禁用 | 话筒与朗读按钮消失；再次调用语音接口返回 404 | `api.actor(..., require_enabled)` 用 `enabled_resolver` 判活；`host.stop` 调 `service.close()` 释放 worker 和任务 | `api.py:actor`、`host.py:stop` |
| UC-103 | 禁用后重新启用 | 无需重启即可再次使用 | `host.start` 把 `_closed` 复位；路由对象复用，不重复注册 | `host.py:start` |
| UC-104 | 宿主关闭 | 本地识别 worker 被杀掉，在途任务取消 | `close()` 先取消 `_preparation` 和全部 `_jobs`，再 `_stop_worker()` | `service.py:close` |

---

## 4. 语音识别（UC-2xx）

| 编号 | 触发 | 预期现象 | 规则与边界 | 依据 |
|---|---|---|---|---|
| UC-201 | 点话筒 → 开始录音 | 浮窗显示音量条与秒数；输入框不变 | 录音在浏览器侧；超过 `maxDurationSeconds`（120 s）自动停止并转写 | `web/chat.js:record`、`protocol.py:MAX_DURATION_SECONDS` |
| UC-202 | 停止录音 | 显示「正在识别…」，成功后在草稿光标处插入文字 | 只插入，不自动发送；草稿在录音期间被改动时不插入，转为「确认后插入」 | `web/chat.js:finish`、`shared.js:splitSpeechText` 同文件的 composer 契约 |
| UC-203 | 上传的 WAV 不是 16 kHz 单声道 PCM16 | 返回 400 `invalid-audio` | `validate_wave` 逐字段校验 RIFF/`WAVEfmt `/`data` 偏移、采样率 16000、单声道、16 位、≤4 MiB、≤120 s | `protocol.py:validate_wave` |
| UC-204 | ASR provider = `local` 且模型未准备 | 返回 409 `unprepared`，提示先去准备模型 | 本地模式要求 `_verified`；不会静默降级到云端 | `service.py:transcribe` |
| UC-205 | 本地模型文件被替换或截断 | 视为未准备，要求重新准备 | 按「字节数 + SHA-256」双重校验，任一不符即 `_matches` 返回 False | `service.py:ASSETS`、`service.py:_matches` |
| UC-206 | 点「准备模型」 | 依次显示检查、下载、校验、加载进度，可取消 | 下载写入 `.part` 再原子改名；校验失败删除临时文件；源可在 huggingface 与镜像间回退 | `service.py:_download`、`service.py:_prepare` |
| UC-207 | 本地识别正在跑时又发起一次 | 第二次返回 429 `busy` | `_operation` 锁串行化本地推理；同一 `(owner, identity)` 重复请求返回 409 `duplicate-request` | `service.py:transcribe` |
| UC-208 | 识别中途点取消 / 切换会话 | 请求被取消，worker 释放 | `cancel(owner, identity)` 取消对应任务；`CancelLedError` 分支先 `_stop_worker()` 再抛出 | `service.py:cancel` |
| UC-209 | 云端识别失败 | 返回 502，错误信息不含密钥或服务商原始响应体 | `providers.request` 只回 HTTP 状态码；`_api_job` 把 `TimeoutError` 转 504、`VoiceAPIError` 转 502 | `providers.py:request`、`service.py:_api_job` |

---

## 5. 朗读与流式播放（UC-3xx）

| 编号 | 触发 | 预期现象 | 规则与边界 | 依据 |
|---|---|---|---|---|
| UC-301 | 点 Final 卡片「朗读」 | 首段音频到达即出声，不等整篇合成完 | 走 `/synthesize/stream`，PCM 分片按音频时钟连续排期；实测 523 字回答 1.23 s 出声 | `web/chat.js:stream`、`api.py:synthesize_stream` |
| UC-302 | 一段播完前 | 下一段的请求已经在途，段间无静音空档 | 消费当前段之前就发出下一段请求；实测 gaps 为空 | `web/chat.js:stream`（`ahead` 预取） |
| UC-303 | 回答很长 | 内存不随篇幅线性增长 | 已排期音频超过 24 s 就暂停拉取，等播放追上来再继续 | `web/chat.js:stream`（背压循环） |
| UC-304 | 点「停止朗读」 | 立即静音，按钮回到「朗读」 | 中止全部在途请求、`stop()` 所有音源、`close()` AudioContext | `web/chat.js:stopPlayback` |
| UC-305 | 切换会话 / 播放另一张卡片 / 禁用插件 | 当前朗读停止且不残留音源 | `myagent:session-change`、`scan` 里 `button.isConnected` 检查都会触发 `stopPlayback` | `web/chat.js` 监听与 `scan` |
| UC-306 | TTS provider 是 `openai-compatible` | 自动退回整段合成，功能不报错 | `/synthesize/stream` 对这种 provider 返回 409 `streaming-unsupported`，前端捕获后改用 `/synthesize`，并把窗口放宽到 600 字 | `service.py:stream_parameters`、`web/chat.js:buffered` |
| UC-307 | 朗读文本超过 4000 字 | 返回 400 `invalid-text` | 该上限按单次请求算，分段后每段远小于上限 | `service.py:stream_parameters` |
| UC-308 | 朗读文本为空或全空白 | 返回 400 `invalid-text` | 空文本不发起上游请求 | 同上 |
| UC-309 | 服务端偷偷改了音频格式 | 播放速度不会漂移 | 采样率取自响应头 `X-Sample-Rate`，缺失才回落到 24000 | `web/chat.js:consume` |
| UC-310 | 一个 PCM 分片恰好切断 16 位样本 | 不出现爆音或音调偏移 | 奇数尾字节留到下一个分片拼接；`Int16Array` 只在偶数偏移上构造，必要时先复制对齐 | `web/chat.js:consume` |
| UC-311 | 上游 SSE 里出现 role 帧、`audio: null` 帧、只有 `usage` 的收尾帧 | 都不被当成错误 | 三类帧跳过；`choices[0]` 不无条件索引（收尾帧的 `choices` 是空数组） | `providers.py:synthesize_stream` |
| UC-312 | 上游流超过 32 MiB | 中断并返回 502 | `STREAM_LIMIT` 兜底，避免异常流打满内存 | `providers.py:STREAM_LIMIT` |
| UC-313 | 上层在生成过程中断开 | 上游连接随之关闭，不留后台推理 | 响应迭代器检测 `request.is_disconnected()` 后返回，生成器 `finally` 关闭文件与连接 | `api.py:audio`、`service.py:stream_speech` |

---

## 6. 缓存（UC-4xx）

| 编号 | 触发 | 预期现象 | 规则与边界 | 依据 |
|---|---|---|---|---|
| UC-401 | 第二次朗读同一段文字 | 几乎立刻出声 | 实测命中 0.03–0.18 s；冷启动 0.86–1.23 s | `service.py:stream_speech` |
| UC-402 | 换了音色 / 语速 / 风格后再朗读 | 不复用旧音频 | 这三项都进缓存键 | `service.py:_cache_key` |
| UC-403 | 合成到一半停止 | 不留下半截音频 | 只写 `.part`，完整结束才 `os.replace`；`finally` 删除临时文件 | `service.py:stream_speech` |
| UC-404 | 缓存目录持续增长 | 总占用不超过 256 MB | 超出按最后播放时间淘汰；命中时刷新 mtime，因此按「最近播放」而不是「最近生成」 | `service.py:_trim_cache` |
| UC-405 | 两个请求同时合成同一段 | 各自写各自的 `.part`，先完成者生效 | 末位覆盖，内容等价；不做跨请求去重锁，避免等待 | `service.py:stream_speech` |
| UC-406 | 缓存命中时并发已满 | 仍然返回音频 | busy 检查先看缓存；命中直接回放，不占用流式名额 | `service.py:stream_parameters` |
| UC-407 | 缓存文件被外部删除 | 自动重新合成，不报错 | 命中判断是 `is_file()` + 字节数，失败即走冷路径 | 同上 |

---

## 7. 设置、凭证与权限（UC-5xx）

| 编号 | 触发 | 预期现象 | 规则与边界 | 依据 |
|---|---|---|---|---|
| UC-501 | 保存语音配置 | 成功并回显脱敏状态 | `merge_settings` 逐字段校验：provider 白名单、语速 0.25–4、URL 必须是 http(s) 且不含凭据/查询串 | `configuration.py:merge_settings` |
| UC-502 | 密钥输入框留空后保存 | 保留原密钥 | `api_key` 为空串时跳过赋值；只有勾选「清除密钥」才置空 | `configuration.py:merge_settings` |
| UC-503 | 打开状态接口 | 只返回 `api_key_set`，不回显密钥 | `public_settings` 用布尔替换 `api_key` | `configuration.py:public_settings` |
| UC-504 | 非管理员改配置 / 准备模型 | 拒绝 | `PATCH /config`、`POST /prepare` 要求 `admin` | `api.py:configure`、`api.py:prepare` |
| UC-505 | 普通用户朗读或识别 | 允许，但只能取消自己的请求 | `transcribe`/`synthesize` 要求 `write`；取消按 `(owner, identity)` 匹配 | `api.py:transcribe`、`service.py:cancel` |
| UC-506 | 桌面端网页请求麦克风 | 仅主框架、仅回环源、仅 audio 授权；iframe 与外部源被拒 | `setPermissionCheckHandler` 与 `setPermissionRequestHandler` 同时把关，非 media 权限保持 Electron 默认行为 | `packaging/electron/speech-permissions.js` |
| UC-507 | ASR 用 MiMo 但语言选了方言 | 返回错误而不是静默识别错 | MiMo ASR 只接受 auto/zh/en，其它取值由 `providers.transcribe` 拒绝 | `providers.py:transcribe` |

---

## 8. 前端呈现（UC-6xx）

| 编号 | 触发 | 预期现象 | 规则与边界 | 依据 |
|---|---|---|---|---|
| UC-601 | 回答渲染完成 | 工具栏出现「朗读」 | `scan()` 给每个 answer-frame 工具栏补一个按钮，已存在则跳过 | `web/chat.js:scan` |
| UC-602 | 点「朗读」后 | 按钮变「停止朗读」并高亮 | 宽度从 34.6 px 变为 54.5 px，高度不变 | `web/chat.js:read` |
| UC-603 | 浅色主题下看播放态 | 文字仍然清晰 | 播放态用主文字色 + 淡紫底；不用 `--accent-1`（浅色主题下是 `#cba6f7`，0.62rem 小字读起来像缩小了） | `web/voice.css` |
| UC-604 | 窄窗口 | 按钮不换行、不被压缩 | `white-space: nowrap` + `flex: 0 0 auto`；420/520/760/1280 px 下尺寸一致 | `web/voice.css` |
| UC-605 | 朗读报错 | 浮窗打开并显示原因 | 只在仍是当前播放时提示，避免停止后弹错误 | `web/chat.js:read` 的 catch |
| UC-606 | 浏览器不支持 AudioContext | 提示不支持流式播放 | 抛错走同一 catch，不静默失败 | `web/chat.js:stream` |

---

## 9. 已知边界与设计取舍（UC-7xx）

| 编号 | 边界 | 说明 |
|---|---|---|
| UC-701 | 非 MiMo 没有增量音频 | 只有 MiMo 的 chat audio 提供分片；其它服务商整段返回，因此首块延迟等于整段合成时间 |
| UC-702 | 110 字窗口是折中 | 更小首块更快但请求更多；实测 110 字下单段音频约 10–20 s，远长于一次请求的生成时间，预取足以覆盖 |
| UC-703 | 缓存不加密 | 内容是合成音频，键是文本哈希；文本本身不落盘 |
| UC-704 | 不做跨进程共享 | 缓存目录属宿主进程，多实例部署时各自维护 |
| UC-705 | 本地 TTS 未实现 | 当前 `local` 只用于 ASR；插件仍只连接云端 TTS |
| UC-706 | 文本归一化依赖服务商 | 数字、单位、缩写由上游处理；本插件不做 G2P 或数字规则 |
| UC-707 | 浏览器自动化用例未入库 | `tests/js/voice_plugin_browser.cjs` 依赖旧的插件贡献渲染方式，待设置中心那批改动落地后一并提交 |

---

## 10. 测试覆盖映射（可复核）

| 用例 | 测试 |
|---|---|
| UC-201~203、UC-501~505 | `tests/test_speech_input.py` |
| UC-204~209 | `tests/test_voice_plugin.py`（本地准备、锁、取消、错误脱敏） |
| UC-301~313 | `tests/test_voice_plugin.py::test_streaming_tts_caches_pcm_and_replays_it`、`test_streaming_tts_keeps_partial_audio_out_of_the_cache`、`test_streaming_endpoint_rejects_non_mimo_providers` |
| UC-401~405 | 同上两项缓存用例；`_trim_cache` 由代码走查覆盖 |
| UC-506 | `tests/js/speech_input_runtime.cjs`（权限处理器 + 波形编码 + 草稿插入守卫） |
| UC-601~606 | `workspace/TempOutput/tswork/e2e_gap.py`、`e2e_cache.py`、`btn_narrow.py` 的实测记录；正式回归待 `voice_plugin_browser.cjs` 入库 |
| 端到端 | `scripts/smoke_speech_input.py --audio <16k-mono-pcm16.wav>` |
