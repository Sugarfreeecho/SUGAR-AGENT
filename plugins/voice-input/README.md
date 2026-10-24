# 语音输入与朗读

随 SugarAgent 发布的内置插件。「语音输入与朗读」直接显示在现有 Agent 高级设置的导航中，与模型、插件等设置项并列。话筒浮窗的「语音设置」直接打开该项。插件贡献麦克风浮窗与 Final 卡片的朗读按钮，禁用时释放录音、网络请求和识别进程。

识别支持通用 `/audio/transcriptions`、小米 MiMo `/chat/completions`，以及可选本地 SenseVoice。朗读支持通用 `/audio/speech` 与小米 MiMo chat audio。API Key 只在后端保存，状态接口只返回是否已配置；留空保留，勾选清除才删除。

API 模式不检查、下载或加载本地模型。`requirements.txt` 只用于本地 SenseVoice，不属于默认安装依赖。

MiMo 预设：基础地址 `https://api.xiaomimimo.com/v1`，识别模型 `mimo-v2.5-asr`，朗读模型 `mimo-v2.5-tts`，默认音色 `mimo_default`。模型和音色均可手动修改。识别与朗读分别填写密钥，可使用同一账号的 API Key。

详见 [使用说明](../../docs/speech_input.md)。
