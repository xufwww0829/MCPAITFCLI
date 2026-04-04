"""星座主题样式配置

定义 CLI 界面的星座主题视觉效果，包括配色、图标、动画等。
"""

from rich.style import Style
from rich.text import Text
from rich.theme import Theme

CONSTELLATION_THEME = Theme(
    {
        "primary": "#7B68EE",
        "secondary": "#9370DB",
        "accent": "#E6E6FA",
        "star": "#FFD700 bold",
        "constellation": "#87CEEB",
        "nebula": "#DDA0DD",
        "cosmos": "#4B0082",
        "meteor": "#00FFFF",
        "title": "#E6E6FA bold",
        "subtitle": "#B0C4DE",
        "success": "#98FB98 bold",
        "warning": "#FFD700",
        "error": "#FF6B6B bold",
        "info": "#87CEEB",
        "dim": "#696969",
        "highlight": "#FFD700 bold",
        "agent.retriever": "#87CEEB bold",
        "agent.generator": "#98FB98 bold",
        "agent.reflector": "#DDA0DD bold",
        "agent.revisor": "#FFB6C1 bold",
        "agent.orchestrator": "#FFD700 bold",
        "progress.bar": "#7B68EE",
        "progress.complete": "#98FB98",
        "iteration": "#00CED1 bold",
        "score.high": "#98FB98 bold",
        "score.medium": "#FFD700",
        "score.low": "#FF6B6B",
    }
)

STAR_CHARS = ["✦", "✧", "★", "☆", "✴", "✵", "❋", "❊"]

CONSTELLATION_PATTERNS = {
    "orion": ["  ★  ", " ☆ ☆ ", "  |  ", "☆   ☆"],
    "big_dipper": ["☆─☆─☆", "    │", "  ☆─★─☆"],
    "cassiopeia": ["☆ ☆ ★ ☆ ☆"],
}

BANNER = """
╔══════════════════════════════════════════════════════════════╗
║  ✦  ✧  ★  ☆  ✴  ✵  ❋  ❊  ✦  ✧  ★  ☆  ✴  ✵  ❋  ❊  ✦  ✧  ║
║                                                              ║
║    ██████╗ ██████╗  ██████╗ ██████╗  ██████╗ ███╗   ██╗     ║
║   ██╔════╝██╔══██╗██╔═══██╗██╔══██╗██╔═══██╗████╗  ██║     ║
║   ██║     ██████╔╝██║   ██║██║  ██║██║   ██║██╔██╗ ██║     ║
║   ██║     ██╔══██╗██║   ██║██║  ██║██║   ██║██║╚██╗██║     ║
║   ╚██████╗██║  ██║╚██████╔╝██████╔╝╚██████╔╝██║ ╚████║     ║
║    ╚═════╝╚═╝  ╚═╝ ╚═════╝ ╚═════╝  ╚═════╝ ╚═╝  ╚═══╝     ║
║                                                              ║
║           ✦ Paper Agent - 反思智能体论文生成系统 ✦            ║
║                                                              ║
║  ✦  ✧  ★  ☆  ✴  ✵  ❋  ❊  ✦  ✧  ★  ☆  ✴  ✵  ❋  ❊  ✦  ✧  ║
╚══════════════════════════════════════════════════════════════╝
"""

AGENT_ICONS = {
    "Retriever": "🔭",
    "Generator": "✍️",
    "Reflector": "🪞",
    "Revisor": "✏️",
    "Orchestrator": "🌌",
}

AGENT_NAMES_CN = {
    "Retriever": "检索智能体",
    "Generator": "生成智能体",
    "Reflector": "反思智能体",
    "Revisor": "修订智能体",
    "Orchestrator": "协调器",
}


def get_star_line(width: int = 60) -> str:
    """生成星星装饰线"""
    import random
    stars = [random.choice(STAR_CHARS) for _ in range(width // 2)]
    return " ".join(stars)


def format_agent_header(agent_name: str) -> Text:
    """格式化智能体标题"""
    icon = AGENT_ICONS.get(agent_name, "✦")
    cn_name = AGENT_NAMES_CN.get(agent_name, agent_name)
    return Text.assemble(
        ("✦ ", "star"),
        (f"{icon} ", "highlight"),
        (cn_name, f"agent.{agent_name.lower()}"),
        (" ✦", "star"),
    )


def format_score(score: float) -> Text:
    """格式化分数显示"""
    if score >= 8.0:
        style = "score.high"
        indicator = "★"
    elif score >= 6.0:
        style = "score.medium"
        indicator = "☆"
    else:
        style = "score.low"
        indicator = "✧"

    return Text.assemble(
        (indicator + " ", style),
        (f"{score:.1f}", style),
        ("/10", "dim"),
    )


def format_word_count(current: int, target: int, tolerance: int = 200) -> Text:
    """格式化字数显示"""
    deviation = abs(current - target)
    if deviation <= tolerance:
        style = "success"
        status = "✓"
    elif deviation <= tolerance + 100:
        style = "warning"
        status = "~"
    else:
        style = "error"
        status = "✗"

    return Text.assemble(
        (f"{status} ", style),
        (f"{current}", "accent"),
        (f"/{target}字", "dim"),
    )