"""反思智能体 - 负责质量评估和问题定位

评估论文质量，整合格式审查模块，生成结构化评估报告。
评估维度：内容准确性、结构逻辑、引用恰当性、字数符合度、语言表达、格式规范性。
"""

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from openai import OpenAI

from mcp_paper_agent.config import settings
from mcp_paper_agent.core.citation_checker import CitationChecker
from mcp_paper_agent.core.evidence import EvidenceExtractor
from mcp_paper_agent.core.format_checker import FormatChecker
from mcp_paper_agent.logger import get_logger

logger = get_logger()


@dataclass
class ContentIssue:
    """内容问题"""
    type: str
    location: str
    text_snippet: str = ""
    suggestion: str = ""


@dataclass
class AssessmentReport:
    """评估报告"""
    scores: Dict[str, float] = field(default_factory=dict)
    overall_score: float = 0.0
    word_count: int = 0
    target_word_count: int = 1900
    format_issues: List[str] = field(default_factory=list)
    content_issues: List[ContentIssue] = field(default_factory=list)
    should_continue: bool = True
    supplementary_search_needed: bool = False
    suggested_search_queries: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "scores": self.scores,
            "overall_score": self.overall_score,
            "word_count": self.word_count,
            "target_word_count": self.target_word_count,
            "format_issues": self.format_issues,
            "content_issues": [
                {
                    "type": issue.type,
                    "location": issue.location,
                    "text_snippet": issue.text_snippet,
                    "suggestion": issue.suggestion,
                }
                for issue in self.content_issues
            ],
            "should_continue": self.should_continue,
            "supplementary_search_needed": self.supplementary_search_needed,
            "suggested_search_queries": self.suggested_search_queries,
        }


