"""日志工具模块 - 基于 rich 的美观日志输出"""

import logging
import sys
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme


custom_theme = Theme(
    {
        "info": "cyan",
        "warning": "yellow",
        "error": "red bold",
        "critical": "red bold reverse",
        "debug": "dim",
        "agent": "magenta",
        "success": "green bold",
        "iteration": "blue bold",
    }
)

console = Console(theme=custom_theme)


class Logger:
    """日志管理器"""

    _instance: Optional["Logger"] = None
    _initialized: bool = False

    def __new__(cls) -> "Logger":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._logger = logging.getLogger("mcp_paper_agent")
        self._logger.setLevel(logging.DEBUG)
        self._logger.handlers.clear()
        self._setup_rich_handler()

    def _setup_rich_handler(self) -> None:
        """设置 Rich 控制台处理器"""
        rich_handler = RichHandler(
            console=console,
            show_time=True,
            show_path=True,
            rich_tracebacks=True,
            markup=True,
        )
        rich_handler.setLevel(logging.DEBUG)
        self._logger.addHandler(rich_handler)

    def setup_file_handler(self, log_file: Path) -> None:
        """设置文件处理器"""
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(formatter)
        self._logger.addHandler(file_handler)

    def set_level(self, level: str) -> None:
        """设置日志级别"""
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }
        self._logger.setLevel(level_map.get(level.upper(), logging.INFO))

    def debug(self, msg: str, *args, **kwargs) -> None:
        self._logger.debug(msg, *args, **kwargs)

    def info(self, msg: str, *args, **kwargs) -> None:
        self._logger.info(msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs) -> None:
        self._logger.warning(msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs) -> None:
        self._logger.error(msg, *args, **kwargs)

    def critical(self, msg: str, *args, **kwargs) -> None:
        self._logger.critical(msg, *args, **kwargs)

    def agent(self, agent_name: str, msg: str) -> None:
        """智能体专用日志"""
        self._logger.info(f"[agent]{agent_name}[/agent]: {msg}")

    def success(self, msg: str) -> None:
        """成功消息"""
        self._logger.info(f"[success]✓ {msg}[/success]")

    def iteration(self, iteration: int, max_iter: int, msg: str) -> None:
        """迭代日志"""
        self._logger.info(
            f"[iteration]迭代 {iteration}/{max_iter}[/iteration]: {msg}"
        )


logger = Logger()


def get_logger() -> Logger:
    """获取日志实例"""
    return logger
