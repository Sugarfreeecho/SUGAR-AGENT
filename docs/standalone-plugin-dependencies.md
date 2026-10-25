# Standalone 插件依赖清单与获取方式

适用于不随安装包分发的 6 个 `standalone` 插件：`voice-input`、`chatgpt-subscription`、
`feishu-transport`、`game-arena`、`repo-engineering`、`sugar-bili-scroll`。

每个插件目录下的 `requirements.txt` 就是它的依赖清单；文件里只有注释表示“无第三方依赖”。

## 1. 依赖总表

| 插件 | 第三方依赖 | 用途 | 是否必需 |
|---|---|---|---|
| `voice-input` | `sherpa-onnx==1.13.8`、`numpy>=1.24,<2` | 本地 SenseVoice 离线识别 | 可选（API 语音不需要） |
| `chatgpt-subscription` | `PyJWT[crypto]>=2.10,<3`、`pywin32>=306; win32` | 订阅令牌解析 / DPAPI 保存凭据 | 必需 |
| `feishu-transport` | `lark-oapi>=1.0` | 飞书长连接与消息 API（传输实现已在本插件内） | 必需 |
| `game-arena` | 无（标准库 + `myagent_plugin_sdk`） | 五子棋 / 围棋 worker | — |
| `repo-engineering` | 无（纯声明式 skills） | 仓库工程流程 | — |
| `sugar-bili-scroll` | `aiohttp>=3.9,<4`、`bilibili-api-python>=17.4,<18`、`pillow>=10`、`faster-whisper>=1.0,<2` | B站接口、表情处理、视频转写 | `faster-whisper` 可选 |

## 2. 装到哪里

| 场景 | 解释器 | 说明 |
|---|---|---|
| 应用内置运行时（推荐） | `<安装目录>\resources\runtime\python\python.exe`；源码环境 `python\python.exe` | `trusted_host` 插件在应用进程内运行，依赖必须装到这里 |
| 插件本地 venv | 安装器自动创建 `plugins/<id>/.myagent-runtime/python` | 仅 `runtime` worker 插件需要；安装器读 `requirements.txt` 自动装 |
| 源码开发 | 仓库自带 `python\python.exe` | 与“应用内置运行时”相同 |

`requirements.txt` 只有注释时，安装器不会创建 venv（按“无依赖”处理）。

## 3. 获取方式

### 3.1 外网 PyPI

```powershell
python\python.exe -m pip install -r plugins\sugar-bili-scroll\requirements.txt
```

### 3.2 华为云镜像（外网可访问）

```powershell
python\python.exe -m pip install -r plugins\sugar-bili-scroll\requirements.txt `
  --index-url https://mirrors.huaweicloud.com/repository/pypi/simple
```

### 3.3 华为内网镜像

把 `--index-url` 换成公司内网 PyPI 源（由 IT/镜像站提供，形如 `https://<内网镜像>/repository/pypi/simple`）：

```powershell
$env:PIP_INDEX_URL = 'https://<内网镜像>/repository/pypi/simple'
$env:PIP_TRUSTED_HOST = '<内网镜像>'
python\python.exe -m pip install -r plugins\sugar-bili-scroll\requirements.txt
```

- 插件安装器创建的本地 venv 也继承 `PIP_INDEX_URL` / `PIP_TRUSTED_HOST`，无需额外参数。
- 离线环境可先在有网机器 `pip download -r requirements.txt -d wheels`，再拷贝目录并 `--no-index --find-links wheels` 安装。
- 桌面版补装依赖同样用内置 pip：

```powershell
"%LOCALAPPDATA%\Programs\SugarAgent\resources\runtime\python\python.exe" -m pip install ^
  -r "plugins\sugar-bili-scroll\requirements.txt" --index-url https://mirrors.huaweicloud.com/repository/pypi/simple
```

## 4. 安装后自检

```powershell
python\python.exe -c "import sherpa_onnx, numpy; print('voice ok')"
python\python.exe -c "import jwt, cryptography, win32crypt; print('chatgpt ok')"
python\python.exe -c "import lark_oapi; print('feishu ok')"
python\python.exe -c "import aiohttp, bilibili_api, PIL, faster_whisper; print('bili ok')"
```

`game-arena` / `repo-engineering` 无第三方依赖，跳过即可。

## 5. 版本口径

- 版本下限来自各插件 `requirements.txt`；`sherpa-onnx` 固定为 `1.13.8`（与语音插件内置模型匹配）。
- `numpy` 限制 `<2`，与 `sherpa-onnx` / `faster-whisper` 的 ABI 兼容。
- 这些包**不进入**桌面安装包（`standalone` 不打包），因此不影响安装包体积。
