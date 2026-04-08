# HTTP MCP 搜索服务部署说明

这个仓库内置了一个最小可用的 HTTP MCP 搜索服务，适合长期部署给主程序使用。

## 1. 安装依赖

```bash
uv sync
```

如果你不用 `uv`，也可以使用：

```bash
pip install -e .
```

## 2. 启动 HTTP MCP 搜索服务

默认会优先读取 `.env` 里的 `MCP_HTTP_HOST`、`MCP_HTTP_PORT` 和 `TAVILY_API_KEY`；如果没有，再回退到 `127.0.0.1:8000`。

最简单的长期配置方式是在项目根目录 `.env` 里写：

```env
TAVILY_API_KEY=你的密钥
MCP_HTTP_HOST=127.0.0.1
MCP_HTTP_PORT=8000
```

然后直接启动：

```bash
mcp-paper-mcp-http --host 127.0.0.1 --port 8000
```

如果你想显式指定 `.env` 文件，也可以：

```bash
mcp-paper-mcp-http --env-file .env
```

如果你临时覆盖 Tavily Key，仍然可以直接传参，这样搜索质量会更稳定：

```bash
mcp-paper-mcp-http --host 127.0.0.1 --port 8000 --tavily-api-key YOUR_KEY
```

未提供 Tavily Key 时，服务会自动回退到 DuckDuckGo 页面搜索。

`fetch_url` 在抓取某些站点正文时可能会遇到目标网站的 `403 Forbidden`。这是目标网站的反爬/访问策略，不是主程序崩溃。现在服务会在这类情况下自动回退到搜索摘要，不再把整次 MCP 调用直接打成 500 重试。

## 3. 验证服务是否启动成功

健康检查：

```bash
curl http://127.0.0.1:8000/health
```

期望返回：

```json
{"status":"ok"}
```

MCP 初始化检查：

```bash
curl -X POST http://127.0.0.1:8000/ ^
  -H "Content-Type: application/json" ^
  -d "{\"jsonrpc\":\"2.0\",\"id\":\"1\",\"method\":\"initialize\",\"params\":{}}"
```

## 4. 让主项目连接这个 HTTP MCP 服务

把 `.env` 配成下面这样：

```env
SEARCH_PROVIDER=mcp
MCP_TRANSPORT=http
MCP_SERVER_URL=http://127.0.0.1:8000
MCP_SEARCH_TOOL=web_search
MCP_TIMEOUT=30
```

然后运行：

```bash
mcp-paper generate "计算机神经网络"
```

## 5. 生产环境建议

1. 将 HTTP MCP 服务和主程序分开运行。
2. 固定端口，避免频繁变更 `MCP_SERVER_URL`。
3. 优先配置 Tavily Key，搜索结果更稳定。
4. 保留 OpenRouter 配置作为兜底，主程序在 MCP 失败时会自动回退。
5. 可以通过进程守护工具长期运行这个服务。

## 6. 当前服务支持的 MCP 方法

1. `initialize`
2. `tools/list`
3. `tools/call`

当前内置工具：

1. `web_search`
