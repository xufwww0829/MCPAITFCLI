"""生成智能体 - 负责大纲生成和论文写作。"""

import json
import re
from dataclasses import dataclass, field
from typing import List, Optional

from openai import OpenAI

from mcp_paper_agent.config import settings
from mcp_paper_agent.core.evidence import EvidenceClaim, EvidenceExtractor
from mcp_paper_agent.logger import get_logger

logger = get_logger()


@dataclass
class GeneratorOutput:
    """生成智能体输出"""
    paper: str
    outline: Optional[str] = None
    word_count: int = 0


@dataclass
class OutlineSection:
    """结构化章节规划。"""

    heading: str
    purpose: str
    source_ids: List[int] = field(default_factory=list)


class Generator:
    """生成智能体

    负责论文大纲生成和正文写作。

    Attributes:
        client: OpenAI 客户端（兼容 OpenRouter）
        model: 使用的模型名称
        temperature: 生成温度
        max_tokens: 最大生成 token 数
    """

    OUTLINE_SYSTEM_PROMPT = """你是一位学术论文写作专家。请根据主题和结构化证据，为论文规划章节。

输出必须是 JSON 数组，每个元素包含：
{
  "heading": "章节标题",
  "purpose": "本节写作目的",
  "source_ids": [1, 2]
}

要求：
1. 章节顺序清晰，至少包括摘要、引言、正文若干节、结论
2. source_ids 只能使用证据中已经存在的编号
3. 企业案例、市场数据、法规标准尽量分开组织，不要混杂引用
4. 只输出 JSON，不要输出 Markdown 或解释"""

    SECTION_SYSTEM_PROMPT = """你是一位严谨的学术写作者。请只根据给定证据撰写当前章节。

写作要求：
1. 使用 Markdown 格式
2. 每个事实句都必须使用 [n] 标注引用，且 n 只能来自允许使用的 source_ids
3. 不得引入证据中不存在的企业、车型、市场数据、政策名称、技术参数
4. 不得把法规类来源用于支撑具体企业产品事实，除非证据本身明确提到该企业
5. 语言学术化、客观，避免口语化表达
6. 只输出当前章节内容，不输出解释"""
    MIN_SECTION_SOURCES = 2

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ):
        """初始化生成智能体

        Args:
            api_key: OpenRouter API Key
            base_url: OpenRouter API 基础 URL
            model: 模型名称
            temperature: 生成温度
            max_tokens: 最大生成 token 数
        """
        self.api_key = api_key or settings.openrouter.api_key
        self.base_url = base_url or settings.openrouter.base_url
        self.model = model or settings.openrouter.model
        self.temperature = temperature or settings.openrouter.temperature
        self.max_tokens = max_tokens or settings.openrouter.max_tokens

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=f"{self.base_url}",
        )
        self.evidence_extractor = EvidenceExtractor()

    def _count_words(self, text: str) -> int:
        """计算中文字数

        中文字符按 1 个字计算，英文单词按 1 个字计算。
        """
        import re
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        english_words = len(re.findall(r'[a-zA-Z]+', text))
        return chinese_chars + english_words

    def _parse_outline_sections(
        self,
        response_text: str,
        available_ids: list[int],
    ) -> list[OutlineSection]:
        try:
            json_match = re.search(r"\[[\s\S]*\]", response_text)
            payload = json.loads(json_match.group()) if json_match else json.loads(response_text)
        except Exception:
            return []

        sections: list[OutlineSection] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            source_ids = [
                int(source_id)
                for source_id in item.get("source_ids", [])
                if isinstance(source_id, int) and source_id in available_ids
            ]
            heading = str(item.get("heading", "")).strip()
            purpose = str(item.get("purpose", "")).strip()
            if not heading:
                continue
            sections.append(
                OutlineSection(
                    heading=heading,
                    purpose=purpose or "围绕已知证据展开分析",
                    source_ids=source_ids,
                )
            )
        return sections

    def _fallback_outline_sections(
        self,
        evidence_claims: list[EvidenceClaim],
    ) -> list[OutlineSection]:
        ids = sorted({claim.source_id for claim in evidence_claims}) or [1]
        regulation_ids = sorted({claim.source_id for claim in evidence_claims if claim.source_type == "regulation"})
        company_ids = sorted({claim.source_id for claim in evidence_claims if claim.source_type == "company"})
        report_ids = sorted({claim.source_id for claim in evidence_claims if claim.source_type in {"report", "news"}})

        return [
            OutlineSection("## 摘要", "概括研究主题、证据范围与结论。", ids[: min(4, len(ids))]),
            OutlineSection("## 引言", "介绍研究背景、研究意义与问题。", ids[: min(4, len(ids))]),
            OutlineSection("## 1. 概念界定与基础框架", "说明定义、分类、制度或技术框架。", regulation_ids or ids[: min(4, len(ids))]),
            OutlineSection("## 2. 核心技术与实现路径", "梳理核心技术、系统架构及实现条件。", ids[: min(6, len(ids))]),
            OutlineSection("## 3. 行业应用与发展趋势", "分析企业案例、市场应用和发展趋势。", company_ids or report_ids or ids[: min(6, len(ids))]),
            OutlineSection("## 结论", "总结主要发现、风险和未来方向。", ids[: min(4, len(ids))]),
        ]

    def generate_outline(
        self,
        topic: str,
        evidence_claims: list[EvidenceClaim],
        target_words: int = 1900,
    ) -> list[OutlineSection]:
        """生成结构化章节规划。"""
        logger.agent("Generator", "正在生成论文大纲...")
        available_ids = sorted({claim.source_id for claim in evidence_claims})
        evidence_context = self.evidence_extractor.build_claim_context(evidence_claims, max_items=24)

        user_prompt = f"""【论文主题】{topic}
【目标字数】{target_words}字
【结构化证据】
{evidence_context}

请规划一份严谨的章节结构。"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.OUTLINE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=min(self.temperature, 0.4),
                max_tokens=min(self.max_tokens, 2048),
            )
            response_text = response.choices[0].message.content or ""
            sections = self._parse_outline_sections(response_text, available_ids)
        except Exception:
            sections = []

        if not sections:
            sections = self._fallback_outline_sections(evidence_claims)

        logger.success("大纲生成完成")
        return sections

    def _build_section_evidence(
        self,
        evidence_claims: list[EvidenceClaim],
        source_ids: list[int],
    ) -> str:
        scoped_claims = [claim for claim in evidence_claims if claim.source_id in source_ids]
        if not scoped_claims:
            scoped_claims = evidence_claims[:8]
        return self.evidence_extractor.build_claim_context(scoped_claims, max_items=18)

    def _generate_section(
        self,
        topic: str,
        section: OutlineSection,
        evidence_claims: list[EvidenceClaim],
        target_words: int,
        existing_sections: list[str],
    ) -> str:
        evidence_context = self._build_section_evidence(evidence_claims, section.source_ids)
        section_word_target = max(120, target_words // max(len(existing_sections) + 1, 5))
        allowed_ids = section.source_ids or sorted({claim.source_id for claim in evidence_claims})

        user_prompt = f"""【论文主题】{topic}