class Reflector:
    """反思智能体

    负责论文质量评估，整合格式审查和内容评估。

    Attributes:
        client: OpenAI 客户端
        model: 使用的模型名称
        format_checker: 格式审查器
    """

    SYSTEM_PROMPT = """你是一位严格的学术论文审稿人。请评估以下论文的内容质量（不包括格式，因为格式已由自动化工具检查）。

请评估以下五个维度（每项0-10分）：
1. 内容准确性（25%）：是否基于搜索资料，有无明显事实错误。
2. 结构逻辑（20%）：章节连贯性、论证层次、过渡自然。
3. 引用内容恰当性（10%）：引用是否真正支持论点，而非随意堆砌。
4. 语言表达（10%）：语法、用词、学术风格。
5. 字数符合度（15%）：根据当前字数与目标字数的偏差评分。

输出必须是有效的 JSON 格式，包含以下字段：
{
  "scores": {
    "accuracy": <0-10>,
    "structure_logic": <0-10>,
    "citation_content": <0-10>,
    "language": <0-10>,
    "word_count": <0-10>
  },
  "content_issues": [
    {
      "type": "missing_citation|fact_check|structural|language",
      "location": "问题位置描述",
      "text_snippet": "相关文本片段",
      "suggestion": "修改建议"
    }
  ],
  "supplementary_search_needed": <true|false>,
  "suggested_search_queries": ["查询1", "查询2"]
}

注意：只输出 JSON，不要输出其他内容。"""

    WEIGHTS = {
        "accuracy": 0.30,
        "structure_logic": 0.20,
        "citation_content": 0.10,
        "language": 0.10,
        "word_count": 0.15,
        "format": 0.15,
    }
    MAX_SUGGESTED_SEARCH_QUERIES = 2

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.3,
    ):
        """初始化反思智能体

        Args:
            api_key: OpenRouter API Key
            base_url: OpenRouter API 基础 URL
            model: 模型名称
            temperature: 生成温度（评估时建议较低值）
        """
        self.api_key = api_key or settings.openrouter.api_key
        self.base_url = base_url or settings.openrouter.base_url
        self.model = model or settings.openrouter.model
        self.temperature = temperature

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )
        self.evidence_extractor = EvidenceExtractor()

    def _count_words(self, text: str) -> int:
        """计算中文字数"""
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        english_words = len(re.findall(r'[a-zA-Z]+', text))
        return chinese_chars + english_words

    def _calculate_word_count_score(
        self, word_count: int, target: int, tolerance: int = 200
    ) -> float:
        """计算字数符合度分数

        Args:
            word_count: 实际字数
            target: 目标字数
            tolerance: 允许偏差

        Returns:
            分数 (0-10)
        """
        deviation = abs(word_count - target)
        if deviation <= tolerance:
            return 10.0
        elif deviation <= tolerance + 50:
            return 9.0
        elif deviation <= tolerance + 100:
            return 8.0
        elif deviation <= tolerance + 150:
            return 7.0
        elif deviation <= tolerance + 200:
            return 6.0
        else:
            return max(0, 10 - (deviation - tolerance) / 50)

    def _parse_llm_response(self, response_text: str) -> Dict[str, Any]:
        """解析 LLM 响应

        Args:
            response_text: LLM 返回的文本

        Returns:
            解析后的字典
        """
        try:
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            logger.warning("LLM 响应不是有效的 JSON 格式")

        return {
            "scores": {
                "accuracy": 5.0,
                "structure_logic": 5.0,
                "citation_content": 5.0,
                "language": 5.0,
                "word_count": 5.0,
            },
            "content_issues": [],
            "supplementary_search_needed": False,
            "suggested_search_queries": [],
        }

    def assess(
        self,
        paper: str,
        context: str,
        citations: List[str],
        target_word_count: Optional[int] = None,
    ) -> AssessmentReport:
        """评估论文

        Args:
            paper: 论文文本
            context: 参考资料
            citations: 引用列表
            target_word_count: 目标字数

        Returns:
            AssessmentReport 评估报告
        """
        target = target_word_count or settings.paper.target_word_count
        word_count = self._count_words(paper)

        logger.agent("Reflector", "正在进行格式审查...")
        format_checker = FormatChecker(paper)
        format_result = format_checker.full_check(citations)
        citation_claims = self.evidence_extractor.extract(
            [
                type("EvidenceSource", (), {"title": citation, "url": citation.split()[-1], "content": context})()
                for citation in citations
                if citation
            ]
        )
        citation_check = CitationChecker(citation_claims).check(paper)

        logger.agent("Reflector", "正在进行内容评估...")
        user_prompt = f"""【论文主题】{settings.paper.target_word_count}字论文
【目标字数】{target}字（允许±200字）
【当前字数】{word_count}字
【参考资料（带引用编号）】
{context[:3000]}

【当前论文版本】
{paper}

【自动格式检查发现的问题】（仅供参考，你不需要再评估格式）
{chr(10).join(format_result.issues) if format_result.issues else '无格式问题'}

【自动引用一致性检查】
引用一致性得分: {citation_check.score}/10
{chr(10).join(f"- {issue.message} | 句子: {issue.sentence}" for issue in citation_check.issues[:8]) if citation_check.issues else '无明显引用错配'}

请评估论文质量并输出 JSON 格式的评估报告。"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=self.temperature,
            max_tokens=2048,
        )

        response_text = response.choices[0].message.content or ""
        parsed = self._parse_llm_response(response_text)

        scores = parsed.get("scores", {})
        scores["format"] = format_result.format_score
        scores["word_count"] = self._calculate_word_count_score(word_count, target)
        scores["citation_content"] = min(
            scores.get("citation_content", 5.0),
            citation_check.score,
        )

        overall_score = sum(
            scores.get(key, 0) * weight
            for key, weight in self.WEIGHTS.items()
        )

        content_issues = [
            ContentIssue(
                type=issue.get("type", "unknown"),
                location=issue.get("location", ""),
                text_snippet=issue.get("text_snippet", ""),
                suggestion=issue.get("suggestion", ""),
            )
            for issue in parsed.get("content_issues", [])
        ]
        content_issues.extend(
            ContentIssue(
                type=issue.issue_type,
                location="引用一致性检查",
                text_snippet=issue.sentence,
                suggestion=issue.message,
            )
            for issue in citation_check.issues[:8]
        )

        should_continue = overall_score < settings.paper.min_quality_score

        report = AssessmentReport(
            scores=scores,
            overall_score=round(overall_score, 2),
            word_count=word_count,
            target_word_count=target,
            format_issues=format_result.issues,
            content_issues=content_issues,
            should_continue=should_continue,
            supplementary_search_needed=parsed.get("supplementary_search_needed", False),
            suggested_search_queries=parsed.get("suggested_search_queries", [])[: self.MAX_SUGGESTED_SEARCH_QUERIES],
        )

        logger.success(f"评估完成，综合分数: {report.overall_score}")
        return report
