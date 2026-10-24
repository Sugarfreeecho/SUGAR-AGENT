# ChatGPT Subscription · SugarAgent 插件

通过官方 **Sign in with ChatGPT** 登录，为 SugarAgent 接入用户授权的 ChatGPT 套餐额度。
需要符合条件的账号与应用授权；是否可用由 OpenAI 的账号、工作区和套餐政策决定。

账号、登录、模型与推理适配业务均位于 `plugins/chatgpt-subscription/`。
通过 `trusted_host` 插件接口注册设置入口与生命周期；本机 Responses 适配服务复用
SugarAgent 的现有 `openai-responses` 模型协议。1.1.0 使用设置宿主新增的通用内嵌协议，
直接显示在 **设置 → ChatGPT 订阅** 页签中，并跟随设置窗口的主题、字号和语言。
旧版宿主未支持 `embedded` 声明时，仍可从页签按钮打开插件界面。

1.1.1 修复订阅接口未返回 `Content-Type` 时，有效事件流被误报为 502 的问题。
响应按实际 SSE 事件校验；空响应、HTML/JSON 错误页和中断流仍会报错。
若最终完成事件省略 `output`，使用之前的已完成输出项补齐，保留正文、工具调用及用量，
避免标题与摘要调用返回空文本；不会把未完成的增量拼成成功响应。
更新插件后，设置接口也会切换到新的插件实现。

## 安装与使用

1. 将本目录完整放到 **SugarAgent 程序目录**的 `plugins/chatgpt-subscription/` 下，
   确认 `.myagent-plugin/plugin.json` 存在。ZIP 解压后应保持这一层目录结构。
2. 为运行 SugarAgent 的 Python 安装签名验证依赖。Windows 源码版在仓库根目录运行：

   ```powershell
   .\python\python.exe -m pip install -r .\plugins\chatgpt-subscription\requirements.txt
   ```

   Linux/macOS 使用 SugarAgent 对应虚拟环境的 Python：

   ```sh
   .venv/bin/python -m pip install -r plugins/chatgpt-subscription/requirements.txt
   ```

   还复用宿主已有的 `httpx`、`FastAPI`；Windows 凭据保护使用宿主已有的 `pywin32`。
   此插件的宿主适配器在 SugarAgent 进程内运行，因此依赖须装入**宿主 Python**，
   仅安装到插件私有 Worker 虚拟环境无效。当前工程运行时已有这些依赖。
3. 重启 SugarAgent，确认「插件」中 **ChatGPT Subscription** 已启用。
4. 打开 **设置 → ChatGPT 订阅**。当前仓库已支持内嵌，无需再打开独立窗口。
5. 点击 **Continue with ChatGPT**，在系统浏览器选择账号、工作区并授权使用套餐。
   浏览器没有自动打开时，可点击页签中的授权链接。完成授权后，设置页签会自动更新。
6. 连接成功或切换账号后，会自动读取模型。可按名称或模型 ID 筛选，编辑 **配置名称**，
   再点击 **添加模型**。已添加的模型会显示状态；修改名称可更新配置。
7. 可手动点击 **测试调用** 验证访问权限；每次发送一条简短请求，使用少量套餐额度。
   页面加载和读取目录不会自动发起推理测试。
8. **已添加的配置** 列出当前账号的模型，**管理模型** 在同一个设置窗口内切到模型页。
   回到聊天页后，在模型菜单中选择你设置的名称。添加配置不会替换当前会话的模型。

每个模型配置绑定一个明确的账号注册。可添加多个账号或工作区、对各连接重新授权或退出。
同名邮箱可能对应不同工作区，连接编号用于区分。重复添加同一账号和模型会更新该配置。
页面会保留当前选择和尚未提交的配置名称，切换设置页签后可继续编辑。
首次连接套餐时显示一次用量说明；可从 **管理用量** 直接打开 ChatGPT Usage 设置。

**安装位置要求：**仓库现有安全策略只允许直接位于程序 `plugins/<插件 id>/` 的原生插件
加载 `trusted_host`。放到工作区技能目录或其他自定义插件发现目录不会取得此能力。
本插件不修改这个策略，安装后无需给 agent 增加模型侧工具。

## 调用方式

```text
SugarAgent ReAct / 标题 / 摘要 / Judge
    → 账号绑定的本机 /accounts/<id>/v1/responses
    → 插件读取、必要时续期 OAuth 授权
    → https://api.openai.com/v1/responses
    → SugarAgent 原有工具调度、权限与会话记录
```

