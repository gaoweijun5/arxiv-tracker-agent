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

    # LLM Provider: "openai" (DeepSeek/OpenAI-compatible) or "anthropic"
    llm_provider: str = "openai"

    # LLM API (OpenAI-compatible: DeepSeek, OpenAI, etc.)
    openai_api_key: str = ""
    openai_api_base: str = "https://api.deepseek.com"
    llm_model: str = "gpt-4o-mini"
    llm_agent_model: str = ""
    llm_temperature: float = 0.3

    # Anthropic API
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"

    # Embedding API (OpenAI-compatible, e.g. DashScope, DeepSeek, OpenAI)
    embedding_api_key: str = ""
    embedding_api_base: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    embedding_model: str = "text-embedding-v4"

    # VLM caption API for Docling table/figure enrichment (OpenAI-compatible)
    vlm_api_key: str = ""
    vlm_api_endpoint: str = ""
    vlm_model: str = ""
    vlm_temperature: float = 0.0
    vlm_max_tokens: int = 512
    vlm_timeout_seconds: float = 60.0
    vlm_image_scale: float = 2.0

    # arXiv
    arxiv_max_results: int = 50
    arxiv_categories: list[str] = ["cs.AI", "cs.CL", "cs.CV", "cs.LG"]
    arxiv_page_size: int = 10
    arxiv_request_interval_seconds: float = 3.0
    arxiv_max_retries: int = 2
    arxiv_rate_limit_backoff_seconds: float = 60.0
    arxiv_request_timeout_seconds: float = 90.0
    arxiv_user_agent: str = "arxiv-tracker-agent/0.1.0"

    # RAG retrieval
    rag_chunk_top_k: int = 15
    rag_retrieval_candidates: int = 30
    rag_confidence_threshold: float = 0.7
    rag_rrf_k: int = 60
    rag_query_rewrite_count: int = 3

    # Scheduler
    daily_fetch_hour: int = 8
    daily_fetch_minute: int = 0

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    def get_paper_path(self, arxiv_id: str) -> Path:
        """Get the file path for a downloaded paper."""
        return self.papers_dir / f"{arxiv_id.replace('/', '_')}.pdf"


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()
