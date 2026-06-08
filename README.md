# WaveMate

WaveMate 是一个面向无线分析与虚拟专家协作的本地 AI Agent 平台。它通过浏览器 Web UI 提供会话式交互，由 Python FastAPI 后端驱动 ReAct 推理循环、工具调用、子 Agent 编排、上下文压缩、MCP 扩展和会话持久化。

## 核心能力

- 会话式 AI 交互
- ReAct 推理与工具调用
- 子 Agent 任务拆分与协作
- 上下文压缩与记忆管理
- MCP 扩展支持
- 会话持久化与审计日志

## 快速开始

### 环境要求

- Python 3.10+
- Node.js
- Git

### 本地运行

1. 安装后端依赖

```bash
pip install -r app/requirements.txt
```

2. 配置环境变量

复制 `.env.example` 为 `.env`，并填写 API Key、模型名、工作目录等配置。

3. 启动服务

```bash
# Windows
RUN.bat

# 或手动启动
python app/main.py
```

4. 打开浏览器

访问 `http://127.0.0.1:8192/`

## 目录说明

```text
app/          后端、Agent 核心、路由与模板
frontend/     前端源码与构建入口
workspace/    工作区数据
logs/         运行日志
RUN.bat       Windows 启动脚本
SPEC.md       工程规格说明
```

## 开发前端

```bash
cd frontend
npm install
npm run dev
```

## 反馈与支持

如果你在使用中遇到问题，欢迎直接到 GitHub 提交 Issue 反馈。
