# MyAgent Developer

一个本地运行的 AI Agent 开发与使用平台。通过浏览器 Web UI 提供会话式交互，由 Python FastAPI 后端驱动 ReAct 推理循环、工具调用、子 Agent 编排、上下文压缩、MCP 扩展和会话持久化。

## 特性

- 会话式 AI Agent 交互界面
- ReAct 推理循环与工具调用
- 子 Agent 编排与任务分解
- 上下文压缩与记忆管理
- MCP (Model Context Protocol) 扩展支持
- 会话持久化与审计日志

## 快速开始

### 前置要求
- Python 3.10+
- Node.js (用于前端开发)
- Git

### 安装
1. 克隆仓库：
   ```bash
   git clone https://github.com/你的用户名/myagent-developer.git
   cd myagent-developer
   ```

2. 安装 Python 依赖：
   ```bash
   pip install -r requirements.txt  # 如果存在
   ```

3. 配置环境变量：
   复制 `.env.example` 到 `.env` 并填入必要的配置（如 API 密钥）。

4. 启动服务：
   ```bash
   # Windows
   RUN.bat
   # 或手动启动
   python app/main.py
   ```

5. 打开浏览器访问 `http://127.0.0.1:8192/`

## 项目结构

```
MyAgent Developer/
├── app/                  # 后端应用
│   ├── main.py          # 主入口
│   ├── webui.py         # FastAPI 应用
│   └── templates/       # 前端模板
├── frontend/            # 前端源代码
├── workspace/           # 工作区数据 (gitignore)
├── logs/                # 运行日志 (gitignore)
├── RUN.bat              # Windows 启动脚本
└── SPEC.md              # 工程规格说明
```

## 配置

配置通过环境变量管理，主要配置项：
- `OPENAI_API_KEY` 或其他 LLM 提供商的 API 密钥
- `OPEN_BROWSER` 是否自动打开浏览器 (默认 true)
- `HOST` 和 `PORT` 服务监听地址

详细配置请参考 `SPEC.md`。

## 开发

### 前端开发
```bash
cd frontend
npm install
npm run dev
```

### 后端开发
后端使用 FastAPI，支持热重载。

## 部署

### 生产部署
1. 设置环境变量
2. 运行 `RUN.bat` 或使用 `python app/main.py`
3. 建议使用反向代理（如 Nginx）并启用 HTTPS

### Docker 部署 (计划中)
```bash
docker build -t myagent-developer .
docker run -p 8192:8192 myagent-developer
```

## 许可证

请查看 LICENSE 文件（如果存在）。

## 贡献

欢迎贡献！请阅读 CONTRIBUTING.md（如果存在）了解如何参与。

## 联系方式

有问题或建议？请创建 GitHub Issue 或联系维护者。
