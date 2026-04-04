# MCP Paper Agent

反思智能体论文生成系统 - 基于迭代优化的学术论文自动生成工具

## 功能特性

- 🔍 **智能检索**: 使用 Tavily API 进行联网搜索，收集学术资料
- ✍️ **自动生成**: 基于 OpenRouter LLM 自动生成学术论文
- 🔄 **迭代优化**: 通过反思-修订循环持续提升论文质量
- 📋 **格式审查**: 自动检查 Markdown 格式和论文结构规范
- 💾 **智能缓存**: 缓存搜索结果，避免重复请求

## 快速开始

### 安装

```bash
uv sync
```

### 配置

1. 复制环境变量模板：
```bash
cp .env.example .env
```

2. 编辑 `.env` 文件，填入你的 API Key：
- `OPENROUTER_API_KEY`: OpenRouter API 密钥
- `TAVILY_API_KEY`: Tavily 搜索 API 密钥

### 使用

```bash
mcp-paper generate "人工智能在医疗领域的应用"
```

## 项目结构

```
src/mcp_paper_agent/
├── agents/          # 智能体模块
│   ├── retriever.py # 检索智能体
│   ├── generator.py # 生成智能体
│   ├── reflector.py # 反思智能体
│   └── revisor.py   # 修订智能体
├── core/            # 核心模块
│   ├── orchestrator.py   # 协调器
│   └── format_checker.py # 格式审查
├── cli/             # 命令行界面
└── utils/           # 工具模块
```

## 许可证

MIT
