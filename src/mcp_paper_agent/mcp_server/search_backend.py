"""搜索后端实现。"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import quote_plus, urlparse

import httpx

try:
    from tavily import TavilyClient
except Exception:  # pragma: no cover - 依赖缺失时运行时降级
    TavilyClient = None  # type: ignore[assignment]


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
BLOCKED_FETCH_DOMAINS = {
    "baike.baidu.com",
    "zh.wikipedia.org",
    "wikipedia.org",
    "zhihu.com",
    "www.zhihu.com",
    "zhuanlan.zhihu.com",
    "researchgate.net",
    "www.researchgate.net",
    "gartner.com",
    "www.gartner.com",
    "cloudflare.com",
    "www.cloudflare.com",
    "reddit.com",
    "www.reddit.com",
    "youtube.com",
    "www.youtube.com",
}


@dataclass
class SearchItem:
    title: str
    url: str
    snippet: str
    content: str = ""
    score: float = 0.0
    source_type: str = "general"


@dataclass
class FetchItem:
    url: str
    title: str
    content: str
    snippet: str = ""
    source_type: str = "general"


class SearchBackend(Protocol):
    def search(self, query: str, max_results: int = 10) -> list[SearchItem]:
        """执行搜索。"""

    def fetch_url(self, url: str, max_chars: int = 6000) -> FetchItem:
        """抓取网页正文。"""


def get_domain(url: str) -> str:
    return urlparse(url).netloc.lower()


def should_skip_fetch(url: str) -> bool:
    domain = get_domain(url)
    return any(domain == blocked or domain.endswith(f".{blocked}") for blocked in BLOCKED_FETCH_DOMAINS)


def infer_source_type(title: str, url: str) -> str:
    haystack = f"{title} {url}".lower()
    if any(token in haystack for token in ("gov", "政策", "法规", "标准", "law", "regulation")):
        return "regulation"
    if any(token in haystack for token in ("pdf", "report", "报告", "白皮书", "研究")):
        return "report"
    if any(token in haystack for token in ("microsoft", "openai", "google", "aws", "ibm", "huawei", "xiaomi", "tesla", "waymo", "baidu")):
        return "company"
    if any(token in haystack for token in ("edu", "ac.", "大学", "研究院", "research")):
        return "research"
    if any(token in haystack for token in ("zhihu", "csdn", "reddit", "youtube", "blog")):
        return "community"
    if any(token in haystack for token in ("news", "观察", "36kr", "快讯")):
        return "news"
    return "general"


def score_source_quality(title: str, url: str, base_score: float = 0.5) -> float:
    source_type = infer_source_type(title, url)
    bonuses = {
        "regulation": 0.35,
        "report": 0.3,
        "research": 0.25,
        "company": 0.2,
        "news": 0.05,
        "general": 0.0,
        "community": -0.2,
    }
    score = base_score + bonuses.get(source_type, 0.0)
    return max(0.0, min(1.0, score))


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
                    score=score_source_quality(
                        str(item.get("title", "")).strip(),
                        str(item.get("url", "")).strip(),
                        base_score=max(0.0, 1.0 - index * 0.05),
                    ),
                    source_type=infer_source_type(
                        str(item.get("title", "")).strip(),
                        str(item.get("url", "")).strip(),
                    ),
                )
            )
        return items

    def fetch_url(self, url: str, max_chars: int = 6000) -> FetchItem:
        return _fetch_page(url, timeout=20.0, max_chars=max_chars)


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
                    score=score_source_quality(
                        title or "未命名结果",
                        raw_url,
                        base_score=max(0.0, 1.0 - index * 0.05),
                    ),
                    source_type=infer_source_type(title or "未命名结果", raw_url),
                )
            )
            if len(items) >= max_results:
                break

        return items

    @staticmethod
    def _strip_html(value: str) -> str:
        text = re.sub(r"<.*?>", "", value)
        return html.unescape(text).strip()

    def fetch_url(self, url: str, max_chars: int = 6000) -> FetchItem:
        return _fetch_page(url, timeout=self.timeout, max_chars=max_chars)


def _fetch_page(url: str, timeout: float, max_chars: int = 6000) -> FetchItem:
    if should_skip_fetch(url):
        raise ValueError(f"skip fetch for blocked domain: {get_domain(url)}")

    with httpx.Client(
        timeout=timeout,
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
    ) as client:
        response = client.get(url)
        response.raise_for_status()

    content_type = response.headers.get("Content-Type", "").lower()
    text = response.text
    if "html" in content_type or "<html" in text.lower():
        title_match = re.search(r"<title[^>]*>(.*?)</title>", text, re.IGNORECASE | re.DOTALL)
        title = html.unescape(re.sub(r"\s+", " ", title_match.group(1))).strip() if title_match else url
        body = re.sub(r"(?is)<script.*?>.*?</script>|<style.*?>.*?</style>", " ", text)
        body = re.sub(r"(?is)<[^>]+>", " ", body)
        body = html.unescape(re.sub(r"\s+", " ", body)).strip()
    else:
        title = url
        body = re.sub(r"\s+", " ", text).strip()

    snippet = body[:300]
    content = body[:max_chars]
    source_type = infer_source_type(title, url)
    return FetchItem(
        url=url,
        title=title,
        content=content,
        snippet=snippet,
        source_type=source_type,
    )


def build_default_backend(
    tavily_api_key: str = "",
    timeout: float = 20.0,
) -> SearchBackend:
    """根据配置自动选择搜索后端。"""
    if tavily_api_key:
        return TavilySearchBackend(tavily_api_key)
    return DuckDuckGoSearchBackend(timeout=timeout)
