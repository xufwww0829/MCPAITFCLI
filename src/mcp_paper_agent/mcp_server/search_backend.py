"""搜索后端实现。"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import quote_plus

import httpx

try:
    from tavily import TavilyClient
except Exception:  # pragma: no cover - 依赖缺失时运行时降级
    TavilyClient = None  # type: ignore[assignment]


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


@dataclass
class SearchItem:
    title: str
    url: str
    snippet: str
    content: str = ""
    score: float = 0.0


class SearchBackend(Protocol):
    def search(self, query: str, max_results: int = 10) -> list[SearchItem]:
        """执行搜索。"""


class TavilySearchBackend:
    """使用 Tavily API 的搜索后端。"""

    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ValueError("Tavily API key 不能为空")
        if TavilyClient is None:
            raise RuntimeError("tavily-python 未安装或不可用")
        self.client = TavilyClient(api_key=api_key)

    def search(self, query: str, max_results: int = 10) -> list[SearchItem]:
        response = self.client.search(
            query=query,
            max_results=max_results,
            include_raw_content=True,
        )
        results = response.get("results", [])
        items: list[SearchItem] = []
        for index, item in enumerate(results, start=1):
            items.append(
                SearchItem(
                    title=str(item.get("title", "")).strip() or "未命名结果",
                    url=str(item.get("url", "")).strip(),
                    snippet=str(item.get("content", "")).strip(),
                    content=str(item.get("raw_content", "") or item.get("content", "")).strip(),
                    score=max(0.0, 1.0 - index * 0.05),
                )
            )
        return items


class DuckDuckGoSearchBackend:
    """基于 DuckDuckGo HTML 页面的轻量搜索后端。"""

    RESULT_PATTERN = re.compile(
        r'<a[^>]*class="result__a"[^>]*href="(?P<url>[^"]+)"[^>]*>(?P<title>.*?)</a>.*?'
        r'<a[^>]*class="result__snippet"[^>]*>(?P<snippet>.*?)</a>',
        re.DOTALL,
    )

    def __init__(self, timeout: float = 20.0) -> None:
        self.timeout = timeout

    def search(self, query: str, max_results: int = 10) -> list[SearchItem]:
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        with httpx.Client(
            timeout=self.timeout,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        ) as client:
            response = client.get(url)
            response.raise_for_status()

        items: list[SearchItem] = []
        for index, match in enumerate(self.RESULT_PATTERN.finditer(response.text), start=1):
            raw_url = html.unescape(match.group("url")).strip()
            title = self._strip_html(match.group("title"))
            snippet = self._strip_html(match.group("snippet"))
            if not raw_url.startswith(("http://", "https://")):
                continue
            items.append(
                SearchItem(
                    title=title or "未命名结果",
                    url=raw_url,
                    snippet=snippet,
                    content=snippet,
                    score=max(0.0, 1.0 - index * 0.05),
                )
            )
            if len(items) >= max_results:
                break

        return items

    @staticmethod
    def _strip_html(value: str) -> str:
        text = re.sub(r"<.*?>", "", value)
        return html.unescape(text).strip()


def build_default_backend(
    tavily_api_key: str = "",
    timeout: float = 20.0,
) -> SearchBackend:
    """根据配置自动选择搜索后端。"""
    if tavily_api_key:
        return TavilySearchBackend(tavily_api_key)
    return DuckDuckGoSearchBackend(timeout=timeout)
