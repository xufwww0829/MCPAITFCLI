"""CLI 主入口 - 星座主题命令行界面

使用 click + rich 实现美观的命令行交互体验。
"""

import time
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.text import Text

from mcp_paper_agent import __version__
from mcp_paper_agent.cli.styles import (
    BANNER,
    CONSTELLATION_THEME,
    format_score,
    format_word_count,
)
from mcp_paper_agent.config import settings
from mcp_paper_agent.core.orchestrator import Orchestrator, OrchestratorResult

console = Console(theme=CONSTELLATION_THEME)


def print_banner():
    """打印星座主题 Banner"""
    console.print(BANNER, style="primary")
    console.print()


def print_config_info():
    """打印配置信息"""
    config_table = Table(
        title="✧ 配置信息 ✧",
        show_header=False,
        border_style="constellation",
        title_style="title",
    )
    config_table.add_column("Key", style="secondary")
    config_table.add_column("Value", style="accent")

    config_table.add_row("模型", settings.openrouter.model)
    config_table.add_row("目标字数", str(settings.paper.target_word_count))
    config_table.add_row("最大迭代", str(settings.paper.max_iterations))
    config_table.add_row("质量阈值", str(settings.paper.min_quality_score))

    console.print(config_table)
    console.print()


def print_iteration_progress(result: OrchestratorResult):
    """打印迭代进度表"""
    if not result.iteration_history:
        return

    table = Table(
        title="✧ 迭代历程 ✧",
        border_style="constellation",
        title_style="title",
    )
    table.add_column("轮次", style="iteration", justify="center")
    table.add_column("分数", justify="center")
    table.add_column("字数", style="accent", justify="center")
    table.add_column("问题数", style="warning", justify="center")

    for record in result.iteration_history:
        table.add_row(
            f"第 {record.iteration} 轮",
            format_score(record.score),
            str(record.word_count),
            str(record.issues_count),
        )

    console.print()
    console.print(table)


def print_result_summary(result: OrchestratorResult, topic: str):
    """打印结果摘要"""
    console.print()
    console.rule("[title]✦ 生成完成 ✦[/title]")
    console.print()

    summary = Panel(
        Text.assemble(
            ("主题: ", "secondary"),
            (f"{topic}\n\n", "accent"),
            ("最终分数: ", "secondary"),
            format_score(result.final_score),
            ("\n", ""),
            ("最终字数: ", "secondary"),
            format_word_count(
                result.word_count,
                settings.paper.target_word_count,
                settings.paper.word_count_tolerance,
            ),
            ("\n", ""),
            ("迭代次数: ", "secondary"),
            (f"{result.iterations} 次", "iteration"),
            ("\n", ""),
            ("引用来源: ", "secondary"),
            (f"{len(result.citations)} 条", "accent"),
        ),
        title="[star]★ 论文摘要 ★[/star]",
        border_style="nebula",
        padding=(1, 2),
    )
    console.print(summary)


def print_paper_preview(paper: str, lines: int = 20):
    """打印论文预览"""
    paper_lines = paper.split("\n")[:lines]
    preview = "\n".join(paper_lines)
    if len(paper_lines) < len(paper.split("\n")):
        preview += f"\n\n... (共 {len(paper.split(chr(10)))} 行)"

    panel = Panel(
        preview,
        title="[star]★ 论文预览 ★[/star]",
        border_style="constellation",
        padding=(1, 1),
    )
    console.print()
    console.print(panel)


def save_paper(paper: str, topic: str, output_dir: Optional[Path] = None) -> Path:
    """保存论文到文件"""
    import re
    from datetime import datetime

    output = output_dir or Path("./papers")
    output.mkdir(parents=True, exist_ok=True)

    safe_topic = re.sub(r'[<>:"/\\|?*]', "", topic)[:30]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{safe_topic}_{timestamp}.md"
    filepath = output / filename

    filepath.write_text(paper, encoding="utf-8")
    return filepath


@click.group(invoke_without_command=True)
@click.option("--version", "-v", is_flag=True, help="显示版本信息")
@click.pass_context
def main(ctx: click.Context, version: bool):
    """✦ MCP Paper Agent - 反思智能体论文生成系统 ✦

    基于迭代优化的学术论文自动生成工具，采用星座主题界面。
    """
    if version:
        console.print(f"[star]★[/star] mcp-paper-agent version {__version__}")
        return

    if ctx.invoked_subcommand is None:
        print_banner()
        console.print("[info]使用 'mcp-paper generate <主题>' 开始生成论文[/info]")
        console.print("[dim]使用 'mcp-paper --help' 查看所有命令[/dim]")


