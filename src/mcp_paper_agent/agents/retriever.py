"""检索智能体 - 负责联网搜索和引用收集

使用 OpenRouter 的 Perplexity 联网模型进行搜索，收集学术资料和引用信息。
支持缓存机制，避免重复搜索相同主题。
"""

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import List, Optional

from diskcache import Cache
from openai import OpenAI

from mcp_paper_agent.config import settings
from mcp_paper_agent.logger import get_logger

logger = get_logger()


@dataclass
class SearchResult:
    """单条搜索结果"""
    title: str
    url: str
    content: str
    score: float = 0.0


@dataclass
class RetrievalOutput:
    """检索智能体输出"""
    context: str
    citations: List[str] = field(default_factory=list)
    sources: List[SearchResult] = field(default_factory=list)


class Retriever:
    """检索智能体

    使用 OpenRouter 的 Perplexity 联网模型进行搜索。

    Attributes:
        client: OpenAI 客户端
        cache: 磁盘缓存实例
        search_model: 搜索用的联网模型
        max_results: 每次搜索返回的最大结果数
    """

    SEARCH_PROMPT = """请搜索关于以下主题的信息，并提供详细的搜索结果。

主题: {query}

请按以下格式返回搜索结果，每条结果包含：
1. 标题
2. 来源链接
3. 详细内容摘要

格式要求：
[1] 标题
来源: URL
内容: 详细摘要...

[2] 标题
来源: URL
内容: 详细摘要...

请提供 {max_results} 条最相关的搜索结果。"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        search_model: Optional[str] = None,
        cache_dir: Optional[Path] = None,
        cache_expire_days: int = 7,
        max_results: int = 10,
    ):
        """初始化检索智能体

        Args:
            api_key: OpenRouter API Key
            base_url: OpenRouter API 基础 URL
            search_model: 搜索用的联网模型
            cache_dir: 缓存目录
            cache_expire_days: 缓存过期天数
            max_results: 每次搜索返回的最大结果数
        """
        self.api_key = api_key or settings.openrouter.api_key
        self.base_url = base_url or settings.openrouter.base_url
        self.search_model = search_model or settings.openrouter.search_model
        self.max_results = max_results or settings.search.max_results

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )

        self.cache_dir = cache_dir or settings.cache.cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache = Cache(str(self.cache_dir / "search_cache"))
        self.cache_expire = timedelta(days=cache_expire_days)

    def _get_cache_key(self, query: str) -> str:
        """生成缓存键"""
        return hashlib.md5(f"search:{query}".encode()).hexdigest()

    def _parse_search_results(self, response_text: str) -> List[SearchResult]:
        """解析搜索结果

        Args:
            response_text: 模型返回的文本

        Returns:
            搜索结果列表
        """
        results = []

        blocks = re.split(r'\[(\d+)\]', response_text)

        for i in range(1, len(blocks), 2):
            if i + 1 >= len(blocks):
                break

            block = blocks[i + 1]
            title_match = re.search(r'^\s*(.+?)(?=\n|来源)', block, re.DOTALL)
            url_match = re.search(r'来源[:\s]*(https?://[^\s\n]+)', block)
            content_match = re.search(r'内容[:\s]*(.+?)(?=\n\[|\Z)', block, re.DOTALL)

            if title_match:
                title = title_match.group(1).strip()
                url = url_match.group(1).strip() if url_match else f"https://search.result/{i}"
                content = content_match.group(1).strip() if content_match else block.strip()

                results.append(
                    SearchResult(
                        title=title,
                        url=url,
                        content=content,
                        score=1.0 - (i * 0.1),
                    )
                )

        if not results:
            results.append(
                SearchResult(
                    title="搜索结果",
                    url="https://openrouter.ai",
                    content=response_text[:500],
                    score=1.0,
                )
            )

        return results[:self.max_results]

    def _format_citation(self, result: SearchResult, index: int) -> str:
        """格式化引用条目"""
        return f"[{index}] {result.title}. {result.url}"

    def _build_context(self, results: List[SearchResult]) -> str:
        """构建上下文文本"""
        context_parts = []
        for i, result in enumerate(results, 1):
            context_parts.append(f"[{i}] {result.title}\n{result.content}\n")
        return "\n".join(context_parts)

    def search(self, query: str, use_cache: bool = True) -> RetrievalOutput:
        """执行搜索

        Args:
            query: 搜索查询
            use_cache: 是否使用缓存

        Returns:
            RetrievalOutput 包含上下文、引用和来源
        """
        cache_key = self._get_cache_key(query)

        if use_cache and cache_key in self.cache:
            logger.info(f"从缓存加载搜索结果: {query}")
            cached = self.cache[cache_key]
            return RetrievalOutput(
                context=cached["context"],
                citations=cached["citations"],
                sources=[SearchResult(**s) for s in cached["sources"]],
            )

        logger.agent("Retriever", f"正在搜索: {query}")

        prompt = self.SEARCH_PROMPT.format(
            query=query,
            max_results=self.max_results,
        )

        response = self.client.chat.completions.create(
            model=self.search_model,
            messages=[
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=4096,
        )

        response_text = response.choices[0].message.content or ""
        results = self._parse_search_results(response_text)

        citations = [
            self._format_citation(r, i) for i, r in enumerate(results, 1)
        ]
        context = self._build_context(results)

        self.cache.set(
            cache_key,
            {
                "context": context,
                "citations": citations,
                "sources": [
                    {"title": s.title, "url": s.url, "content": s.content, "score": s.score}
                    for s in results
                ],
            },
            expire=self.cache_expire.total_seconds(),
        )

        logger.success(f"搜索完成，获取 {len(results)} 条结果")

        return RetrievalOutput(
            context=context,
            citations=citations,
            sources=results,
        )

    def supplementary_search(
        self, queries: List[str], existing_context: str = ""
    ) -> RetrievalOutput:
        """补充搜索

        Args:
            queries: 补充搜索查询列表
            existing_context: 已有的上下文文本

        Returns:
            合并后的 RetrievalOutput
        """
        all_results: List[SearchResult] = []
        all_citations: List[str] = []

        for query in queries:
            output = self.search(query)
            all_results.extend(output.sources)

        start_idx = 1
        if existing_context:
            existing_refs = existing_context.count("[")
            start_idx = existing_refs + 1

        for i, result in enumerate(all_results, start_idx):
            all_citations.append(self._format_citation(result, i))

        context = existing_context
        if context:
            context += "\n\n[补充资料]\n"
        context += self._build_context(all_results)

        return RetrievalOutput(
            context=context,
            citations=all_citations,
            sources=all_results,
        )

    def clear_cache(self) -> None:
        """清空搜索缓存"""
        self.cache.clear()
        logger.info("搜索缓存已清空")
