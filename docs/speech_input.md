# 语音输入与 Final 朗读插件

「语音输入与朗读」直接接入现有 Agent 高级设置，与模型、插件等设置项并列，不再增加「Agent 高级设置」子分区。录音条的「语音设置」、右键或长按麦克风都直接打开该项。输入框旁保留麦克风，点一下就开始录音，显示独立浮窗；录音状态、音量、识别结果和取消操作均在浮窗中，不在输入框下方增加内容。原「···」入口已移除。

## API 配置

先开启语音插件，再分别配置 ASR（录音转文字）与 TTS（文字转语音）。地址、模型、密钥可以使用不同服务商。API Key 在后端写入 `WORK_DIR/.config/speech-input/settings.json`，接口不回显；留空保留已有密钥，勾选「清除密钥」才删除。

| 模式 | 地址与协议 | 参数 |
|---|---|---|
| 通用 ASR | 基础地址加 `/audio/transcriptions` | multipart `file`、`model`、可选 `language` |
| 通用 TTS | 基础地址加 `/audio/speech` | `input`、`model`、`voice`、`speed`，返回音频 |
| 小米 MiMo ASR | `https://api.xiaomimimo.com/v1/chat/completions` | `input_audio` data URL、`asr_options.language` |
| 小米 MiMo TTS | 同上 | 待读文本放在 assistant 消息，风格放在 user 消息，返回 `message.audio.data` |

