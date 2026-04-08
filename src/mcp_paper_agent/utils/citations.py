"""引用编号与参考文献后处理。"""

from __future__ import annotations

import re


REFERENCE_HEADING_PATTERN = re.compile(r"^##\s*参考文献\s*$", re.MULTILINE)
REFERENCE_INDEX_PATTERN = re.compile(r"^\[\d+\]\s*")


def _split_reference_section(paper: str) -> tuple[str, str]:
    match = REFERENCE_HEADING_PATTERN.search(paper)
    if not match:
        return paper.rstrip(), ""
    return paper[: match.start()].rstrip(), paper[match.end() :].strip()


def _strip_reference_index(citation: str) -> str:
    return REFERENCE_INDEX_PATTERN.sub("", citation.strip())


def normalize_paper_citations(paper: str, citations: list[str]) -> str:
    """将正文引用和参考文献列表压缩为连续有效编号。"""
    body, _ = _split_reference_section(paper)
    mapping: dict[int, int] = {}
    used_numbers: list[int] = []

    def replace_ref(match: re.Match[str]) -> str:
        old_number = int(match.group(1))
        if old_number < 1 or old_number > len(citations):
            return ""
        if old_number not in mapping:
            mapping[old_number] = len(mapping) + 1
            used_numbers.append(old_number)
        return f"[{mapping[old_number]}]"

    normalized_body = re.sub(r"\[(\d+)\]", replace_ref, body)
    normalized_body = re.sub(r"[ \t]+$", "", normalized_body, flags=re.MULTILINE).strip()

    if used_numbers:
        ordered_citations = [
            f"[{mapping[old_number]}] {_strip_reference_index(citations[old_number - 1])}"
            for old_number in used_numbers
        ]
    else:
        ordered_citations = [
            f"[{index}] {_strip_reference_index(citation)}"
            for index, citation in enumerate(citations, start=1)
        ]

    references_block = "## 参考文献\n\n" + "\n".join(ordered_citations)
    return f"{normalized_body}\n\n{references_block}\n"
