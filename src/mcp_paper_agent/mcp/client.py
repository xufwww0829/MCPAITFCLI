"""MCP 协议客户端。"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

from mcp_paper_agent.config import MCPConfig
from mcp_paper_agent.logger import get_logger

logger = get_logger()


class MCPError(Exception):
    """MCP 基础错误类。"""

    def __init__(
        self,
        message: str,
        code: Optional[int] = None,
        data: Any = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.data = data


class MCPConnectionError(MCPError):
    """连接错误。"""


class MCPTimeoutError(MCPError):
    """超时错误。"""


class MCPProtocolError(MCPError):
    """协议错误。"""


class MCPToolError(MCPError):
    """工具调用错误。"""


@dataclass
class MCPTool:
    """MCP 工具定义。"""

    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)


@dataclass
class MCPToolResult:
    """工具调用结果。"""

    content: list[dict[str, Any]] = field(default_factory=list)
    is_error: bool = False


class _BaseTransport:
    async def send(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    async def close(self) -> None:
        return None


class _HTTPTransport(_BaseTransport):
    def __init__(
        self,
        server_url: str,
        timeout: float,
        headers: Optional[dict[str, str]] = None,
    ) -> None:
        self.server_url = server_url.rstrip("/")
        self.timeout = timeout
        self.headers = headers or {}
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    **self.headers,
                },
            )
        return self._client

    async def send(self, payload: dict[str, Any]) -> dict[str, Any]:
        client = await self._get_client()
        response = await client.post(f"{self.server_url}/", json=payload)
        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
        self._client = None


class _StdioTransport(_BaseTransport):
    def __init__(self, command: str, args: list[str], timeout: float) -> None:
        self.command = command
        self.args = args
        self.timeout = timeout
        self._process: Optional[asyncio.subprocess.Process] = None

    async def _ensure_process(self) -> asyncio.subprocess.Process:
        if self._process is None or self._process.returncode is not None:
            self._process = await asyncio.create_subprocess_exec(
                self.command,
                *self.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        return self._process

    async def _read_message(self, stream: asyncio.StreamReader) -> bytes:
        headers: dict[str, str] = {}
        while True:
            line = await asyncio.wait_for(stream.readline(), timeout=self.timeout)
            if not line:
                raise MCPConnectionError("MCP stdio 连接已关闭")
            if line in (b"\r\n", b"\n"):
                break
            name, _, value = line.decode("utf-8").partition(":")
            headers[name.strip().lower()] = value.strip()

        content_length = int(headers.get("content-length", "0"))
        if content_length <= 0:
            raise MCPProtocolError("MCP stdio 响应缺少 Content-Length")
        return await asyncio.wait_for(stream.readexactly(content_length), timeout=self.timeout)

    async def send(self, payload: dict[str, Any]) -> dict[str, Any]:
        process = await self._ensure_process()
        if process.stdin is None or process.stdout is None:
            raise MCPConnectionError("MCP stdio 通道不可用")

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("utf-8")
        process.stdin.write(header + body)
        await asyncio.wait_for(process.stdin.drain(), timeout=self.timeout)

        raw_response = await self._read_message(process.stdout)
        return json.loads(raw_response.decode("utf-8"))

    async def close(self) -> None:
        if self._process is not None and self._process.returncode is None:
            self._process.terminate()
            await self._process.wait()
        self._process = None


class MCPClient:
    """支持 HTTP 和 stdio 两种传输的 MCP 客户端。"""

    def __init__(
        self,
        transport: str = "stdio",
        server_url: str = "",
        server_command: str = "",
        server_args: Optional[list[str]] = None,
        timeout: float = 30.0,
        headers: Optional[dict[str, str]] = None,
    ) -> None:
        self.transport = transport.lower()
        self.server_url = server_url.rstrip("/")
        self.server_command = server_command
        self.server_args = server_args or []
        self.timeout = timeout
        self.headers = headers or {}
        self._initialized = False
        self._tools_cache: Optional[list[MCPTool]] = None
        self.max_retries = 3
        self.retry_backoff = 0.5

        if self.transport == "http":
            if not self.server_url:
                raise MCPConnectionError("HTTP 模式需要 MCP_SERVER_URL")
            self._transport: _BaseTransport = _HTTPTransport(
                server_url=self.server_url,
                timeout=self.timeout,
                headers=self.headers,
            )
        elif self.transport == "stdio":
            if not self.server_command:
                raise MCPConnectionError("stdio 模式需要 MCP_SERVER_COMMAND")
            self._transport = _StdioTransport(
                command=self.server_command,
                args=self.server_args,
                timeout=self.timeout,
            )
        else:
            raise MCPConnectionError(f"不支持的 MCP 传输方式: {transport}")

    @classmethod
    def from_config(cls, config: MCPConfig) -> "MCPClient":
        headers: dict[str, str] = {}
        if config.api_key:
            headers["Authorization"] = f"Bearer {config.api_key}"
        return cls(
            transport=config.transport,
            server_url=config.server_url,
            server_command=config.server_command,
            server_args=config.server_args_list,
            timeout=config.timeout,
            headers=headers,
        )

    async def close(self) -> None:
        await self._transport.close()
        logger.info("MCP 客户端已关闭")

    async def _make_request(
        self,
        method: str,
        params: Optional[dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": request_id or str(uuid.uuid4()),
            "method": method,
        }
        if params:
            payload["params"] = params

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                result = await self._transport.send(payload)
                break
            except asyncio.TimeoutError as exc:
                last_error = MCPTimeoutError(f"请求超时: {exc}", code=-32000)
            except httpx.TimeoutException as exc:
                last_error = MCPTimeoutError(f"请求超时: {exc}", code=-32000)
            except httpx.ConnectError as exc:
                last_error = MCPConnectionError(f"连接失败: {exc}", code=-32300)
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                if status_code >= 500:
                    last_error = MCPError(
                        f"HTTP错误 {status_code}: {exc.response.text}",
                        code=status_code,
                    )
                else:
                    raise MCPError(
                        f"HTTP错误 {status_code}: {exc.response.text}",
                        code=status_code,
                    ) from exc

            assert last_error is not None
            if attempt >= self.max_retries:
                raise last_error
            logger.warning(f"MCP 请求失败，正在重试 ({attempt}/{self.max_retries}): {last_error}")
            await asyncio.sleep(self.retry_backoff * attempt)

        if "error" in result:
            error = result["error"]
            raise MCPProtocolError(
                error.get("message", "未知MCP错误"),
                code=error.get("code"),
                data=error.get("data"),
            )
        return result.get("result", {})

    async def initialize(self) -> bool:
        try:
            result = await self._make_request(
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "mcp-paper-agent",
                        "version": "0.1.0",
                    },
                },
            )
            self._initialized = True
            logger.success(f"MCP初始化成功: {result}")
            return True
        except Exception as exc:
            logger.error(f"MCP初始化失败: {exc}")
            self._initialized = False
            return False

    async def list_tools(self, force_refresh: bool = False) -> list[MCPTool]:
        if self._tools_cache and not force_refresh:
            return self._tools_cache

        result = await self._make_request("tools/list")
        tools_data = result.get("tools", [])
        self._tools_cache = [
            MCPTool(
                name=tool.get("name", ""),
                description=tool.get("description", ""),
                input_schema=tool.get("inputSchema", {}),
            )
            for tool in tools_data
        ]
        logger.info(f"获取到 {len(self._tools_cache)} 个MCP工具")
        return self._tools_cache

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> MCPToolResult:
        logger.info(f"调用MCP工具: {tool_name}, 参数: {list(arguments.keys())}")
        result = await self._make_request(
            "tools/call",
            {"name": tool_name, "arguments": arguments},
        )
        content = result.get("content", [])
        is_error = result.get("isError", False)
        if is_error:
            error_msg = "\n".join(
                item.get("text", "")
                for item in content
                if item.get("type") == "text"
            )
            raise MCPToolError(f"工具 {tool_name} 返回错误: {error_msg}", code=-32602)
        logger.success(f"工具 {tool_name} 调用成功")
        return MCPToolResult(content=content, is_error=is_error)

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    async def __aenter__(self) -> "MCPClient":
        await self.initialize()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        await self.close()
        return False
