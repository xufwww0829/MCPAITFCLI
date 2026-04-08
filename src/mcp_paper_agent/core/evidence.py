"""结构化证据抽取。"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable, List


@dataclass
class EvidenceClaim:
    """可直接用于写作和校验的证据条目。"""

    claim: str
    source_id: int
    source_title: str
    source_url: str
    evidence_text: str
    source_type: str
    keywords: List[str] = field(default_factory=list)


@dataclass
class EvidenceCoverageResult:
    """证据覆盖检查结果。"""

    is_sufficient: bool
    type_counts: dict[str, int] = field(default_factory=dict)
    missing_types: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


class EvidenceExtractor:
    """从搜索结果中提取可追溯证据。"""

    SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[。！？.!?；;])\s+")
    KEYWORD_PATTERN = re.compile(r"[\u4e00-\u9fffA-Za-z0-9]{2,}")

    SOURCE_TYPE_RULES = {
        "regulation": ("标准", "法规", "政策", "law", "regulation", "legal", "samr", "gov"),
        "report": ("报告", "report", "白皮书", "pdf", "研究"),
        "company": ("xiaomi", "waymo", "tesla", "奥迪", "小米", "小鹏", "比亚迪", "蔚来", "理想"),
        "news": ("news", "新闻网", "快讯", "观察", "ofweek", "36kr"),
    }
    SOURCE_TYPE_QUOTAS = {
        "regulation": 1,
        "report": 1,
        "company": 2,
    }
    GENERAL_SOURCE_LIMIT = 0.5

    def extract(self, results: Iterable[object]) -> list[EvidenceClaim]:
        """从检索结果列表中抽取证据。"""
        claims: list[EvidenceClaim] = []
        for index, result in enumerate(results, start=1):
            title = str(getattr(result, "title", "")).strip()
            url = str(getattr(result, "url", "")).strip()
            content = str(getattr(result, "content", "")).strip()
            if not title or not url:
                continue

            source_type = self._infer_source_type(title, url)
            sentences = self._pick_sentences(content or title)
            if not sentences:
                sentences = [title]

            for sentence in sentences[:3]:
                claim = sentence.strip()
                if len(claim) < 12:
                    continue
                claims.append(
                    EvidenceClaim(
                        claim=claim,
                        source_id=index,
                        source_title=title,
                        source_url=url,
                        evidence_text=sentence.strip(),
                        source_type=source_type,
                        keywords=self._extract_keywords(f"{title} {sentence}"),
                    )
                )

        return self._deduplicate(claims)

    def build_claim_context(self, claims: list[EvidenceClaim], max_items: int = 30) -> str:
        """构建给生成器使用的证据上下文。"""
        lines = []
        for claim in claims[:max_items]:
            lines.append(
                f"[{claim.source_id}] 类型: {claim.source_type}\n"
                f"来源标题: {claim.source_title}\n"
                f"来源链接: {claim.source_url}\n"
                f"可用事实: {claim.claim}\n"
            )
        return "\n".join(lines)

    def check_coverage(self, claims: list[EvidenceClaim]) -> EvidenceCoverageResult:
        """检查证据池是否满足综述写作的来源覆盖要求。"""
        counts = Counter(claim.source_type for claim in claims)
        missing_types: list[str] = []
        suggestions: list[str] = []

        for source_type, minimum in self.SOURCE_TYPE_QUOTAS.items():
            actual = counts.get(source_type, 0)
            if actual < minimum:
                missing_types.append(source_type)
                suggestions.append(
                    f"缺少 {source_type} 类型证据，当前 {actual}/{minimum}"
                )

        total = sum(counts.values())
        general_share = counts.get("general", 0) / total if total else 0.0
        if general_share > self.GENERAL_SOURCE_LIMIT:
            missing_types.append("high_quality_sources")
            suggestions.append(
                f"通用/弱来源占比过高 ({general_share:.0%})，需要补充标准、报告或官方案例来源"
            )

        return EvidenceCoverageResult(
            is_sufficient=not missing_types,
            type_counts=dict(counts),
            missing_types=missing_types,
            suggestions=suggestions,
        )

    def _pick_sentences(self, text: str) -> list[str]:
        cleaned = re.sub(r"\s+", " ", text).strip()
        parts = self.SENTENCE_SPLIT_PATTERN.split(cleaned)
        sentences = [part.strip(" -") for part in parts if len(part.strip()) >= 12]
        if not sentences and cleaned:
            sentences = [cleaned[:240]]
        return sentences

    def _infer_source_type(self, title: str, url: str) -> str:
        haystack = f"{title} {url}".lower()
        for source_type, keywords in self.SOURCE_TYPE_RULES.items():
            if any(keyword.lower() in haystack for keyword in keywords):
                return source_type
        return "general"

    def _extract_keywords(self, text: str) -> list[str]:
        seen: set[str] = set()
        keywords: list[str] = []
        for token in self.KEYWORD_PATTERN.findall(text):
            normalized = token.lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            keywords.append(token)
        return keywords[:12]

    def _deduplicate(self, claims: list[EvidenceClaim]) -> list[EvidenceClaim]:
        seen: set[tuple[int, str]] = set()
        deduped: list[EvidenceClaim] = []
        for claim in claims:
            key = (claim.source_id, claim.claim)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(claim)
        return deduped