- 本机服务只绑定 `127.0.0.1`，首次启动分配端口并持久保存，重启时复用。
  服务需要随机本机 Bearer 凭据，并校验 Host；不启用 CORS。设置操作只允许本机同源浏览器。
- 模型配置只保存本机服务凭据。OpenAI access/refresh/ID token 不进入模型配置、浏览器存储或源代码。
- 使用 OAuth PKCE、一次性 state、nonce 和 OpenAI JWKS 验证 ID token 签名、issuer、audience、有效期。
  只有已授予 `chatgpt.tokens.use.direct` 的连接可发起推理。
- 刷新凭据时使用进程间文件锁，串行完成刷新及原子写入，保留最新的旋转 refresh token。
- 上游每次发送完整历史、`store=false` 和 `stream=true`。SugarAgent 的非流式辅助调用由插件
  读取上游完成事件后组装原生 Responses JSON，保留 usage。
- 函数工具放入 `sugaragent` namespace，仍由 SugarAgent 原有权限与执行器在本地执行。
  插件不代理 OpenAI 托管 MCP、Code Interpreter、图片生成或 `tool_search`。
- 只有收到 `response.completed` 才把辅助调用当作成功；流中断或额度错误不会伪装为完整回复。
  主会话的 `response.incomplete` 保留原有的截断语义。
- 不向该预览接口发送 `max_output_tokens`、温度等不支持参数，因此输出上限由上游控制。
  `responses.compact` 没有代理接口，SugarAgent 将使用自身已有的本地摘要/裁剪回退。
- 模型目录来自当前 OAuth 账号。目录中的模型是否能完成调用，仍须以实际推理结果确认。

插件使用标准 TLS 验证，通过 HTTPX 读取宿主配置的代理环境变量。不会复制 Codex 登录文件，
不会连接 ChatGPT 内部 `backend-api`，也不提供通用公网转发端点。

## 凭据存放与退出

- Windows：`%LOCALAPPDATA%/SugarAgent/plugins/chatgpt-subscription/credentials.json`，
  整份记录使用当前 Windows 用户的 **DPAPI** 加密。
- Linux/macOS：`${XDG_CONFIG_HOME:-~/.config}/sugaragent/plugins/chatgpt-subscription/credentials.json`，
  目录权限 `0700`、文件权限 `0600`。这两个平台使用文件权限保护，未实现系统钥匙串加密。

存储与插件源目录、工作区分开，更新插件不会覆盖登录信息。退出登录会尝试撤销 refresh session，
随后删除本地令牌并保留账号注册和 host ID；若远程撤销未确认，页面会提示到 ChatGPT 设置断开应用。
退出不会删除模型配置；其调用会返回重新登录提示。禁用插件后本机服务停止，配置会不可用。

额度以 **ChatGPT 设置 → Usage** 为准。插件不估算剩余额度，也不会把其他账号或 API Key
自动当作此连接的替代凭据。SugarAgent 自身若配置了备用模型，其既有故障切换规则仍然适用。

端口被占用时，请关闭其他使用同一登录存储的 SugarAgent 实例，然后重新尝试登录。
配置凭据不能跨 Windows 用户解密；迁移到另一台机器时请重新登录。

## 验证与打包

在仓库根目录运行：

```powershell
.\python\python.exe -m pytest plugins/chatgpt-subscription/tests -q
.\python\python.exe plugins/chatgpt-subscription/package.py --output .config/artifacts/chatgpt-subscription-1.1.1.zip
```

测试使用模拟 OpenAI HTTP/SSE 服务和真实本机 HTTP 通道，覆盖签名验证、PKCE、账号与权限、
令牌续期、凭据保护、工具调用、辅助请求和异常流。测试不会登录真实账号或消耗套餐额度。
真实授权和模型可用性需在用户浏览器完成登录后验证。

界面开发可用 `python plugins/chatgpt-subscription/tests/preview.py` 启动本机模拟服务，
使用真实设置外壳和插件静态资源验证内嵌流程，不会修改真实登录或消耗套餐额度。

## 官方接口依据

实现依据于 2026-10-20 核对的官方文档；此能力处于预览阶段，接口限制可能更新。

- [Registration and sign-in](https://developers.openai.com/siwc/token-sharing-open-source/sign-in)
- [Accounts and sessions](https://developers.openai.com/siwc/token-sharing-open-source/profiles-and-sessions)
- [Models and inference](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference)
- [Preview limitations](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations)
- [UI/UX guidelines](https://developers.openai.com/siwc/ui-ux-guidelines)
