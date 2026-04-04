"""交互式 Shell 模块 - 提供类似 opencode 的交互体验"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text
from rich.layout import Layout
from rich.live import Live

from mcp_paper_agent.cli.styles import CONSTELLATION_THEME
from mcp_paper_agent.config import settings

console = Console(theme=CONSTELLATION_THEME)


class Mode(Enum):
    """运行模式"""
    REFLECT = "reflect"
    DIRECT = "direct"


@dataclass
class ShellState:
    """Shell 状态"""
    mode: Mode = Mode.REFLECT
    max_iterations: int = 3
    target_words: int = 1900
    use_cache: bool = True
    verbose: bool = False
    history: List[str] = field(default_factory=list)


@dataclass
class Command:
    """命令定义"""
    name: str
    description: str
    usage: str
    handler: Callable


class InteractiveShell:
    """交互式 Shell

    提供类似 opencode 的交互体验，支持：
    - /mode 切换反思/直接模式
    - /config 配置参数
    - /help 显示帮助
    - /clear 清屏
    - /exit 退出
    - 直接输入主题生成论文
    """

    WELCOME_BANNER = """
[primary]╔════════════════════════════════════════════════════════════════╗
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
╚══════════════════════════════════════════════════════════════╝[/primary]
"""

    def __init__(self):
        self.state = ShellState(
            max_iterations=settings.paper.max_iterations,
            target_words=settings.paper.target_word_count,
        )
        self.running = True
        self.commands = self._register_commands()

    def _register_commands(self) -> Dict[str, Command]:
        """注册命令"""
        return {
            "mode": Command(
                name="mode",
                description="切换运行模式 (reflect/direct)",
                usage="/mode [reflect|direct]",
                handler=self._cmd_mode,
            ),
            "config": Command(
                name="config",
                description="查看或修改配置",
                usage="/config [key=value]",
                handler=self._cmd_config,
            ),
            "set": Command(
                name="set",
                description="设置参数",
                usage="/set <key> <value>",
                handler=self._cmd_set,
            ),
            "help": Command(
                name="help",
                description="显示帮助信息",
                usage="/help [command]",
                handler=self._cmd_help,
            ),
            "clear": Command(
                name="clear",
                description="清空屏幕",
                usage="/clear",
                handler=self._cmd_clear,
            ),
            "history": Command(
                name="history",
                description="显示历史记录",
                usage="/history",
                handler=self._cmd_history,
            ),
            "exit": Command(
                name="exit",
                description="退出程序",
                usage="/exit",
                handler=self._cmd_exit,
            ),
            "quit": Command(
                name="quit",
                description="退出程序",
                usage="/quit",
                handler=self._cmd_exit,
            ),
        }

    def _cmd_mode(self, args: List[str]) -> None:
        """处理 /mode 命令"""
        if not args:
            current = "反思模式" if self.state.mode == Mode.REFLECT else "直接模式"
            console.print(f"\n[info]当前模式: [accent]{current}[/accent][/info]")
            console.print("[dim]  使用 /mode reflect 切换到反思模式[/dim]")
            console.print("[dim]  使用 /mode direct 切换到直接模式[/dim]")
            return

        mode_str = args[0].lower()
        if mode_str == "reflect":
            self.state.mode = Mode.REFLECT
            console.print("\n[success]✓ 已切换到反思模式[/success]")
            console.print("[dim]  将进行多轮评估-修订迭代[/dim]")
        elif mode_str == "direct":
            self.state.mode = Mode.DIRECT
            console.print("\n[success]✓ 已切换到直接模式[/success]")
            console.print("[dim]  将直接生成论文，不进行迭代优化[/dim]")
        else:
            console.print(f"\n[error]✗ 未知模式: {mode_str}[/error]")
            console.print("[dim]  可用模式: reflect, direct[/dim]")

    def _cmd_config(self, args: List[str]) -> None:
        """处理 /config 命令"""
        if not args:
            self._show_config()
            return

        for arg in args:
            if "=" in arg:
                key, value = arg.split("=", 1)
                self._set_config(key.strip(), value.strip())

    def _cmd_set(self, args: List[str]) -> None:
        """处理 /set 命令"""
        if len(args) < 2:
            console.print("\n[error]✗ 用法: /set <key> <value>[/error]")
            console.print("[dim]  可设置: iterations, words, cache, verbose[/dim]")
            return

        key, value = args[0], " ".join(args[1:])
        self._set_config(key, value)

    def _set_config(self, key: str, value: str) -> None:
        """设置配置"""
        try:
            if key == "iterations":
                self.state.max_iterations = int(value)
                console.print(f"\n[success]✓ 最大迭代次数已设置为: {value}[/success]")
            elif key == "words":
                self.state.target_words = int(value)
                console.print(f"\n[success]✓ 目标字数已设置为: {value}[/success]")
            elif key == "cache":
                self.state.use_cache = value.lower() in ("true", "1", "yes", "on")
                status = "开启" if self.state.use_cache else "关闭"
                console.print(f"\n[success]✓ 缓存已{status}[/success]")
            elif key == "verbose":
                self.state.verbose = value.lower() in ("true", "1", "yes", "on")
                status = "开启" if self.state.verbose else "关闭"
                console.print(f"\n[success]✓ 详细模式已{status}[/success]")
            else:
                console.print(f"\n[error]✗ 未知配置项: {key}[/error]")
                console.print("[dim]  可设置: iterations, words, cache, verbose[/dim]")
        except ValueError as e:
            console.print(f"\n[error]✗ 无效值: {e}[/error]")

    def _show_config(self) -> None:
        """显示当前配置"""
        table = Table(
            title="✧ 当前配置 ✧",
            show_header=False,
            border_style="constellation",
            title_style="title",
        )
        table.add_column("Key", style="secondary")
        table.add_column("Value", style="accent")

        mode_str = "反思模式" if self.state.mode == Mode.REFLECT else "直接模式"
        cache_str = "开启" if self.state.use_cache else "关闭"
        verbose_str = "开启" if self.state.verbose else "关闭"

        table.add_row("运行模式", mode_str)
        table.add_row("最大迭代", str(self.state.max_iterations))
        table.add_row("目标字数", str(self.state.target_words))
        table.add_row("缓存", cache_str)
        table.add_row("详细模式", verbose_str)
        table.add_row("模型", settings.openrouter.model)
        table.add_row("搜索模型", settings.openrouter.search_model)

        console.print()
        console.print(table)

    def _cmd_help(self, args: List[str]) -> None:
        """处理 /help 命令"""
        if args and args[0] in self.commands:
            cmd = self.commands[args[0]]
            console.print(f"\n[title]✧ /{cmd.name} ✧[/title]")
            console.print(f"  [secondary]描述:[/secondary] {cmd.description}")
            console.print(f"  [secondary]用法:[/secondary] {cmd.usage}")
            return

        table = Table(
            title="✧ 命令帮助 ✧",
            border_style="constellation",
            title_style="title",
        )
        table.add_column("命令", style="accent", justify="center")
        table.add_column("描述", style="secondary")
        table.add_column("用法", style="dim")

        for cmd in self.commands.values():
            table.add_row(f"/{cmd.name}", cmd.description, cmd.usage)

        console.print()
        console.print(table)
        console.print("\n[dim]💡 直接输入主题即可生成论文[/dim]")

    def _cmd_clear(self, args: List[str]) -> None:
        """处理 /clear 命令"""
        console.clear()
        self._show_prompt_header()

    def _cmd_history(self, args: List[str]) -> None:
        """处理 /history 命令"""
        if not self.state.history:
            console.print("\n[dim]暂无历史记录[/dim]")
            return

        console.print("\n[title]✧ 历史记录 ✧[/title]")
        for i, item in enumerate(self.state.history[-10:], 1):
            console.print(f"  [secondary]{i}.[/secondary] {item}")

    def _cmd_exit(self, args: List[str]) -> None:
        """处理 /exit 命令"""
        self.running = False
        console.print("\n[primary]✦ 感谢使用 Paper Agent，再见！✦[/primary]")

    def _show_prompt_header(self) -> None:
        """显示提示符头部"""
        mode_icon = "🔄" if self.state.mode == Mode.REFLECT else "⚡"
        mode_str = "反思" if self.state.mode == Mode.REFLECT else "直接"
        cache_icon = "📦" if self.state.use_cache else "🚫"

        header = Text()
        header.append("┌─ ", style="dim")
        header.append(f"{mode_icon} {mode_str}模式", style="accent")
        header.append(" │ ", style="dim")
        header.append(f"📝 {self.state.target_words}字", style="secondary")
        header.append(" │ ", style="dim")
        header.append(f"🔄 {self.state.max_iterations}轮", style="secondary")
        header.append(" │ ", style="dim")
        header.append(f"{cache_icon} 缓存", style="secondary")
        header.append("\n└─▶ ", style="dim")

        console.print()
        console.print(header)

    def _generate_paper(self, topic: str) -> None:
        """生成论文"""
        from mcp_paper_agent.core.orchestrator import Orchestrator, OrchestratorResult
        from rich.progress import (
            BarColumn,
            Progress,
            SpinnerColumn,
            TaskProgressColumn,
            TextColumn,
            TimeElapsedColumn,
        )

        self.state.history.append(topic)

        console.print(f"\n[title]✦ 开始生成论文 ✦[/title]")
        console.print(f"[secondary]主题:[/secondary] [accent]{topic}[/accent]\n")

        orchestrator = Orchestrator(
            max_iterations=self.state.max_iterations if self.state.mode == Mode.REFLECT else 1,
            target_word_count=self.state.target_words,
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

            def update_progress(stage: str, step: int, total: int):
                progress.update(
                    task,
                    description=f"[accent]{stage}[/accent]",
                    completed=int(step / total * 100),
                )

            orchestrator.progress_callback = update_progress
            result = orchestrator.generate(topic, use_cache=self.state.use_cache)
            progress.update(task, completed=100)

        self._show_result(result, topic)

    def _show_result(self, result: "OrchestratorResult", topic: str) -> None:
        """显示生成结果"""
        from pathlib import Path
        import re
        from datetime import datetime

        console.print()
        console.rule("[title]✦ 生成完成 ✦[/title]")
        console.print()

        summary = Panel(
            Text.assemble(
                ("主题: ", "secondary"),
                (f"{topic}\n\n", "accent"),
                ("最终分数: ", "secondary"),
                (f"{result.final_score:.2f}\n", "success" if result.final_score >= 8 else "warning"),
                ("最终字数: ", "secondary"),
                (f"{result.word_count}\n", "accent"),
                ("迭代次数: ", "secondary"),
                (f"{result.iterations} 次\n", "iteration"),
                ("引用来源: ", "secondary"),
                (f"{len(result.citations)} 条", "accent"),
            ),
            title="[star]★ 论文摘要 ★[/star]",
            border_style="nebula",
            padding=(1, 2),
        )
        console.print(summary)

        output = Path("./papers")
        output.mkdir(parents=True, exist_ok=True)
        safe_topic = re.sub(r'[<>:"/\\|?*]', "", topic)[:30]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_topic}_{timestamp}.md"
        filepath = output / filename
        filepath.write_text(result.paper, encoding="utf-8")

        console.print()
        console.print(f"[success]✓ 论文已保存至:[/success] [accent]{filepath}[/accent]")

    def run(self) -> None:
        """运行交互式 Shell"""
        console.print(self.WELCOME_BANNER)
        console.print("[dim]输入 /help 查看可用命令，直接输入主题开始生成论文[/dim]")
        self._show_prompt_header()

        while self.running:
            try:
                user_input = Prompt.ask("").strip()

                if not user_input:
                    continue

                if user_input.startswith("/"):
                    parts = user_input[1:].split()
                    cmd_name = parts[0].lower()
                    args = parts[1:] if len(parts) > 1 else []

                    if cmd_name in self.commands:
                        self.commands[cmd_name].handler(args)
                    else:
                        console.print(f"\n[error]✗ 未知命令: /{cmd_name}[/error]")
                        console.print("[dim]  输入 /help 查看可用命令[/dim]")
                else:
                    self._generate_paper(user_input)

                if self.running:
                    self._show_prompt_header()

            except KeyboardInterrupt:
                console.print("\n\n[dim]按 Ctrl+C 再次退出，或输入 /exit[/dim]")
                self._show_prompt_header()
            except EOFError:
                self.running = False
                console.print("\n[primary]✦ 再见！✦[/primary]")


def run_interactive():
    """启动交互式 Shell"""
    shell = InteractiveShell()
    shell.run()
