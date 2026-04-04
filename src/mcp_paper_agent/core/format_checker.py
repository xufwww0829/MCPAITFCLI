"""格式审查模块 - 负责检查论文格式规范

使用正则表达式进行确定性格式检查，不依赖 LLM。
检查范围包括：Markdown 语法、论文结构、引用格式、参考文献列表。
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass
class FormatCheckResult:
    """格式检查结果"""
    format_score: float
    sub_scores: Dict[str, int] = field(default_factory=dict)
    issues: List[str] = field(default_factory=list)


class FormatChecker:
    """论文格式审查器

    检查论文的 Markdown 格式规范，包括：
    - 标题语法：# 标记后是否有空格
    - 论文结构：是否包含必需章节（摘要、引言、结论）
    - 引用格式：引用标记是否正确、编号是否在范围内
    - 参考文献列表：格式是否统一、条目数是否匹配
    """

    def __init__(self, paper: str):
        """初始化格式审查器

        Args:
            paper: 论文文本（Markdown 格式）
        """
        self.paper = paper
        self.lines = paper.split("\n")

    def check_heading_syntax(self) -> Tuple[int, List[str]]:
        """检查标题语法

        检查 # 标记后是否有空格，例如 '#标题' 应为 '# 标题'

        Returns:
            (分数, 问题列表)，满分 10 分，每发现一个问题扣 1 分
        """
        score = 10
        issues = []
        for i, line in enumerate(self.lines):
            if line.startswith("#"):
                if re.match(r'^#+[^\s#]', line):
                    score -= 1
                    issues.append(f"行{i+1}: 标题标记后缺少空格 '{line[:20]}...'" )
        return max(score, 0), issues

    def check_structure(self) -> Tuple[int, List[str]]:
        """检查必需章节是否存在

        必需章节：摘要、引言、结论

        Returns:
            (分数, 问题列表)，按存在章节比例计分
        """
        required_sections = ['摘要', '引言', '结论']
        found = [sec for sec in required_sections if sec in self.paper]
        score = int(len(found) / len(required_sections) * 10)
        missing = [sec for sec in required_sections if sec not in found]
        issues = [f"缺少必需章节: {', '.join(missing)}"] if missing else []
        return score, issues

    def check_citation_format(self, citations_count: int) -> Tuple[int, List[str]]:
        """检查引用标记格式和范围

        检查：
        - 论文中是否有引用标记
        - 引用编号是否在有效范围内（1 到 citations_count）
        - 引用后是否紧跟标点符号

        Args:
            citations_count: 参考文献总数

        Returns:
            (分数, 问题列表)
        """
        refs = re.findall(r'\[(\d+)\]', self.paper)
        if not refs:
            return 0, ["论文中没有任何引用标记"]

        invalid_refs = [int(r) for r in refs if int(r) > citations_count or int(r) < 1]
        score = max(0, 10 - len(invalid_refs))
        issues = [f"引用编号超出范围: {invalid_refs}"] if invalid_refs else []

        misplaced = re.findall(r'\[\d+\]\s*[^\.,;:\s]', self.paper)
        if misplaced:
            issues.append(f"发现 {len(misplaced)} 处引用后未紧跟标点符号")
            score = max(0, score - 1)

        return score, issues

    def check_reference_list(self, citations: List[str]) -> Tuple[int, List[str]]:
        """检查参考文献列表格式

        检查：
        - 是否存在参考文献章节
        - 条目数是否与正文引用数匹配
        - 每条参考文献是否包含链接

        Args:
            citations: 参考文献列表

        Returns:
            (分数, 问题列表)
        """
        ref_match = re.search(r'参考文献\s*\n(.*)$', self.paper, re.DOTALL)
        if not ref_match:
            return 0, ["找不到参考文献列表"]
        ref_section = ref_match.group(1)

        lines = ref_section.split('\n')
        expected_count = len(citations)
        actual_count = len([l for l in lines if re.match(r'^\[\d+\]', l.strip())])
        if actual_count != expected_count:
            return 5, [f"参考文献条目数不一致：正文引用{expected_count}条，列表只有{actual_count}条"]

        score = 10
        issues = []
        for i, line in enumerate(lines):
            if re.match(r'^\[\d+\]', line.strip()):
                if 'http' not in line and '://' not in line:
                    score -= 1
                    issues.append(f"参考文献第{i+1}条缺少链接")
        return max(score, 0), issues

    def full_check(self, citations: List[str]) -> FormatCheckResult:
        """执行所有格式检查

        Args:
            citations: 参考文献列表

        Returns:
            FormatCheckResult 包含总分、各维度分数和问题列表
        """
        heading_score, heading_issues = self.check_heading_syntax()
        structure_score, structure_issues = self.check_structure()
        citation_score, citation_issues = self.check_citation_format(len(citations))
        ref_score, ref_issues = self.check_reference_list(citations)

        weights = {'heading': 0.2, 'structure': 0.3, 'citation': 0.3, 'reference': 0.2}
        total_score = (
            heading_score * weights['heading']
            + structure_score * weights['structure']
            + citation_score * weights['citation']
            + ref_score * weights['reference']
        )

        all_issues = heading_issues + structure_issues + citation_issues + ref_issues
        return FormatCheckResult(
            format_score=round(total_score, 1),
            sub_scores={
                'heading': heading_score,
                'structure': structure_score,
                'citation_mark': citation_score,
                'reference_list': ref_score,
            },
            issues=all_issues[:10],
        )
