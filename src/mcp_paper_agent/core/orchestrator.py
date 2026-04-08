"""协调器 - 负责流程控制和迭代管理

整合检索、生成、反思、修订四个智能体，管理迭代优化流程。
支持缓存机制，避免重复计算。
"""

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

from diskcache import Cache

from mcp_paper_agent.agents.generator import Generator, GeneratorOutput
from mcp_paper_agent.agents.reflector import AssessmentReport, Reflector
from mcp_paper_agent.agents.retriever import RetrievalOutput, Retriever
from mcp_paper_agent.agents.revisor import Revisor, RevisorOutput
from mcp_paper_agent.config import settings
from mcp_paper_agent.core.citation_checker import CitationChecker
from mcp_paper_agent.logger import get_logger
from mcp_paper_agent.utils.citations import normalize_paper_citations

logger = get_logger()

ProgressCallback = Callable[[str, int, int], None]


@dataclass
class IterationRecord:
    """迭代记录"""
    iteration: int
    score: float
    word_count: int
    issues_count: int


@dataclass
class OrchestratorResult:
    """协调器输出结果"""
    paper: str
    word_count: int
    iterations: int
    final_score: float
    iteration_history: List[IterationRecord] = field(default_factory=list)
    citations: List[str] = field(default_factory=list)
    sources: List[dict] = field(default_factory=list)
    from_cache: bool = False


