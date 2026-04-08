"""MCP 搜索工具封装。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from mcp_paper_agent.mcp.client import MCPClient


@dataclass
class SearchResult:
    """单条搜索结果。"""

    title: str
    url: str
    content: str = ""
    snippet: str = ""
    score: float = 0.0


@dataclass
class SearchResults:
    """搜索结果集合。"""

    query: str
    results: list[SearchResult] = field(default_factory=list)
    total_results: int = 0

    @property
    def count(self) -> int:
        return len(self.results)


class WebSearchTool:
    """网页搜索工具。"""

    @classmethod
    async def execute(
        cls,
        client: MCPClient,
        query: str,
        max_results: int = 10,
        tool_name: str = "web_search",
    ) -> SearchResults:
        tool_result = await client.call_tool(
            tool_name,
            {"query": query, "max_results": max_results},
        )
        results = cls._parse_tool_result(tool_result.content)
        return SearchResults(
            query=query,
            results=results[:max_results],
            total_results=len(results),
        )

    @classmethod
    def _parse_tool_result(cls, content: list[dict[str, Any]]) -> list[SearchResult]:
        parsed: list[SearchResult] = []

        for item in content:
            item_type = item.get("type")
            if item_type == "json":
                parsed.extend(cls._extract_from_payload(item.get("json")))
            elif item_type == "text":
                text = item.get("text", "").strip()
                if not text:
                    continue
                try:
                    payload = json.loads(text)
                except json.JSONDecodeError:
                    parsed.append(
                        SearchResult(
                            title=text.splitlines()[0][:120] or "搜索结果",
                            url="",
                            content=text,
                            snippet=text[:300],
                        )
                    )
                else:
                    parsed.extend(cls._extract_from_payload(payload))

        return parsed

    @classmethod
    def _extract_from_payload(cls, payload: Any) -> list[SearchResult]:
        if payload is None:
            return []
        if isinstance(payload, list):
            results: list[SearchResult] = []
            for item in payload:
                results.extend(cls._extract_from_payload(item))
            return results
        if isinstance(payload, dict):
            if cls._looks_like_result(payload):
                return [cls._coerce_result(payload)]

            for key in ("results", "items", "data", "documents"):
                value = payload.get(key)
                if value is not None:
                    return cls._extract_from_payload(value)
        if isinstance(payload, str):
            return [
                SearchResult(
                    title=payload.splitlines()[0][:120] or "搜索结果",
                    url="",
                    content=payload,
                    snippet=payload[:300],
                )
            ]
        return []

    @staticmethod
    def _looks_like_result(payload: dict[str, Any]) -> bool:
        return any(key in payload for key in ("url", "link", "href")) or (
            "title" in payload and any(key in payload for key in ("snippet", "content", "body", "description"))
        )

    @staticmethod
    def _coerce_result(payload: dict[str, Any]) -> SearchResult:
        title = str(payload.get("title") or payload.get("name") or "搜索结果").strip()
        url = str(payload.get("url") or payload.get("link") or payload.get("href") or "").strip()
        content = str(
            payload.get("content")
            or payload.get("body")
            or payload.get("text")
            or payload.get("description")
            or payload.get("snippet")
            or ""
        ).strip()
        snippet = str(payload.get("snippet") or payload.get("description") or content[:300]).strip()
        score_raw = payload.get("score")
        try:
            score = float(score_raw) if score_raw is not None else 0.0
        except (TypeError, ValueError):
            score = 0.0
        return SearchResult(
            title=title,
            url=url,
            content=content,
            snippet=snippet,
            score=score,
        )
