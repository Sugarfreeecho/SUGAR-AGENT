**语音插件：流式朗读、按句预取与 PCM 缓存（2026-10-24）**

内置「语音输入与朗读」插件首个可提交版本，同时把 Final 卡片朗读从「整段等合成」改为边收边播。

**为什么要改。** 原实现把回答按 1800 字切段，每段用 `stream: false` 一次性请求 MiMo，必须等整段 WAV 生成、Base64 解码完才开始播放。实测 13 字 4.0 秒、69 字 8.7 秒、235 字 19.1 秒、500 字 70.5 秒，基本是「3 秒固定开销 + 每字 0.1–0.14 秒」，而且超线性。一条 800 字的回答，第一个字要等一分半以上；1800 字的段落还会撞上 `providers.request` 的 120 秒超时和 `service._api_job` 的 180 秒上限，表现是「等很久然后失败」。

**流式与 PCM16。** MiMo 的 `stream: true` 需要把 `audio.format` 指定为 `pcm16`，音频以 base64 分片出现在 SSE 的 `choices[0].delta.audio.data`，24 kHz 单声道。解析时有三类帧必须跳过：`delta.role` 的首帧、`audio: null` 的空帧，以及流末尾 `choices` 为空数组、只带 `usage` 的收尾帧——按 `choices[0]` 直接取会在最后一帧抛错。新端点 `POST /api/speech/synthesize/stream` 返回 `audio/pcm`，并带 `X-Sample-Rate`、`X-Channels`、`X-Format` 头；非 MiMo 服务商没有增量音频能力，返回 409 `streaming-unsupported`，前端据此退回整段合成。

**按句切段与预取。** 切分窗口从 1800 字降到 110 字，优先在句末切，其次退到逗号，最后才硬切，保证不把从句切两半。前端改用 Web Audio，PCM 分片到达即按音频时钟连续排期，因此首段一到就出声；消费当前段之前就发出下一段请求，段间不留空档。排期超过 24 秒时暂停拉取，长回答不会把整篇音频堆进内存。停止、切会话、播放另一张卡片都会关闭 `AudioContext` 并中止所有在途请求。

**缓存。** 按「服务商 + 模型 + 音色 + 语速 + 风格 + 文本」做 SHA-256，把 PCM 存到 `WORK_DIR/.config/speech-input/cache/`。只在完整合成后 `os.replace` 落盘，中途停止不会留下半截音频；容量上限 256 MB，按最后播放时间淘汰，命中时刷新 mtime。

**顺带修的按钮观感。** 「朗读」按下后变成「停止朗读」，实际尺寸是变宽（34.6px → 54.5px），并没有变小。真正的问题是播放态用 `--accent-1`，浅色主题下是 `#cba6f7` 淡紫，在浅灰底上对比度极低，0.62rem 的小字看起来像缩水。改为使用主文字色 + 淡紫底，并给按钮加 `white-space: nowrap` 与 `flex: 0 0 auto`，任何窗口宽度下都不换行、不压缩。

**实测（本机 i5-1130G7，无 GPU）。** 523 字回答冷启动 1.23 秒出声，段间空隙为 0；再次朗读同一段 0.03–0.18 秒；停止后立即静音且按钮复位。生成的 PCM 写成 WAV 后用本地 SenseVoice 回转写，内容与原文一致，缓存回放字节级相同。

**测试。** `tests/test_voice_plugin.py` 新增三项：缓存回放只调用一次上游、半截音频不落盘也不留 `.part`、非 MiMo 返回 409。连同 `tests/test_speech_input.py`、`tests/test_plugin_web_gateway.py` 共 30 项通过。`tests/js/speech_input_runtime.cjs` 通过。

主要实现文件：`plugins/voice-input/speech_input/providers.py`、`service.py`、`api.py`、`web/chat.js`、`web/shared.js`、`web/voice.css`，文档 `docs/speech_input.md`，桌面前置 `packaging/electron/speech-permissions.js` 与 `packaging/electron/main.js` 的接线。

逐条审查清单见 [`docs/Agent 设计（用户方案）/06-能力扩展加载/09-内置插件-语音输入与朗读方案设计-UseCase清单.md`](Agent%20设计（用户方案）/06-能力扩展加载/09-内置插件-语音输入与朗读方案设计-UseCase清单.md)（UC-101~707）；`06-能力扩展加载/00-整体设计` 的功能地图与 `00-总览与导航` 的份数同步为 9。

遗留：`tests/js/voice_plugin_browser.cjs` 依赖设置中心旧的贡献渲染方式，当前工作区里设置中心的改动尚未提交，该用例查不到 `plugin:voice-input:voice` 导航项，未随本次提交入库；待设置中心那批改动落地后一并提交。
