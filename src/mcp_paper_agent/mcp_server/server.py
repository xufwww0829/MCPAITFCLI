"""最小可用的 HTTP MCP 搜索服务。"""

from __future__ import annotations

import json
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Optional

import click

from mcp_paper_agent import __version__
from mcp_paper_agent.logger import get_logger
from mcp_paper_agent.mcp_server.search_backend import SearchBackend, SearchItem, build_default_backend

logger = get_logger()


class MCPServerError(Exception):
    """MCP 服务错误。"""

    def __init__(self, message: str, code: int = -32603) -> None:
        super().__init__(message)
        self.code = code


class SearchMCPService:
    """搜索服务对应的 MCP 方法处理器。"""

    TOOL_NAME = "web_search"

    def __init__(self, backend: SearchBackend) -> None:
        self.backend = backend

    def handle(self, method: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        params = params or {}
        if method == "initialize":
            return {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": "mcp-paper-agent-http-search",
                    "version": __version__,
                },
            }
        if method == "tools/list":
            return {"tools": [self._tool_definition()]}
        if method == "tools/call":
            return self._call_tool(params)
        raise MCPServerError(f"不支持的方法: {method}", code=-32601)

    def _tool_definition(self) -> dict[str, Any]:
        return {
            "name": self.TOOL_NAME,
            "description": "联网搜索网页结果，返回标题、URL、摘要等信息",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索查询词"},
                    "max_results": {
                        "type": "integer",
                        "description": "最大返回结果数",
                        "default": 10,
                    },
                },
                "required": ["query"],
            },
        }

    def _call_tool(self, params: dict[str, Any]) -> dict[str, Any]:
        tool_name = params.get("name")
        if tool_name != self.TOOL_NAME:
            raise MCPServerError(f"未知工具: {tool_name}", code=-32602)

        arguments = params.get("arguments", {})
        query = str(arguments.get("query", "")).strip()
        if not query:
            raise MCPServerError("query 不能为空", code=-32602)

        max_results = int(arguments.get("max_results", 10))
        items = self.backend.search(query=query, max_results=max_results)
        payload = {
            "query": query,
            "results": [self._serialize_item(item) for item in items],
            "count": len(items),
        }
        return {
            "content": [
                {"type": "json", "json": payload},
                {"type": "text", "text": json.dumps(payload, ensure_ascii=False)},
            ],
            "isError": False,
        }

    @staticmethod
    def _serialize_item(item: SearchItem) -> dict[str, Any]:
        return asdict(item)


class MCPHTTPRequestHandler(BaseHTTPRequestHandler):
    """处理 HTTP MCP 请求。"""

    service: SearchMCPService

    server_version = "MCPPaperHTTP/0.1"

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._send_json(HTTPStatus.OK, {"status": "ok"})
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        try:
            raw_length = self.headers.get("Content-Length", "0")
            content_length = int(raw_length)
            payload = self.rfile.read(content_length)
            request = json.loads(payload.decode("utf-8"))

            response = self._handle_jsonrpc(request)
            self._send_json(HTTPStatus.OK, response)
        except MCPServerError as exc:
            self._send_json(
                HTTPStatus.OK,
                {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": exc.code, "message": str(exc)},
                },
            )
        except Exception as exc:  # pragma: no cover - HTTP 层兜底
            logger.error(f"HTTP MCP 请求处理失败: {exc}")
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32603, "message": str(exc)},
                },
            )

    def log_message(self, format: str, *args: Any) -> None:
        logger.debug(format % args)

    def _handle_jsonrpc(self, request: dict[str, Any]) -> dict[str, Any]:
        if request.get("jsonrpc") != "2.0":
            raise MCPServerError("仅支持 JSON-RPC 2.0", code=-32600)

        method = str(request.get("method", "")).strip()
        if not method:
            raise MCPServerError("method 不能为空", code=-32600)

        params = request.get("params", {})
        result = self.service.handle(method=method, params=params)
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "result": result,
        }

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def create_server(
    host: str,
    port: int,
    backend: SearchBackend,
) -> ThreadingHTTPServer:
    """创建 HTTP MCP 服务。"""

    handler_cls = type(
        "BoundMCPHTTPRequestHandler",
        (MCPHTTPRequestHandler,),
        {"service": SearchMCPService(backend)},
    )
    return ThreadingHTTPServer((host, port), handler_cls)


@click.command()
@click.option("--host", default="127.0.0.1", show_default=True, help="监听地址")
@click.option("--port", default=8000, show_default=True, type=int, help="监听端口")
@click.option("--tavily-api-key", default="", help="可选 Tavily API Key")
@click.option("--timeout", default=20.0, show_default=True, type=float, help="搜索超时时间")
def main(host: str, port: int, tavily_api_key: str, timeout: float) -> None:
    """启动一个最小可用的 HTTP MCP 搜索服务。"""
    backend = build_default_backend(tavily_api_key=tavily_api_key, timeout=timeout)
    server = create_server(host=host, port=port, backend=backend)
    logger.info(f"HTTP MCP 搜索服务启动于 http://{host}:{port}")
    logger.info("健康检查: GET /health")
    logger.info("MCP 入口: POST /")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("收到中断信号，HTTP MCP 搜索服务正在关闭")
    finally:
        server.server_close()