@main.command()
@click.argument("topic")
@click.option("--output", "-o", type=click.Path(), help="输出文件路径")
@click.option("--max-iter", "-i", default=3, help="最大迭代次数")
@click.option("--words", "-w", default=1900, help="目标字数")
@click.option("--no-cache", is_flag=True, help="禁用缓存")
@click.option("--preview", "-p", is_flag=True, help="显示论文预览")
@click.option("--verbose", "-v", is_flag=True, help="详细输出")
def generate(
    topic: str,
    output: Optional[str],
    max_iter: int,
    words: int,
    no_cache: bool,
    preview: bool,
    verbose: bool,
):
    """✦ 生成论文

    根据给定主题自动生成学术论文。

    示例:
        mcp-paper generate "人工智能在医疗领域的应用"
        mcp-paper generate "量子计算的发展前景" -w 2000 -i 5
    """
    print_banner()

    if verbose:
        print_config_info()

    console.print(
        Panel(
            Text.assemble(
                ("✦ ", "star"),
                (topic, "title"),
                (" ✦", "star"),
            ),
            title="[constellation]★ 论文主题 ★[/constellation]",
            border_style="primary",
        )
    )
    console.print()

    orchestrator = Orchestrator(
        max_iterations=max_iter,
        target_word_count=words,
    )

    with Progress(
        SpinnerColumn(spinner_name="star"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=40, complete_style="progress.complete", finished_style="progress.bar"),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[accent]正在生成论文...[/accent]", total=100)

        stages = [
            ("[agent.retriever]检索资料中...[/agent.retriever]", 10),
            ("[agent.generator]生成初稿中...[/agent.generator]", 30),
        ]

        for i in range(max_iter):
            stages.append(
                (f"[agent.reflector]第 {i+1} 轮评估...[/agent.reflector]", 30 + i * 20 + 10)
            )
            if i < max_iter - 1:
                stages.append(
                    (f"[agent.revisor]第 {i+1} 轮修订...[/agent.revisor]", 30 + i * 20 + 20)
                )

        current = 0
        for desc, target_val in stages:
            progress.update(task, description=desc)
            while current < target_val:
                time.sleep(0.05)
                current += 1
                progress.update(task, completed=current)

        result = orchestrator.generate(topic, use_cache=not no_cache)
        progress.update(task, completed=100)

    print_result_summary(result, topic)

    if verbose:
        print_iteration_progress(result)

    if preview:
        print_paper_preview(result.paper)

    output_path = save_paper(result.paper, topic, Path(output) if output else None)
    console.print()
    console.print(
        f"[success]✓ 论文已保存至:[/success] [accent]{output_path}[/accent]"
    )


@main.command()
def config():
    """✦ 显示当前配置"""
    print_banner()
    print_config_info()

    console.print("[title]环境变量:[/title]")
    env_table = Table(show_header=False, border_style="dim")
    env_table.add_column("Key", style="secondary")
    env_table.add_column("Value", style="accent")

    env_vars = [
        ("OPENROUTER_API_KEY", "***" if settings.openrouter.api_key else "未设置"),
        ("OPENROUTER_MODEL", settings.openrouter.model),
        ("TAVILY_API_KEY", "***" if settings.tavily.api_key else "未设置"),
        ("TARGET_WORD_COUNT", str(settings.paper.target_word_count)),
        ("MAX_ITERATIONS", str(settings.paper.max_iterations)),
    ]

    for key, value in env_vars:
        env_table.add_row(key, value)

    console.print(env_table)


@main.command()
@click.option("--all", "-a", "clear_all", is_flag=True, help="清空所有缓存")
def cache(clear_all: bool):
    """✦ 缓存管理"""
    print_banner()

    if clear_all:
        orchestrator = Orchestrator()
        orchestrator.clear_cache()
        console.print("[success]✓ 所有缓存已清空[/success]")
    else:
        console.print("[info]使用 --all 参数清空所有缓存[/info]")


if __name__ == "__main__":
    main()