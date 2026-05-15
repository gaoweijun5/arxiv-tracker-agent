"""Application configuration using pydantic-settings."""

from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # App
    app_name: str = "ArXiv Tracker Agent"
    debug: bool = True

    # Paths
    base_dir: Path = Path(__file__).parent.parent.parent
    data_dir: Path = base_dir / "data"
    papers_dir: Path = data_dir / "papers"
    vectors_dir: Path = data_dir / "vectors"

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/arxiv_tracker.db"

    # Vector Store
    chroma_persist_dir: str = "./data/vectors"
    embedding_model: str = "all-MiniLM-L6-v2"

    # LLM API (DeepSeek)
    openai_api_key: str = ""
    openai_api_base: str = "https://api.deepseek.com"
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.3

    # Embedding API (DashScope)
    embedding_api_key: str = ""
    embedding_api_base: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    embedding_model: str = "text-embedding-v4"

    # arXiv
    arxiv_max_results: int = 50
    arxiv_categories: list[str] = ["cs.AI", "cs.CL", "cs.CV", "cs.LG"]

    # Scheduler
    daily_fetch_hour: int = 8
    daily_fetch_minute: int = 0

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    def get_paper_path(self, arxiv_id: str) -> Path:
        """Get the file path for a downloaded paper."""
        return self.papers_dir / f"{arxiv_id.replace('/', '_')}.pdf"


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()
