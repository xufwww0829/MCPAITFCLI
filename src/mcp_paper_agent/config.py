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
        default="openrouter",
        description="搜索提供商: openrouter 或 tavily",
    )
    max_results: int = Field(default=10, description="每次搜索返回的最大结果数")


class PaperConfig(BaseSettings):
    """论文生成配置"""

    model_config = SettingsConfigDict(env_prefix="")

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

    model_config = SettingsConfigDict(env_prefix="")

    cache_dir: Path = Field(default=Path("./cache"), description="缓存目录")
    cache_expire_days: int = Field(default=7, description="缓存过期天数")

    @field_validator("cache_dir", mode="before")
    @classmethod
    def ensure_path(cls, v: str | Path) -> Path:
        return Path(v) if isinstance(v, str) else v


class LogConfig(BaseSettings):
    """日志配置"""

    model_config = SettingsConfigDict(env_prefix="")

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
    paper: PaperConfig = Field(default_factory=PaperConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    log: LogConfig = Field(default_factory=LogConfig)

    @classmethod
    def load(cls) -> "Settings":
        """加载配置"""
        return cls(
            openrouter=OpenRouterConfig(),
            search=SearchConfig(),
            paper=PaperConfig(),
            cache=CacheConfig(),
            log=LogConfig(),
        )


settings: Settings = Settings.load()