选择 Xiaomi MiMo 时会填入预设：ASR `mimo-v2.5-asr`、TTS `mimo-v2.5-tts`。默认音色 `mimo_default`，也可填写冰糖、茉莉、苏打、白桦、Mia、Chloe、Milo、Dean 或服务商支持的其他音色。模型名称和基础地址均可修改。MiMo ASR 的语言选项为 auto、zh、en，方言可选 auto。官方接口：[ASR](https://mimo.mi.com/docs/zh-CN/api/audio/Speech-Recognition)、[TTS](https://mimo.mi.com/docs/en-US/quick-start/usage-guide/audio/speech-synthesis-v2.5)。

保存后回到聊天页。**点一下麦克风就开始录音**，不用再点第二次；录音条贴在输入框上方，显示红点、计时和实时波形，**再点一下麦克风结束**。识别完成后文字直接插入原草稿选区，录音条自动收起；草稿在录音期间被改过时，录音条改为显示识别结果，由「插入」或「取消」决定。最长 120 秒。

其他交互：

| 操作 | 结果 |
|---|---|
| 点麦克风 | 开始录音；已配置缺失时，录音条直接说明缺什么并提供「语音设置」 |
| 再点麦克风 / 点「完成」 | 结束录音并识别 |
| 点「取消」/ Escape / 点别处 | 丢弃本次录音并释放麦克风 |
| 右键麦克风 / 长按 0.55 秒 | 直接打开语音设置 |

录音期间切换会话、窗口失焦或页面隐藏都会丢弃录音。浏览器需 HTTPS 或本机环回地址，以及系统麦克风权限。

## Final 卡片朗读

启用 TTS 并保存配置后，Final 卡片工具栏提供「朗读 / 停止朗读」。勾选「回答完成后自动朗读」时，回答结束会自行开始朗读；未勾选则只有点击才发送文本。

朗读前先把回答拆成**按类型分块的语音计划**，每块单独请求、单独播放，块与块之间插入停顿：

| 块类型 | 读法 | 停顿 |
|---|---|---|
| 普通段落 | 原文 | 0.3 s |
| 标题 | 原文 | 0.4 s |
| 列表项 | 「第 N，」+ 原文 | 0.22 s |
| 引用 | 「引用：」+ 原文 | 0.35 s |
| 表格 | 先读「下面是一张表格，共 N 行，列有：…」，再逐行「第 N 行：列名，值；…」 | 提示 0.5 s，行 0.18 s |
| 代码块 | 只读「这里有一段 js 代码，共 N 行，就不逐行念了，请查看原文。」 | 0.45 s |
| 图片 | 「此处有一张图片：<alt 或图注>」 | 0.45 s |

超过 8 行的表格只读前 8 行，末尾补一句「其余 N 行请查看原文」。行内代码超过 24 字符或本身是 URL 时读作「一段代码」「链接」，不逐字拼读。表情符号与零宽字符不参与朗读。

**括号默认不读。** 中文 `（）` 与英文 `()` 里的内容（附注、日期、参数、文件名）默认跳过，设置里勾选「朗读括号里的内容」后才读；支持嵌套。

**长路径、链接、代码分开计数。** 行内代码按内容分类处理，连续的同类合并成一句：

| 内容 | 读法 | 例子 |
|---|---|---|
| URL | 一个链接 / N 个链接 | `https://example.test/a` |
| 带路径的文件（含 `/` 或 `\`） | 一个文件 / N 个文件 | `frontend/src/app/modules/sse-handling.js:301` |
| 单个短文件名（≤24 字符、无路径） | 照读 | `chat.js`、`message-rendering.js` |
| 其它长标识符 | 一段代码 / N 处代码 | 长哈希、`oc_sk_…` |

这样「…sse-handling.js:301、message-rendering.js、chat.js…」不会读成一串「一段代码、一段代码」。

播放中工具栏会出现「暂停 / 继续」和「从头」：暂停挂起音频时钟，已排期的音频停在原位置，继续后接着读；从头会丢弃当前进度重新开始，命中缓存时几乎立刻出声。切换会话、点击停止、播放另一张卡片或禁用插件会停止播放、取消未完成请求并释放音频上下文。不把生成音频写入会话或附件。

**边生成边读（自动朗读开启时）。** 回答还在流式生成时，界面上的内容是一行纯文本草稿（最终卡片要等运行提交才一次成型），所以这条路径直接读草稿并自己解析 markdown，只读「已经定型」的块：

- 除最后一块外都算定型；最后一块要等它后面出现新内容（或流结束）才读；
- 没写完的代码围栏不读；表格要等分隔行到齐才读，且提示语不带行数（行数会变，读出口就收不回）；
- 某一行的末尾带 `|` 时先不读，因为下一行可能是分隔行、把它变成表头；
- 已经读过的块如果文本被改写，立即停止——宁可断，也不读用户没看到的内容；
- 这一轮流式读过的回答，最终卡片不会再读一遍。

手动点「朗读」仍走最终卡片（渲染后的 DOM，质量最高）；两者共用一个播放会话，开始新的播放会先停掉旧的。

MiMo TTS 支持增量音频：前端用 `stream: true` + `pcm16` 请求，Web Audio 把到达的分片连续排期，因此首段音频一到就出声，不必等整段合成结束。其它服务商没有该能力，会自动退回整段合成。合成结果按「服务商 + 模型 + 音色 + 语速 + 风格 + 文本」哈希缓存为 PCM，放在 `WORK_DIR/.config/speech-input/cache/`，重复朗读同一段文字直接命中；缓存总量上限 256 MB，超出后按最久未播放优先淘汰。缓存只在完整合成后落盘，中断的请求不会留下半截音频。

## 资源与可选本地模式

API 模式只负责浏览器录音、网络传输和音频播放，不检查本地识别依赖，不下载或加载模型。计算在服务商端执行；录音或待读文字会发送给用户配置的服务商，网络、隐私和费用取决于该服务。此前下载的本地模型缓存保留在磁盘，但不会因选择 API 模式而加载。

本地模式仍支持 SenseVoiceSmall INT8 + Silero VAD CPU 识别。选择本地后，在应用 Python 中安装插件的可选依赖：

```powershell
python\python.exe -m pip install -r plugins/voice-input/requirements.txt
```

开启 ASR 并保存，再点击「下载并准备本地模型」。首次模型下载约 241 MB，运行库另占磁盘空间；建议预留 1 GB 可用内存。模型缓存位于 `WORK_DIR/.config/speech-input/models/`，固定版本和 SHA-256 校验后才发布。可选 Hugging Face、HF-Mirror 或自动回退。取消保留完整已校验文件，清理半成品。准备任务由后端拥有，关闭设置不会取消；禁用插件会取消准备和识别并释放进程。识别进程空闲五分钟后回收。

## 插件与接口

代码位于 `plugins/voice-input/`。Manifest 通过 `trusted_host` 注册路由和生命周期，通过 `chat.extension` 挂载前端，通过受信任的 `settings.section` 渲染器直接贡献设置分区（`/settings#plugin:voice-input:voice`）。宿主只提供通用输入框接口和会话切换事件。普通插件不能通过 Manifest 获得宿主页代码执行权限。

`/api/speech/status` 返回状态与脱敏配置；`PATCH /api/speech/config` 保存设置；`POST /api/speech/transcribe` 接收 WAV；`POST /api/speech/synthesize` 接收 `{requestId,text}` 并返回音频；`POST /api/speech/synthesize/stream` 接收同样的请求体，返回 `audio/pcm` 分片，并带 `X-Sample-Rate`、`X-Channels`、`X-Format` 头；仅 MiMo 支持，其它服务商返回 409 `streaming-unsupported`。`DELETE /api/speech/transcriptions/{id}` 按当前身份取消请求。配置与模型准备需要管理员权限，识别、朗读及取消自己的请求需要写权限。音频上限 4 MiB、120 秒，单次 TTS 文本上限 4000 字符。云端响应有大小和时间限制，错误不回传密钥或服务商原始响应体。

默认安装依赖不再包含语音原生运行库。已有安装版需重新打包更新，源码版更新后构建前端并重启服务。

## 验证

```powershell
python\python.exe -m pytest tests/test_voice_plugin.py tests/test_speech_input.py tests/test_plugin_settings.py tests/test_input_actions_runtime.py -q
node tests/js/speech_input_runtime.cjs
node tests/js/voice_plugin_browser.cjs
python\python.exe -X utf8 scripts/check_frontend_dist_sync.py
```

浏览器测试使用独立的无头 Edge 和模拟麦克风，验证设置导航与话筒直达入口、MiMo 预设、一步录音与录音条、草稿冲突、Final 朗读、停止及插件释放。云端协议使用模拟响应测试；实际云端调用需要用户配置有效 API Key。本地模型可用 `scripts/smoke_speech_input.py --audio <16k-mono-pcm16.wav>` 独立验证。
