"""MCP 客户端与工具封装。"""

from mcp_paper_agent.mcp.client import (
    MCPClient,
    MCPConnectionError,
    MCPError,
    MCPProtocolError,
    MCPTimeoutError,
    MCPTool,
    MCPToolError,
    MCPToolResult,
)
from mcp_paper_agent.mcp.tools import SearchResult, SearchResults, WebSearchTool

__all__ = [
    "MCPClient",
    "MCPConnectionError",
    "MCPError",
    "MCPProtocolError",
    "MCPTimeoutError",
    "MCPTool",
    "MCPToolError",
    "MCPToolResult",
    "SearchResult",
    "SearchResults",
    "WebSearchTool",
]
