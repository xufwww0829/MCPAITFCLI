# MCP Paper Agent

<div align="center">

**反思智能体论文生成系统**

基于迭代优化的学术论文自动生成工具

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

</div>

---

## ✨ 功能特性

- 🔍 **智能检索** - 使用 Perplexity 联网模型进行学术资料搜索
- ✍️ **自动生成** - 基于 LLM 自动生成结构化学术论文
- 🔄 **迭代优化** - 通过反思-修订循环持续提升论文质量
- 📋 **格式审查** - 自动检查 Markdown 格式和论文结构规范
- 💾 **智能缓存** - 缓存搜索结果，避免重复请求
- 🎮 **交互模式** - 类似 opencode 的交互式命令行界面

---

## 📦 安装

### 方式一：使用 uv 安装（推荐）

```bash
# 克隆项目
git clone https://github.com/yourusername/mcp-paper-agent.git
cd mcp-paper-agent

# 安装为全局工具
uv tool install .
```

### 方式二：从 PyPI 安装（即将支持）

```bash
pip install mcp-paper-agent
```

---

## ⚙️ 配置

### 1. 获取 API Key

| 服务 | 用途 | 获取地址 |
|------|------|----------|
| OpenRouter | LLM 生成 + 联网搜索 | [openrouter.ai](https://openrouter.ai/keys) |

### 2. 设置环境变量

**Windows (PowerShell):**
```powershell
[Environment]::SetEnvironmentVariable("OPENROUTER_API_KEY", "your-api-key-here", "User")
```

**macOS / Linux:**
```bash
echo 'export OPENROUTER_API_KEY="your-api-key-here"' >> ~/.bashrc
source ~/.bashrc
```

### 3. 可选配置项

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `OPENROUTER_API_KEY` | - | OpenRouter API 密钥（必需） |
| `OPENROUTER_MODEL` | `openai/gpt-4o-mini` | 生成模型 |
| `OPENROUTER_SEARCH_MODEL` | `perplexity/sonar` | 搜索模型 |
| `TARGET_WORD_COUNT` | `1900` | 目标字数 |
| `MAX_ITERATIONS` | `3` | 最大迭代次数 |
| `MIN_QUALITY_SCORE` | `8.0` | 质量阈值 |

---

## 🚀 使用指南

### 交互模式（推荐）

直接运行命令进入交互界面：

```bash
mcp-paper
```

```
╔════════════════════════════════════════════════════════════════╗
║           ✦ Paper Agent - 反思智能体论文生成系统 ✦              ║
╚════════════════════════════════════════════════════════════════╝

输入 /help 查看可用命令，直接输入主题开始生成论文

┌─ 🔄 反思模式 │ 📝 1900字 │ 🔄 3轮 │ 📦 缓存
└─▶ 
```

#### 交互命令

| 命令 | 说明 | 示例 |
|------|------|------|
| `/mode reflect` | 切换到反思模式（多轮迭代） | `/mode reflect` |
| `/mode direct` | 切换到直接模式（单次生成） | `/mode direct` |
| `/config` | 查看当前配置 | `/config` |
| `/set <key> <value>` | 设置参数 | `/set words 2000` |
| `/help` | 显示帮助 | `/help` |
| `/clear` | 清屏 | `/clear` |
| `/history` | 显示历史 | `/history` |
| `/exit` | 退出 | `/exit` |

#### 参数设置

```
/set iterations 5    # 设置最大迭代次数
/set words 2000      # 设置目标字数
/set cache off       # 关闭缓存
/set verbose on      # 开启详细模式
```

#### 生成论文

直接输入主题即可：

```
┌─ 🔄 反思模式 │ 📝 1900字 │ 🔄 3轮 │ 📦 缓存
└─▶ 人工智能在医疗领域的应用

✦ 开始生成论文 ✦
主题: 人工智能在医疗领域的应用

✹ 检索资料中... ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100%
...
```

### 命令行模式

适合脚本调用或快速生成：

```bash
# 基本用法
mcp-paper generate "人工智能在医疗领域的应用"

# 指定参数
mcp-paper generate "量子计算的发展前景" -w 2000 -i 5

# 禁用缓存
mcp-paper generate "区块链技术" --no-cache

# 详细输出
mcp-paper generate "深度学习" -v

# 显示预览
mcp-paper generate "自然语言处理" -p
```

#### 命令行参数

| 参数 | 简写 | 默认值 | 说明 |
|------|------|--------|------|
| `--output` | `-o` | `./papers/` | 输出目录 |
| `--max-iter` | `-i` | `3` | 最大迭代次数 |
| `--words` | `-w` | `1900` | 目标字数 |
| `--no-cache` | | | 禁用缓存 |
| `--preview` | `-p` | | 显示论文预览 |
| `--verbose` | `-v` | | 详细输出 |

### 其他命令

```bash
# 查看配置
mcp-paper config

# 清空缓存
mcp-paper cache --all

# 查看版本
mcp-paper --version

# 查看帮助
mcp-paper --help
```

---

## 📁 项目结构

```
src/mcp_paper_agent/
├── agents/              # 智能体模块
│   ├── retriever.py     # 检索智能体 - 联网搜索资料
│   ├── generator.py     # 生成智能体 - 生成论文大纲和内容
│   ├── reflector.py     # 反思智能体 - 质量评估
│   └── revisor.py       # 修订智能体 - 针对性修改
├── core/                # 核心模块
│   ├── orchestrator.py  # 协调器 - 流程控制
│   └── format_checker.py # 格式审查 - Markdown 规范检查
├── cli/                 # 命令行界面
│   ├── main.py          # CLI 入口
│   ├── shell.py         # 交互式 Shell
│   └── styles.py        # 星座主题样式
├── config.py            # 配置管理
└── logger.py            # 日志系统
```

---

## 🔄 工作流程

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   检索资料   │ ──▶ │   生成初稿   │ ──▶ │   迭代优化   │
│  (Retriever) │     │ (Generator)  │     │             │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                    ┌──────────────────────────┘
                    │
                    ▼
            ┌─────────────┐     ┌─────────────┐
            │   质量评估   │ ──▶ │   论文修订   │
            │ (Reflector)  │     │  (Revisor)  │
            └─────────────┘     └─────────────┘
                    │                   │
                    └─────── ◀ ─────────┘
                        (循环直到达标)
```

### 评估维度

| 维度 | 权重 | 说明 |
|------|------|------|
| 内容准确性 | 30% | 基于资料、无事实错误 |
| 结构逻辑 | 20% | 章节连贯、论证层次 |
| 引用恰当性 | 10% | 引用支持论点 |
| 语言表达 | 10% | 语法、用词、学术风格 |
| 字数符合度 | 15% | 符合目标字数范围 |
| 格式规范性 | 15% | Markdown 格式正确 |

---

## 📝 输出示例

生成的论文保存在 `./papers/` 目录：

```
papers/
├── 人工智能在医疗领域的应用_20240404_103000.md
├── 量子计算的发展前景_20240404_110500.md
└── ...
```

论文格式：

```markdown
# 人工智能在医疗领域的应用

## 摘要

本文探讨了人工智能技术在医疗领域的应用现状...

## 引言

随着人工智能技术的快速发展...

## 主体内容

### 医学影像诊断
...

### 药物研发
...

## 结论

...

## 参考文献

[1] 来源标题. https://example.com/article1
[2] 来源标题. https://example.com/article2
```

---

## 🛠️ 开发

### 环境设置

```bash
# 克隆项目
git clone https://github.com/yourusername/mcp-paper-agent.git
cd mcp-paper-agent

# 安装开发依赖
uv sync

# 运行测试
uv run pytest

# 代码检查
uv run ruff check .
uv run mypy .
```

### 添加新功能

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

---

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

---

## 🙏 致谢

- [OpenRouter](https://openrouter.ai/) - LLM API 服务
- [Perplexity](https://perplexity.ai/) - 联网搜索模型
- [Rich](https://github.com/Textualize/rich) - 终端美化库
- [Click](https://click.palletsprojects.com/) - CLI 框架