【当前章节】{section.heading}
【章节目标】{section.purpose}
【当前章节目标字数】约{section_word_target}字
【已完成章节】
{chr(10).join(existing_sections) if existing_sections else '无'}

【允许使用的来源编号】
{allowed_ids}

【结构化证据】
{evidence_context}

请撰写当前章节。注意：
1. 只写当前章节
2. 每个事实句都必须带 [n] 引用
3. 引用编号只能从允许使用的来源编号中选择
4. 如果证据不足，不要编造，宁可保守表述"""

        for attempt in range(2):
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SECTION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=min(self.temperature, 0.5),
                max_tokens=min(self.max_tokens, 2500),
            )
            section_text = (response.choices[0].message.content or "").strip()
            if self._section_uses_enough_sources(section_text):
                return section_text

            user_prompt += "\n\n补充要求：当前章节至少显式使用 2 个不同的引用编号，不允许整节只使用单一来源。"

        return section_text or f"{section.heading}\n\n本节暂无足够证据支撑展开论述。"

    def _section_uses_enough_sources(self, section_text: str) -> bool:
        source_ids = set(re.findall(r"\[(\d+)\]", section_text))
        return len(source_ids) >= self.MIN_SECTION_SOURCES

    def generate_paper(
        self,
        topic: str,
        context: str,
        citations: List[str],
        evidence_claims: list[EvidenceClaim],
        outline: Optional[str] = None,
        target_words: int = 1900,
    ) -> GeneratorOutput:
        """生成论文正文

        Args:
            topic: 论文主题
            context: 参考资料（带引用编号）
            citations: 引用列表
            outline: 论文大纲（可选）
            target_words: 目标字数

        Returns:
            GeneratorOutput 包含论文、大纲和字数
        """
        if not evidence_claims:
            raise ValueError("生成论文时缺少结构化证据，无法保证引用一致性。")

        sections = self.generate_outline(topic, evidence_claims, target_words)
        outline_text = "\n".join(
            f"{section.heading}\n- {section.purpose}\n- 参考来源: {section.source_ids or '待补充'}"
            for section in sections
        )

        logger.agent("Generator", "正在撰写论文...")
        drafted_sections: list[str] = []
        for section in sections:
            drafted_sections.append(
                self._generate_section(
                    topic=topic,
                    section=section,
                    evidence_claims=evidence_claims,
                    target_words=target_words,
                    existing_sections=drafted_sections,
                )
            )

        citations_text = "\n".join(citations)
        paper = "\n\n".join(drafted_sections).strip()
        paper = f"{paper}\n\n## 参考文献\n\n{citations_text}"
        word_count = self._count_words(paper)

        logger.success(f"论文生成完成，字数: {word_count}")

        return GeneratorOutput(
            paper=paper,
            outline=outline_text,
            word_count=word_count,
        )

    def generate(
        self,
        topic: str,
        context: str,
        citations: List[str],
        evidence_claims: list[EvidenceClaim],
        target_words: Optional[int] = None,
    ) -> GeneratorOutput:
        """便捷方法：一键生成论文

        Args:
            topic: 论文主题
            context: 参考资料
            citations: 引用列表
            target_words: 目标字数

        Returns:
            GeneratorOutput
        """
        target = target_words or settings.paper.target_word_count
        return self.generate_paper(
            topic,
            context,
            citations,
            evidence_claims=evidence_claims,
            target_words=target,
        )