class Orchestrator:
    """协调器

    整合四个智能体，管理论文生成的迭代优化流程。

    流程：
    1. 检查缓存
    2. 检索智能体 -> 获取资料
    3. 生成智能体 -> 生成初稿
    4. 循环迭代：反思 -> 修订 -> 检查终止条件
    5. 返回最终结果

    Attributes:
        retriever: 检索智能体
        generator: 生成智能体
        reflector: 反思智能体
        revisor: 修订智能体
        cache: 磁盘缓存
    """

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        max_iterations: Optional[int] = None,
        min_quality_score: Optional[float] = None,
        target_word_count: Optional[int] = None,
        word_count_tolerance: Optional[int] = None,
        progress_callback: Optional[ProgressCallback] = None,
    ):
        """初始化协调器

        Args:
            cache_dir: 缓存目录
            max_iterations: 最大迭代次数
            min_quality_score: 最低质量分数阈值
            target_word_count: 目标字数
            word_count_tolerance: 字数允许偏差
            progress_callback: 进度回调函数 (stage_name, current_step, total_steps)
        """
        self.max_iterations = max_iterations or settings.paper.max_iterations
        self.min_quality_score = min_quality_score or settings.paper.min_quality_score
        self.target_word_count = target_word_count or settings.paper.target_word_count
        self.word_count_tolerance = word_count_tolerance or settings.paper.word_count_tolerance
        self.progress_callback = progress_callback

        self.retriever = Retriever()
        self.generator = Generator()
        self.reflector = Reflector()
        self.revisor = Revisor()
        self.min_citation_score = 8.0
        self.max_supplementary_rounds = settings.search.supplementary_max_total_rounds

        self.cache_dir = cache_dir or settings.cache.cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache = Cache(str(self.cache_dir / "paper_cache"))

    def _report_progress(self, stage: str, step: int, total: int):
        """报告进度"""
        if self.progress_callback:
            self.progress_callback(stage, step, total)

    def _get_paper_cache_key(self, topic: str, model: str) -> str:
        """生成论文缓存键"""
        content = f"paper:{topic}:{model}:{self.max_iterations}:{self.target_word_count}"
        return hashlib.md5(content.encode()).hexdigest()

    def _check_termination(
        self, report: AssessmentReport, iteration: int
    ) -> tuple[bool, str]:
        """检查终止条件

        Args:
            report: 评估报告
            iteration: 当前迭代次数

        Returns:
            (是否终止, 原因)
        """
        word_deviation = abs(report.word_count - self.target_word_count)

        if report.overall_score >= self.min_quality_score and word_deviation <= self.word_count_tolerance:
            return True, f"质量达标 (分数: {report.overall_score}, 字数偏差: {word_deviation})"

        if iteration >= self.max_iterations:
            return True, f"达到最大迭代次数 ({self.max_iterations})"

        return False, "继续迭代"

    def _ensure_evidence_coverage(self, retrieval_output: RetrievalOutput, topic: str) -> RetrievalOutput:
        """确保综述所需的证据类型覆盖到位，不足则自动补搜。"""
        coverage = self.retriever.evidence_extractor.check_coverage(retrieval_output.evidence_claims)
        if coverage.is_sufficient:
            return retrieval_output

        logger.warning(
            f"证据覆盖不足: {coverage.suggestions}，将执行补充搜索"
        )
        queries: list[str] = []
        for missing_type in coverage.missing_types:
            if missing_type == "regulation":
                queries.append(f"{topic} 标准 法规 分级")
            elif missing_type == "report":
                queries.append(f"{topic} 市场 报告 趋势")
            elif missing_type == "company":
                queries.extend(
                    [
                        f"{topic} 企业 案例 官方",
                        f"{topic} 车企 智驾 案例",
                    ]
                )

        supplementary = self.retriever.supplementary_search(
            queries=queries,
            existing_context=retrieval_output.context,
        )

        merged_citations = retrieval_output.citations + [
            citation
            for citation in supplementary.citations
            if citation not in retrieval_output.citations
        ]
        merged_sources = retrieval_output.sources + [
            source for source in supplementary.sources
            if source.url not in {existing.url for existing in retrieval_output.sources}
        ]
        merged_claims = retrieval_output.evidence_claims + [
            claim for claim in supplementary.evidence_claims
            if (claim.source_title, claim.claim) not in {
                (existing.source_title, existing.claim)
                for existing in retrieval_output.evidence_claims
            }
        ]

        return RetrievalOutput(
            context=supplementary.context,
            citations=merged_citations,
            sources=merged_sources,
            evidence_claims=merged_claims,
        )

    def _ensure_citation_quality(
        self,
        paper: str,
        evidence_claims: list,
    ) -> None:
        """引用一致性不过关时阻断出稿。"""
        citation_result = CitationChecker(evidence_claims).check(paper)
        if citation_result.score < self.min_citation_score:
            issue_summary = "; ".join(issue.message for issue in citation_result.issues[:5])
            raise ValueError(
                f"引用一致性未达标 ({citation_result.score}/{self.min_citation_score})，已阻断出稿: {issue_summary}"
            )

    def _run_single_iteration(
        self,
        paper: str,
        context: str,
        citations: List[str],
        iteration: int,
    ) -> tuple[str, AssessmentReport]:
        """执行单次迭代

        Args:
            paper: 当前论文版本
            context: 参考资料
            citations: 引用列表
            iteration: 当前迭代次数

        Returns:
            (新论文, 评估报告)
        """
        logger.iteration(iteration, self.max_iterations, "开始评估")

        report = self.reflector.assess(
            paper=paper,
            context=context,
            citations=citations,
            target_word_count=self.target_word_count,
        )

        should_stop, reason = self._check_termination(report, iteration)
        if should_stop:
            logger.info(f"迭代终止: {reason}")
            return paper, report

        logger.iteration(iteration, self.max_iterations, "开始修订")
        result = self.revisor.revise(
            paper=paper,
            report=report,
            context=context,
            citations=citations,
        )

        return result.paper, report

    def generate(
        self,
        topic: str,
        use_cache: bool = True,
    ) -> OrchestratorResult:
        """生成论文

        Args:
            topic: 论文主题
            use_cache: 是否使用缓存

        Returns:
            OrchestratorResult 包含论文和迭代统计
        """
        cache_key = self._get_paper_cache_key(topic, settings.openrouter.model)

        if use_cache and cache_key in self.cache:
            logger.info("从缓存加载论文")
            cached = self.cache[cache_key]
            return OrchestratorResult(
                paper=cached["paper"],
                word_count=cached["word_count"],
                iterations=cached["iterations"],
                final_score=cached["final_score"],
                iteration_history=[
                    IterationRecord(**r) for r in cached.get("iteration_history", [])
                ],
                citations=cached["citations"],
                from_cache=True,
            )

        total_steps = 2 + self.max_iterations * 2
        current_step = 0

        logger.info(f"开始生成论文: {topic}")
        iteration_history: List[IterationRecord] = []

        current_step += 1
        self._report_progress("检索资料中...", current_step, total_steps)
        logger.agent("Orchestrator", "执行检索...")
        retrieval_output: RetrievalOutput = self.retriever.search(topic)
        retrieval_output = self._ensure_evidence_coverage(retrieval_output, topic)
        context = retrieval_output.context
        citations = retrieval_output.citations
        evidence_claims = retrieval_output.evidence_claims

        current_step += 1
        self._report_progress("生成初稿中...", current_step, total_steps)
        logger.agent("Orchestrator", "生成初稿...")
        gen_output: GeneratorOutput = self.generator.generate(
            topic=topic,
            context=context,
            citations=citations,
            evidence_claims=evidence_claims,
            target_words=self.target_word_count,
        )
        current_paper = normalize_paper_citations(gen_output.paper, citations)
        supplementary_rounds_used = 0

        for iteration in range(1, self.max_iterations + 1):
            current_step += 1
            self._report_progress(f"第 {iteration} 轮评估...", current_step, total_steps)
            current_paper, report = self._run_single_iteration(
                paper=current_paper,
                context=context,
                citations=citations,
                iteration=iteration,
            )
            current_paper = normalize_paper_citations(current_paper, citations)

            iteration_history.append(
                IterationRecord(
                    iteration=iteration,
                    score=report.overall_score,
                    word_count=report.word_count,
                    issues_count=len(report.content_issues) + len(report.format_issues),
                )
            )

            if (
                report.supplementary_search_needed
                and report.suggested_search_queries
                and supplementary_rounds_used < self.max_supplementary_rounds
            ):
                logger.agent("Orchestrator", "执行补充搜索...")
                supp_output = self.retriever.supplementary_search(
                    queries=report.suggested_search_queries,
                    existing_context=context,
                )
                context = supp_output.context
                citations = supp_output.citations
                evidence_claims = supp_output.evidence_claims
                supplementary_rounds_used += 1

            should_stop, _ = self._check_termination(report, iteration)
            if should_stop:
                break

            current_step += 1
            self._report_progress(f"第 {iteration} 轮修订...", current_step, total_steps)

        final_report = self.reflector.assess(
            paper=current_paper,
            context=context,
            citations=citations,
            target_word_count=self.target_word_count,
        )

        current_paper = normalize_paper_citations(current_paper, citations)
        self._ensure_citation_quality(current_paper, evidence_claims)

        result = OrchestratorResult(
            paper=current_paper,
            word_count=final_report.word_count,
            iterations=len(iteration_history),
            final_score=final_report.overall_score,
            iteration_history=iteration_history,
            citations=citations,
            sources=[
                {"title": s.title, "url": s.url}
                for s in retrieval_output.sources
            ],
            from_cache=False,
        )

        self.cache.set(
            cache_key,
            {
                "paper": result.paper,
                "word_count": result.word_count,
                "iterations": result.iterations,
                "final_score": result.final_score,
                "iteration_history": [
                    {
                        "iteration": r.iteration,
                        "score": r.score,
                        "word_count": r.word_count,
                        "issues_count": r.issues_count,
                    }
                    for r in result.iteration_history
                ],
                "citations": result.citations,
            },
        )

        logger.success(f"论文生成完成，迭代 {result.iterations} 次，最终分数: {result.final_score}")
        return result

    def clear_cache(self) -> None:
        """清空缓存"""
        self.cache.clear()
        self.retriever.clear_cache()
        logger.info("所有缓存已清空")
