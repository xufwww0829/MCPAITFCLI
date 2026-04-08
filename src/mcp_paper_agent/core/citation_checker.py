"""引用一致性检查。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List

from mcp_paper_agent.core.evidence import EvidenceClaim


@dataclass
class CitationIssue:
    """句级引用问题。"""

    issue_type: str
    sentence: str
    citation_ids: List[int] = field(default_factory=list)
    message: str = ""


@dataclass
class CitationCheckResult:
    """引用一致性检查结果。"""

    score: float
    issues: List[CitationIssue] = field(default_factory=list)
    citation_distribution: dict[int, int] = field(default_factory=dict)


class CitationChecker:
    """基于规则的引用一致性检查。"""

    COMPANY_PATTERN = re.compile(
        r"(小米|小鹏|比亚迪|奥迪|Waymo|Tesla|特斯拉|蔚来|理想|ARCFOX|极狐)",
        re.IGNORECASE,
    )
    DATA_PATTERN = re.compile(r"(\d+[%万亿元公里个项级L]\S*)")
    SENTENCE_PATTERN = re.compile(r"[^。！？!?]+[。！？!?]?")
    MAX_SINGLE_SOURCE_SHARE = 0.6
    MIN_DISTRIBUTION_SAMPLE = 4

    def __init__(self, claims: list[EvidenceClaim]):
        self.claims = claims
        self.claims_by_source: dict[int, list[EvidenceClaim]] = {}
        for claim in claims:
            self.claims_by_source.setdefault(claim.source_id, []).append(claim)

    def check(self, paper: str) -> CitationCheckResult:
        issues: list[CitationIssue] = []
        body = paper.split("## 参考文献")[0]
        sentences = [s.strip() for s in self.SENTENCE_PATTERN.findall(body) if s.strip()]
        citation_distribution: dict[int, int] = {}

        for sentence in sentences:
            citation_ids = [int(num) for num in re.findall(r"\[(\d+)\]", sentence)]
            if not citation_ids:
                continue
            for citation_id in citation_ids:
                citation_distribution[citation_id] = citation_distribution.get(citation_id, 0) + 1
            issues.extend(self._check_sentence(sentence, citation_ids))

        issues.extend(self._check_distribution(citation_distribution))

        penalty = min(len(issues) * 1.5, 10)
        return CitationCheckResult(
            score=max(0.0, round(10 - penalty, 2)),
            issues=issues,
            citation_distribution=citation_distribution,
        )

    def _check_sentence(self, sentence: str, citation_ids: list[int]) -> list[CitationIssue]:
        issues: list[CitationIssue] = []
        cited_claims = [claim for cid in citation_ids for claim in self.claims_by_source.get(cid, [])]
        cited_text = " ".join(
            f"{claim.source_title} {claim.claim} {' '.join(claim.keywords)}"
            for claim in cited_claims
        ).lower()
        stripped = re.sub(r"\[\d+\]", "", sentence)

        company_mentions = self.COMPANY_PATTERN.findall(stripped)
        for company in company_mentions:
            if company.lower() not in cited_text:
                issues.append(
                    CitationIssue(
                        issue_type="company_mismatch",
                        sentence=sentence,
                        citation_ids=citation_ids,
                        message=f"句子提到“{company}”，但引用来源中未发现同名实体。",
                    )
                )

        data_mentions = self.DATA_PATTERN.findall(stripped)
        if data_mentions:
            report_like = any(
                claim.source_type in {"report", "news", "company", "general"}
                for claim in cited_claims
            )
            if not report_like:
                issues.append(
                    CitationIssue(
                        issue_type="data_source_mismatch",
                        sentence=sentence,
                        citation_ids=citation_ids,
                        message="句子包含具体数据，但引用来源更像法规/标准，支撑力度不足。",
                    )
                )

        if company_mentions and cited_claims:
            if all(claim.source_type == "regulation" for claim in cited_claims):
                issues.append(
                    CitationIssue(
                        issue_type="regulation_used_for_company_fact",
                        sentence=sentence,
                        citation_ids=citation_ids,
                        message="企业或产品事实被法规/标准类来源支撑，存在错配风险。",
                    )
                )

        return issues

    def _check_distribution(self, citation_distribution: dict[int, int]) -> list[CitationIssue]:
        if not citation_distribution:
            return []

        total = sum(citation_distribution.values())
        if total < self.MIN_DISTRIBUTION_SAMPLE:
            return []
        dominant_id, dominant_count = max(citation_distribution.items(), key=lambda item: item[1])
        share = dominant_count / total if total else 0.0
        if share <= self.MAX_SINGLE_SOURCE_SHARE:
            return []

        return [
            CitationIssue(
                issue_type="source_overconcentration",
                sentence="全文引用分布",
                citation_ids=[dominant_id],
                message=f"来源 [{dominant_id}] 占全文引用的 {share:.0%}，来源过于集中。",
            )
        ]
