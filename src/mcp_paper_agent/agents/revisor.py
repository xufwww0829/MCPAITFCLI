"""修订智能体 - 负责针对性修改论文

根据评估报告对论文进行针对性修改，不重写全文，保持迭代稳定性。
支持引用补全、事实修正、结构调整、字数微调等。
"""

import re
from dataclasses import dataclass
from typing import List, Optional

from openai import OpenAI

from mcp_paper_agent.agents.reflector import AssessmentReport
from mcp_paper_agent.config import settings
from mcp_paper_agent.logger import get_logger

logger = get_logger()


@dataclass
class RevisorOutput:
    """修订智能体输出"""
    paper: str
    word_count: int = 0
    changes_made: List[str] = None

    def __post_init__(self):
        if self.changes_made is None:
            self.changes_made = []


class Revisor:
    """修订智能体

    根据评估报告对论文进行针对性修改。

    Attributes:
        client: OpenAI 客户端
        model: 使用的模型名称
    """

    SYSTEM_PROMPT = """你是一位学术论文编辑。请根据审稿意见修改论文。

修改指导原则：
1. 只修改审稿意见中明确指出的位置和问题。
2. 对于缺失引用，请在相应句子后添加正确的[n]标记（参考提供的参考资料）。
3. 对于事实错误，请根据参考资料更正数据或措辞。
4. 对于结构问题（如结论太短），请扩展对应段落，保持与全文风格一致。
5. 格式问题修复指南：
   - 标题标记后缺少空格：将 "#标题" 改为 "# 标题"
   - 引用编号超出范围：删除该引用标记，或替换为最相关的有效引用
   - 缺少参考文献条目：保持现状，不要自动生成虚假引用
6. 保持其他未提及的部分完全不变。
7. 输出完整的修改后论文（Markdown格式），不要输出解释性文字。

重要：直接输出修改后的论文全文，不要添加任何解释或说明。"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.5,
    ):
        """初始化修订智能体

        Args:
            api_key: OpenRouter API Key
            base_url: OpenRouter API 基础 URL
            model: 模型名称
            temperature: 生成温度
        """
        self.api_key = api_key or settings.openrouter.api_key
        self.base_url = base_url or settings.openrouter.base_url
        self.model = model or settings.openrouter.model
        self.temperature = temperature

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )

    def _count_words(self, text: str) -> int:
        """计算中文字数"""
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        english_words = len(re.findall(r'[a-zA-Z]+', text))
        return chinese_chars + english_words

    def _format_issues(self, report: AssessmentReport) -> str:
        """格式化问题列表

        Args:
            report: 评估报告

        Returns:
            格式化的问题描述
        """
        issues = []

        if report.format_issues:
            issues.append("【格式问题】")
            for issue in report.format_issues:
                issues.append(f"- {issue}")

        if report.content_issues:
            issues.append("\n【内容问题】")
            for issue in report.content_issues:
                issues.append(f"- [{issue.type}] {issue.location}")
                if issue.text_snippet:
                    issues.append(f"  原文: {issue.text_snippet}")
                if issue.suggestion:
                    issues.append(f"  建议: {issue.suggestion}")

        if report.word_count < report.target_word_count - 200:
            issues.append(f"\n【字数不足】当前 {report.word_count} 字，目标 {report.target_word_count} 字，需要扩展内容")
        elif report.word_count > report.target_word_count + 200:
            issues.append(f"\n【字数超标】当前 {report.word_count} 字，目标 {report.target_word_count} 字，需要精简内容")

        return "\n".join(issues) if issues else "无明显问题"

    def revise(
        self,
        paper: str,
        report: AssessmentReport,
        context: str,
        citations: List[str],
    ) -> RevisorOutput:
        """修订论文

        Args:
            paper: 当前论文版本
            report: 评估报告
            context: 参考资料
            citations: 引用列表

        Returns:
            RevisorOutput 包含修订后的论文
        """
        logger.agent("Revisor", "正在根据评估报告修订论文...")

        issues_text = self._format_issues(report)
        citations_text = "\n".join(citations)

        user_prompt = f"""【原始论文】
{paper}

【审稿意见】
综合分数: {report.overall_score}/10
{issues_text}

【参考资料（带引用编号）】
{context[:3000]}

【参考文献列表】
{citations_text}

请根据审稿意见修改论文。直接输出修改后的完整论文，不要添加解释。"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=self.temperature,
            max_tokens=4096,
        )

        revised_paper = response.choices[0].message.content or paper
        word_count = self._count_words(revised_paper)

        changes = []
        if report.format_issues:
            changes.append(f"修复 {len(report.format_issues)} 个格式问题")
        if report.content_issues:
            changes.append(f"处理 {len(report.content_issues)} 个内容问题")
        if abs(word_count - report.word_count) > 50:
            changes.append(f"字数从 {report.word_count} 调整为 {word_count}")

        logger.success(f"修订完成，新字数: {word_count}")

        return RevisorOutput(
            paper=revised_paper,
            word_count=word_count,
            changes_made=changes,
        )
