# MCP Paper Agent

<div align="center">

**反思智能体论文生成系统**

基于迭代优化的学术论文自动生成工具

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

</div>

---

## ✨ 功能特性

- 🔍 **MCP 优先检索** - 支持通过 HTTP/stdio MCP 服务联网搜索，并在失败时回退到 OpenRouter
- 📄 **正文抓取** - 对高价值来源自动抓取正文，增强引用与内容对齐
- ✍️ **自动生成** - 基于 LLM 自动生成结构化学术论文
- 🔄 **迭代优化** - 通过反思-修订循环持续提升论文质量
- 🧪 **引用校验** - 自动检查引用编号、来源覆盖和正文支持关系
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

### 推荐配置方式

项目支持两种搜索路径：

1. `MCP` 搜索
2. `OpenRouter` 联网搜索

推荐长期使用 `HTTP MCP`，因为：

- 配置更清晰
- 服务可单独部署
- 日志和问题排查更容易
- 可以复用搜索、正文抓取、来源过滤等工具

### 1. 获取 API Key / 服务

| 服务 | 用途 | 是否必需 | 获取地址 |
|------|------|----------|----------|
| OpenRouter | 论文生成、MCP 失败时兜底 | 是 | [openrouter.ai](https://openrouter.ai/keys) |
| Tavily | HTTP MCP 搜索后端 | 推荐 | [tavily.com](https://www.tavily.com/) |

### 2. 使用 `.env` 配置

推荐直接复制示例文件：

```bash
cp .env.example .env
```

最常用的一套 `HTTP MCP` 配置如下：

```env
# OpenRouter
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=openai/gpt-4o-mini
OPENROUTER_SEARCH_MODEL=perplexity/sonar

# HTTP MCP 服务
TAVILY_API_KEY=your_tavily_api_key_here
MCP_HTTP_HOST=127.0.0.1
MCP_HTTP_PORT=8000

# 主程序搜索配置
SEARCH_PROVIDER=mcp
MCP_TRANSPORT=http
MCP_SERVER_URL=http://127.0.0.1:8000
MCP_SEARCH_TOOL=web_search
MCP_FETCH_TOOL=fetch_url
MCP_TIMEOUT=30
```

如果你暂时不想启用 MCP，也可以直接改成：

```env
SEARCH_PROVIDER=openrouter
```

### 3. 关键配置项

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `OPENROUTER_API_KEY` | - | OpenRouter API 密钥（必需） |
| `OPENROUTER_MODEL` | `openai/gpt-4o-mini` | 生成模型 |
| `OPENROUTER_SEARCH_MODEL` | `perplexity/sonar` | 搜索模型 |
| `SEARCH_PROVIDER` | `mcp` | 搜索提供商，推荐 `mcp` |
| `MCP_TRANSPORT` | `http`/`stdio` | MCP 连接方式 |
| `MCP_SERVER_URL` | `http://127.0.0.1:8000` | HTTP MCP 服务地址 |
| `MCP_SEARCH_TOOL` | `web_search` | MCP 搜索工具名 |
| `MCP_FETCH_TOOL` | `fetch_url` | MCP 正文抓取工具名 |
| `TAVILY_API_KEY` | - | HTTP MCP 搜索后端密钥 |
| `TARGET_WORD_COUNT` | `1900` | 目标字数 |
| `MAX_ITERATIONS` | `3` | 最大迭代次数 |
| `MIN_QUALITY_SCORE` | `8.0` | 质量阈值 |
| `SEARCH_MAX_RESULTS` | `10` | 主检索每次结果数 |
| `SEARCH_SUPPLEMENTARY_MAX_QUERIES` | `1` | 每轮补充搜索最多查询数 |
| `SEARCH_SUPPLEMENTARY_MAX_TOTAL_ROUNDS` | `2` | 全文最多补充搜索轮数 |
| `SEARCH_SUPPLEMENTARY_MAX_RESULTS` | `4` | 补充搜索结果数 |

### 4. 快速模式

如果你更在意速度，而不是最强覆盖，可以在 `.env` 里改成：

```env
SEARCH_MAX_RESULTS=6
SEARCH_SUPPLEMENTARY_MAX_QUERIES=1
SEARCH_SUPPLEMENTARY_MAX_TOTAL_ROUNDS=1
SEARCH_SUPPLEMENTARY_MAX_RESULTS=3
MAX_ITERATIONS=1
TARGET_WORD_COUNT=1600
WORD_COUNT_TOLERANCE=300
MIN_QUALITY_SCORE=7.0
```

这通常能把一次生成时间明显压缩下来。

---

## 🌐 HTTP MCP 部署

### 1. 启动服务

如果 `.env` 已经配置好 `TAVILY_API_KEY`、`MCP_HTTP_HOST`、`MCP_HTTP_PORT`，直接启动：

```bash
uv run mcp-paper-mcp-http
```

也可以显式指定环境文件：

```bash
uv run mcp-paper-mcp-http --env-file .env
```

### 2. 健康检查

```bash
curl http://127.0.0.1:8000/health
```

返回：

```json
{"status":"ok"}
```

### 3. 当前 MCP 工具

内置 HTTP MCP 服务当前提供：

1. `web_search`
2. `fetch_url`

其中 `fetch_url` 会自动跳过部分高拦截站点，并在抓取失败时回退为摘要，不会直接导致整次论文生成失败。

更详细的部署说明见 [docs/http-mcp-server.md](./docs/http-mcp-server.md)。

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
uv run mcp-paper generate "人工智能在医疗领域的应用"

# 指定参数
uv run mcp-paper generate "量子计算的发展前景" -w 2000 -i 5

# 禁用缓存
uv run mcp-paper generate "区块链技术" --no-cache

# 详细输出
uv run mcp-paper generate "深度学习" -v

# 显示预览
uv run mcp-paper generate "自然语言处理" -p

# 指定别的环境文件
uv run mcp-paper --env-file .env generate "人工智能"

# 显式指定搜索提供商
uv run mcp-paper generate "人工智能" --search-provider mcp
```

#### 命令行参数

| 参数 | 简写 | 默认值 | 说明 |
|------|------|--------|------|
| `--output` | `-o` | `./papers/` | 输出目录 |
| `--max-iter` | `-i` | `3` | 最大迭代次数 |
| `--words` | `-w` | `1900` | 目标字数 |
| `--search-provider` | | 配置值 | 指定 `mcp` 或 `openrouter` |
| `--env-file` | | `.env` | 指定配置文件 |
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
│   ├── format_checker.py # 格式审查 - Markdown 规范检查
│   ├── evidence.py      # 证据抽取与来源覆盖
│   └── citation_checker.py # 引用一致性检查
├── cli/                 # 命令行界面
│   ├── main.py          # CLI 入口
│   ├── shell.py         # 交互式 Shell
│   └── styles.py        # 星座主题样式
├── mcp/                 # MCP 客户端与工具封装
├── mcp_server/          # 内置 HTTP MCP 搜索服务
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

## ⏱️ 性能建议

如果你发现一次生成耗时很长，通常是这几种原因：

1. `MAX_ITERATIONS` 太高，导致多轮反思修订。
2. 补充搜索过多，尤其是 `Reflector` 连续触发补搜。
3. `fetch_url` 在多个 PDF 或慢站点上等待超时。
4. 目标主题过宽，比如直接生成“人工智能”这类大综述。

建议优先这样调：

```env
MAX_ITERATIONS=1
SEARCH_MAX_RESULTS=6
SEARCH_SUPPLEMENTARY_MAX_QUERIES=1
SEARCH_SUPPLEMENTARY_MAX_TOTAL_ROUNDS=1
SEARCH_SUPPLEMENTARY_MAX_RESULTS=3
```

---

## ❓常见问题

### 1. 日志里出现大量 `fetch_url` 失败

这通常不是程序崩溃，而是目标网站拒绝抓取、证书异常或响应超时。当前逻辑会自动回退为搜索摘要继续生成。

### 2. 为什么正文和参考文献还是会有不匹配？

这个项目已经加入了来源覆盖、章节级引用约束和引用一致性检查，但如果搜索结果本身质量差，仍可能出现“结构完整但证据不足”的稿子。优先使用 `HTTP MCP + Tavily`，并尽量选更具体的论文主题。

### 3. 为什么生成这么慢？

大多是补充搜索和多轮修订导致。可参考上面的“性能建议”启用快速模式。

### 4. 启动 HTTP MCP 时还要每次手填 Tavily Key 吗？

不用。把 `TAVILY_API_KEY` 写进 `.env` 即可，之后直接运行：

```bash
uv run mcp-paper-mcp-http
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
- [Tavily](https://www.tavily.com/) - 搜索 API
- [Perplexity](https://perplexity.ai/) - 联网搜索模型
- [Rich](https://github.com/Textualize/rich) - 终端美化库
- [Click](https://click.palletsprojects.com/) - CLI 框架
