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

默认启动在 `127.0.0.1:8000`：

```bash
mcp-paper-mcp-http --host 127.0.0.1 --port 8000
```

如果你有 Tavily Key，推荐一起传入，这样搜索质量会更稳定：

```bash
mcp-paper-mcp-http --host 127.0.0.1 --port 8000 --tavily-api-key YOUR_KEY
```

未提供 Tavily Key 时，服务会自动回退到 DuckDuckGo 页面搜索。

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
