"""配置管理模块 - 使用 pydantic-settings 管理环境变量和配置"""

from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class OpenRouterConfig(BaseSettings):
    """OpenRouter API 配置"""

    model_config = SettingsConfigDict(
        env_prefix="OPENROUTER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_key: str = Field(default="", description="OpenRouter API Key")
    base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        description="OpenRouter API 基础 URL",
    )
    model: str = Field(
        default="openai/gpt-4o-mini",
        description="使用的模型名称",
    )
    search_model: str = Field(
        default="perplexity/sonar",
        description="搜索用的联网模型名称",
    )
    temperature: float = Field(default=0.7, description="生成温度")
    max_tokens: int = Field(default=4096, description="最大生成 token 数")


class SearchConfig(BaseSettings):
    """搜索配置"""

    model_config = SettingsConfigDict(
        env_prefix="SEARCH_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    provider: str = Field(
        default="mcp",
        description="搜索提供商: mcp、openrouter 或 tavily",
    )
    max_results: int = Field(default=10, description="每次搜索返回的最大结果数")
    supplementary_max_queries: int = Field(default=1, description="每轮补充搜索最多执行的查询数")
    supplementary_max_total_rounds: int = Field(default=2, description="整篇论文最多允许的补充搜索轮次")
    supplementary_max_results: int = Field(default=4, description="补充搜索每次最多返回的结果数")


class MCPConfig(BaseSettings):
    """MCP 搜索配置"""

    model_config = SettingsConfigDict(
        env_prefix="MCP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    server_url: str = Field(default="", description="MCP 服务器 URL")
    server_command: str = Field(default="", description="stdio 模式下的 MCP 启动命令")
    server_args: str = Field(default="", description="stdio 模式下的 MCP 启动参数")
    api_key: str = Field(default="", description="MCP API Key")
    search_tool: str = Field(default="web_search", description="MCP 搜索工具名称")
    fetch_tool: str = Field(default="fetch_url", description="MCP 页面抓取工具名称")
    timeout: float = Field(default=30.0, description="MCP 调用超时时间（秒）")
    transport: str = Field(default="stdio", description="MCP 传输方式：stdio 或 http")

    @property
    def server_args_list(self) -> list[str]:
        return [arg for arg in self.server_args.split() if arg]


class PaperConfig(BaseSettings):
    """论文生成配置"""

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    target_word_count: int = Field(default=1900, description="目标字数")
    word_count_tolerance: int = Field(default=200, description="字数允许偏差")
    max_iterations: int = Field(default=3, description="最大迭代次数")
    min_quality_score: float = Field(default=8.0, description="最低质量分数阈值")

    @property
    def word_count_range(self) -> tuple[int, int]:
        """返回字数范围 (最小, 最大)"""
        return (
            self.target_word_count - self.word_count_tolerance,
            self.target_word_count + self.word_count_tolerance,
        )


class CacheConfig(BaseSettings):
    """缓存配置"""

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    cache_dir: Path = Field(default=Path("./cache"), description="缓存目录")
    cache_expire_days: int = Field(default=7, description="缓存过期天数")

    @field_validator("cache_dir", mode="before")
    @classmethod
    def ensure_path(cls, v: str | Path) -> Path:
        return Path(v) if isinstance(v, str) else v


class LogConfig(BaseSettings):
    """日志配置"""

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    log_level: str = Field(default="INFO", description="日志级别")
    log_file: Optional[Path] = Field(default=None, description="日志文件路径")

    @field_validator("log_file", mode="before")
    @classmethod
    def ensure_path(cls, v: str | Path | None) -> Path | None:
        if v is None:
            return None
        return Path(v) if isinstance(v, str) else v


class Settings(BaseSettings):
    """全局配置聚合类"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openrouter: OpenRouterConfig = Field(default_factory=OpenRouterConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)
    paper: PaperConfig = Field(default_factory=PaperConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    log: LogConfig = Field(default_factory=LogConfig)

    @classmethod
    def load(cls, env_file: str | Path | None = ".env") -> "Settings":
        """加载配置"""
        return cls(
            _env_file=env_file,
            openrouter=OpenRouterConfig(_env_file=env_file),
            search=SearchConfig(_env_file=env_file),
            mcp=MCPConfig(_env_file=env_file),
            paper=PaperConfig(_env_file=env_file),
            cache=CacheConfig(_env_file=env_file),
            log=LogConfig(_env_file=env_file),
        )


settings: Settings = Settings.load()


def reload_settings(env_file: str | Path | None = ".env") -> Settings:
    """重新加载全局配置并原地更新 settings 对象。"""
    new_settings = Settings.load(env_file=env_file)
    settings.__dict__.clear()
    settings.__dict__.update(new_settings.__dict__)
    return settings
