"""生成智能体 - 负责大纲生成和论文写作

使用 OpenRouter API 调用 LLM 生成学术论文。
支持大纲生成、逐节写作和字数控制。
"""

from dataclasses import dataclass
from typing import List, Optional

from openai import OpenAI

from mcp_paper_agent.config import settings
from mcp_paper_agent.logger import get_logger

logger = get_logger()


@dataclass
class GeneratorOutput:
    """生成智能体输出"""
    paper: str
    outline: Optional[str] = None
    word_count: int = 0


class Generator:
    """生成智能体

    负责论文大纲生成和正文写作。

    Attributes:
        client: OpenAI 客户端（兼容 OpenRouter）
        model: 使用的模型名称
        temperature: 生成温度
        max_tokens: 最大生成 token 数
    """

    OUTLINE_SYSTEM_PROMPT = """你是一位学术论文写作专家。请根据给定的主题和参考资料，生成一个结构清晰的论文大纲。

大纲要求：
1. 包含以下章节：摘要、引言、正文（2-3个小节）、结论
2. 每个章节简要说明要写的内容
3. 确保逻辑连贯，层次分明
4. 输出格式使用 Markdown"""

    PAPER_SYSTEM_PROMPT = """你是一位学术论文写作专家。请根据大纲和参考资料撰写一篇学术论文。

写作要求：
1. 使用 Markdown 格式
2. 论点必须有参考资料支撑，在相应位置标注引用编号 [n]
3. 只能使用提供的参考资料中的事实，不得编造案例、机构、数据、政策或链接
4. 引用编号必须与参考资料中的编号一致，不能张冠李戴
5. 语言学术化、客观，避免口语化表达
6. 确保结构完整，逻辑清晰
7. 字数控制在目标范围内
8. 在文末保留“## 参考文献”章节，但不要新增未提供的来源"""

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

    def _count_words(self, text: str) -> int:
        """计算中文字数

        中文字符按 1 个字计算，英文单词按 1 个字计算。
        """
        import re
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        english_words = len(re.findall(r'[a-zA-Z]+', text))
        return chinese_chars + english_words

    def generate_outline(
        self, topic: str, context: str, target_words: int = 1900
    ) -> str:
        """生成论文大纲

        Args:
            topic: 论文主题
            context: 参考资料（带引用编号）
            target_words: 目标字数

        Returns:
            论文大纲（Markdown 格式）
        """
        logger.agent("Generator", "正在生成论文大纲...")

        user_prompt = f"""【论文主题】{topic}
【目标字数】{target_words}字
【参考资料】
{context}

请生成论文大纲。"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.OUTLINE_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

        outline = response.choices[0].message.content or ""
        logger.success("大纲生成完成")
        return outline

    def generate_paper(
        self,
        topic: str,
        context: str,
        citations: List[str],
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
        if outline is None:
            outline = self.generate_outline(topic, context, target_words)

        logger.agent("Generator", "正在撰写论文...")

        citations_text = "\n".join(citations)
        user_prompt = f"""【论文主题】{topic}
【目标字数】{target_words}字（允许±200字偏差）
【论文大纲】
{outline}

【参考资料（带引用编号）】
{context}

【参考文献列表】
{citations_text}

请根据以上信息撰写完整的学术论文。注意：
1. 在正文中引用资料时使用 [n] 标记，且编号必须与参考资料中的编号一致
2. 不得把一个来源的编号写给另一个来源
3. 只使用参考资料中能够核实的信息
4. 在文末包含“## 参考文献”章节
5. 控制字数在目标范围内"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.PAPER_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

        paper = response.choices[0].message.content or ""
        word_count = self._count_words(paper)

        logger.success(f"论文生成完成，字数: {word_count}")

        return GeneratorOutput(
            paper=paper,
            outline=outline,
            word_count=word_count,
        )

    def generate(
        self,
        topic: str,
        context: str,
        citations: List[str],
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
        return self.generate_paper(topic, context, citations, target_words=target)
